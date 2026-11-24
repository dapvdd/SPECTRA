"""M3.1 Task 2 — acquisition pipeline: dedup, batches, checkpoint, publish.

Orchestrates a manifest of verified SKUs into the EXISTING M3 publisher
(``backend.app.publishing.publisher``) with no new services or databases:

(a) load + fail-closed-validate the manifest;
(b) dedup on canonical_key — duplicate keys become a conflict quarantine
    list (never auto-merged, mirroring the publisher's R2 gate);
(c) convert MATCHED VerifiedSKUs into publisher-compatible record dicts
    shaped EXACTLY like ``pilot_seed._sku_record()`` output;
(d) dry-run first, then publish in bounded batches 10 -> 25 -> 50 -> 100
    (cumulative deltas, same shape as ``pilot_seed.iter_batches``);
(e) checkpoint after every batch to ``{manifest_path}.progress.json`` so a
    re-run resumes and completed batches are skipped; a re-run after full
    success is a no-op whose publisher report shows
    skipped_existing == published count (idempotency).

CONCURRENCY DECISION (documented per Task 2 contract): bounded concurrency
is deliberately NOT used. SQLite allows a single writer; the publisher
itself opens one connection per batch and commits transactionally.
Parallel writers would only produce lock contention and nondeterministic
batch ordering, so batches are enforced strictly sequential. The bounded
batch sizes (10 -> 25 -> 50 -> 100) remain the blast-radius limiter.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.app.catalog.acquisition.manifest import (
    VerifiedSKU,
    load_manifest,
)
from backend.app.catalog.acquisition.resolver import MATCHED
from backend.app.publishing.publisher import (
    PublicationResult,
    dry_run_batch,
    publish_batch,
)

# Bounded batch ladder (cumulative sizes per wave; Task 2 + pilot contract).
BATCH_SIZES = (10, 25, 50, 100)

_APPROVER = "m31-curator"

# The per-SKU citation corpus source name (registered in the target DB by
# run_acquisition if missing — same name the M3 pilot uses).
_SOURCE_NAME = "Official product pages — manual citations"
_SOURCE_URL = "https://vendor.example/ (per-record citation URL)"
_SOURCE_LICENSE = "site terms (no redistribution license published)"


def progress_path(manifest_path: str | Path) -> Path:
    """Checkpoint file location: ``{manifest_path}.progress.json``."""
    return Path(str(manifest_path) + ".progress.json")


def load_progress(manifest_path: str | Path) -> dict:
    """Load the checkpoint for a manifest (empty structure when absent)."""
    path = progress_path(manifest_path)
    if not path.exists():
        return {"completed_batches": [], "published_records": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("completed_batches", [])
    data.setdefault("published_records", [])
    return data


def _database_fingerprint(db_path: str | Path) -> dict:
    """Identify the data state a checkpoint was written against.

    Two cheap read-only signals: the set of canonical keys already in
    ``hardware`` and its row count. A fresh or different database yields a
    different fingerprint; a restored/wiped same-path database drifts in
    the key set. Either mismatch marks a checkpoint stale — publication
    must run, never silently skip.

    The fingerprint is deliberately content-based (NOT path-based): the
    same database reached at another path (a moved/rebuilt rehearsal) is
    still the same data state, and cumulative runs legitimately re-run the
    same manifest against a DB that has grown since the checkpoint was
    written. Path is recorded for operator diagnostics only.
    """
    path = Path(db_path)
    conn = sqlite3.connect(path)
    try:
        keys = [
            row[0]
            for row in conn.execute(
                "SELECT canonical_key FROM hardware "
                "WHERE canonical_key IS NOT NULL ORDER BY canonical_key"
            ).fetchall()
        ]
        rows = conn.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
    finally:
        conn.close()
    return {
        "path": str(path.resolve()).replace("\\", "/").casefold(),
        "hardware_rows": rows,
        "canonical_keys": keys,
    }


def _checkpoint_is_current(progress: dict, db_path: str | Path) -> bool:
    """True when the checkpoint may be trusted for THIS database.

    New checkpoints carry ``db_fingerprint`` (canonical-key set + hardware
    row count + path): the content components (key set + row count) must
    match the live database exactly. A fresh, different, or restored
    database mismatches — never silently skipped. The path is diagnostic
    only: the same data state at another location still resumes.

    Legacy checkpoints (no fingerprint — the pre-gate shape) are
    reconciled against the target database instead: trusted only when
    EVERY record they name still exists in ``hardware``. On the database
    they were written for, the named rows exist (crash recovery works);
    on a fresh database they do not (no silent skip). The publisher's
    canonical-key idempotency stays the second line of defense either way.
    """
    fingerprint = progress.get("db_fingerprint")
    if isinstance(fingerprint, dict):
        live = _database_fingerprint(db_path)
        return (
            fingerprint.get("canonical_keys") == live["canonical_keys"]
            and fingerprint.get("hardware_rows") == live["hardware_rows"]
        )

    named = progress.get("published_records") or []
    if not named:
        # Nothing named -> nothing the resume could skip; trusting it is
        # equivalent to starting fresh.
        return True
    conn = sqlite3.connect(db_path)
    try:
        found = 0
        for key in named:
            row = conn.execute(
                "SELECT 1 FROM hardware WHERE canonical_key = ?", (key,)
            ).fetchone()
            if row:
                found += 1
    finally:
        conn.close()
    return found == len(named)


def save_progress(manifest_path: str | Path, progress: dict) -> None:
    """Atomically persist the checkpoint (write temp, then replace)."""
    path = progress_path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(progress, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Dedup + conflict quarantine
# ---------------------------------------------------------------------------

def dedup_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group by canonical_key; duplicates go to conflict quarantine.

    Returns ``(unique_records, quarantine)``. Quarantine entries carry the
    key and ALL involved records — never merged, never published; a human
    must resolve and resubmit (same contract as the publisher's conflict
    gate).
    """
    by_key: dict[str, list[dict]] = {}
    for record in records:
        by_key.setdefault(record["canonical_key"], []).append(record)

    unique: list[dict] = []
    quarantine: list[dict] = []
    for key, group in by_key.items():
        if len(group) == 1:
            unique.append(group[0])
        else:
            quarantine.append({
                "canonical_key": key,
                "reason": (
                    f"{len(group)} records share canonical_key {key!r} with "
                    "differing facts; conflict quarantine — never "
                    "auto-merged"
                ),
                "records": group,
            })
    return unique, quarantine


# ---------------------------------------------------------------------------
# Manifest -> publisher record conversion
# ---------------------------------------------------------------------------

def _evidence_by_field(sku: VerifiedSKU) -> dict:
    return {e.spec_field: e for e in sku.fields}


def to_publisher_record(sku: VerifiedSKU) -> dict:
    """Convert a MATCHED VerifiedSKU into a ``pilot_seed._sku_record``-shaped
    publisher record dict.

    Shape (EXACT contract): category, name, manufacturer, product_family,
    identity_status='confirmed', record_status='APPROVED', approved_by,
    canonical_key, spec, provenance map (source_reference + match_method on
    every entry), mpn.
    """
    evidence = _evidence_by_field(sku)
    provenance: dict[str, dict] = {}
    for field_name, value in sku.spec.items():
        if value is None or value == "":
            continue  # NULL spec fields carry no provenance row
        ev = evidence.get(field_name)
        if ev is None or ev.curator_decision != "APPROVED":
            # Manifest validation already blocks this; fail-closed here too.
            raise ValueError(
                f"{sku.name!r}: field {field_name!r} lacks APPROVED evidence"
            )
        provenance[field_name] = {
            "source_name": _SOURCE_NAME,
            "source_url": ev.source_url or sku.per_sku_url,
            "license_name": _SOURCE_LICENSE,
            "evidence_status": "verified",
            "access_date": ev.access_date,
            "source_reference": ev.source_evidence_location,
            "match_method": ev.match_method,
        }
    return {
        "category": sku.category.upper(),
        "name": sku.name,
        "manufacturer": sku.manufacturer,
        "product_family": sku.product_family,
        "identity_status": "confirmed",
        "record_status": "APPROVED",
        "approved_by": sku.approved_by or _APPROVER,
        "canonical_key": canonical_key_for(sku),
        "spec": {k: v for k, v in sku.spec.items()
                 if v is not None and v != ""},
        "provenance": provenance,
        "mpn": sku.mpn,
    }


def canonical_key_for(sku: VerifiedSKU) -> str:
    """Deterministic canonical key for a verified SKU (identity rules reused)."""
    from backend.app.identity.canonical import canonical_key, variant_key

    category = sku.category.upper()
    return canonical_key(
        sku.manufacturer,
        category,
        sku.product_family,
        variant_key(category, sku.spec),
    )


# ---------------------------------------------------------------------------
# Bounded batches (cumulative deltas, mirroring pilot_seed.iter_batches)
# ---------------------------------------------------------------------------

def bounded_batches(records: list[dict], sizes=BATCH_SIZES):
    """Yield cumulative-delta batches: sizes 10 -> 25 -> 50 -> 100 (capped).

    Later waves chunk the remainder into fixed-size batches of the last
    ladder step so any record count is covered deterministically.
    """
    previous = 0
    for size in sizes:
        batch = records[previous:size]
        previous = size
        if batch:
            yield batch
    remainder = records[previous:]
    step = sizes[-1]
    for i in range(0, len(remainder), step):
        yield remainder[i:i + step]


def _ensure_source_registered(db_path: Path) -> None:
    """Register the citation-corpus source row if absent (idempotent).

    SELECT-first, not INSERT OR IGNORE: the sources table has NO unique
    constraint on name, so a blind INSERT OR IGNORE would add a second
    identical row when the DB already carries the source — and the
    publisher's fail-closed INSERT..SELECT rowcount check (must match
    exactly 1) would then abort every batch citing it.
    """
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM sources WHERE name = ?", (_SOURCE_NAME,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO sources (name, url, license_name, "
                "license_status) VALUES (?, ?, ?, ?)",
                (_SOURCE_NAME, _SOURCE_URL, _SOURCE_LICENSE, "unknown"),
            )
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_acquisition(
    manifest_path: str | Path,
    db_path: str | Path,
    mode: str = "apply",
) -> dict:
    """Run one acquisition cycle for a manifest (dry-run or apply).

    ``mode``: ``"dry-run"`` reports what would happen (writes nothing, no
    checkpoint mutation); ``"apply"`` publishes bounded batches with
    checkpointing. Returns a summary dict with counts, quarantine list and
    per-batch publisher results.
    """
    if mode not in ("apply", "dry-run"):
        raise ValueError(f"mode must be 'apply' or 'dry-run', got {mode!r}")

    manifest = load_manifest(manifest_path)
    db_path = Path(db_path)

    skus = [VerifiedSKU.from_dict(e) for e in manifest.get("verified_skus", [])]
    matched = [s for s in skus if s.classification == MATCHED]

    # Fail-closed: manifest validation (load_manifest) already enforced the
    # MATCHED contract; to_publisher_record double-checks per record.
    records = [to_publisher_record(s) for s in matched]

    # Dedup on canonical key BEFORE batching: duplicates never publish.
    unique_records, quarantine = dedup_records(records)

    progress = load_progress(manifest_path)
    done_batches = set(progress["completed_batches"])

    # Database-aware checkpoint validation (M3.2 final gate): a checkpoint
    # is only trusted when it was written for THIS database (path + hardware
    # row count). A fresh, different, or restored database mismatches — the
    # stale checkpoint is discarded and every batch runs. The publisher's
    # canonical-key idempotency keeps an honest same-DB rerun a no-op.
    checkpoint_discarded = False
    if done_batches and not _checkpoint_is_current(progress, db_path):
        progress = {"completed_batches": [], "published_records": []}
        done_batches = set()
        checkpoint_discarded = True

    batches = list(bounded_batches(unique_records))
    summary: dict = {
        "manifest_path": str(manifest_path),
        "mode": mode,
        "verified_skus": len(skus),
        "matched": len(matched),
        "unique_records": len(unique_records),
        "quarantined_conflicts": quarantine,
        "total_batches": len(batches),
        "batches": [],
        "published": 0,
        "skipped_existing": 0,
        "rejected": 0,
        "rejection_reasons": [],
    }
    if mode == "dry-run":
        results = [dry_run_batch(db_path, batch) for batch in batches]
        summary["batches"] = [_result_dict(i, r)
                              for i, r in enumerate(results)]
        summary["published"] = sum(r.would_publish for r in results)
        summary["skipped_existing"] = sum(r.skipped_existing for r in results)
        summary["rejected"] = sum(r.rejected for r in results)
        summary["rejection_reasons"] = [
            reason for r in results for reason in r.rejection_reasons
        ]
        return summary

    _ensure_source_registered(db_path)
    if checkpoint_discarded:
        # The stale checkpoint is dropped from the summary narrative too,
        # so operators see why a "resume" turned into a full run.
        summary["checkpoint_discarded"] = True
        save_progress(manifest_path, {
            "completed_batches": [],
            "published_records": [],
            "db_fingerprint": _database_fingerprint(db_path),
        })
    for i, batch in enumerate(batches):
        if i in done_batches:
            # Checkpoint resume: skip completed batches entirely (no write).
            # Idempotency proof: verify read-only that the batch's records
            # are still present and report them as skipped_existing, so a
            # fully-resumed run reports skipped_existing == published count
            # of the original run while touching no rows.
            summary["batches"].append(
                {"batch_no": i, "status": "skipped_completed"})
            summary["skipped_existing"] += _count_existing(
                db_path, batch)
            continue
        result = publish_batch(
            db_path, batch, approved_by=_APPROVER,
            run_notes=f"m31 acquisition {Path(manifest_path).name}",
        )
        summary["batches"].append(_result_dict(i, result))
        summary["published"] += result.published
        summary["skipped_existing"] += result.skipped_existing
        summary["rejected"] += result.rejected
        summary["rejection_reasons"] += result.rejection_reasons
        if result.published > 0 or not result.rejected:
            # Persist progress AFTER the batch committed (checkpoint =
            # committed state only; a rolled-back batch is never marked).
            # The fingerprint rides along so a later run against a fresh
            # or different database can tell the checkpoint is stale.
            progress["completed_batches"].append(i)
            progress["published_records"] += [
                r["canonical_key"] for r in batch
            ]
            progress["db_fingerprint"] = _database_fingerprint(db_path)
            save_progress(manifest_path, progress)
            done_batches.add(i)
    return summary


def _result_dict(batch_index: int, r: PublicationResult) -> dict:
    return {
        "batch_no": batch_index,
        "status": "ok",
        "published": r.published,
        "skipped_existing": r.skipped_existing,
        "rejected": r.rejected,
        "rejection_reasons": r.rejection_reasons,
    }


def _count_existing(db_path: Path, batch: list[dict]) -> int:
    """Read-only count of batch records already present in the DB.

    Used on checkpoint resume so a fully-resumed run reports
    skipped_existing == the original run's published count without any
    write I/O (SELECT only, transaction untouched).
    """
    conn = sqlite3.connect(db_path)
    try:
        existing = 0
        for record in batch:
            row = conn.execute(
                "SELECT 1 FROM hardware WHERE canonical_key = ?",
                (record["canonical_key"],),
            ).fetchone()
            if row is not None:
                existing += 1
        return existing
    finally:
        conn.close()
