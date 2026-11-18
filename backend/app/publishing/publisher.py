"""M3 Phase 4 — transactional, idempotent, fail-closed batch publication.

Implements the mission §6 Phase 4 contract on top of migration v4's
``publication_batches`` / ``ingestion_runs`` and the Phase 1/3/4 identity +
lifecycle + validation modules.

Guarantees (tested):
- Deterministic dry-run: reports would_publish / provenance plan, writes nothing.
- Lifecycle gate: only APPROVED records can be published (anything else is
  rejected with the reason recorded).
- Validation gate: every record passes ``validate_record`` fail-closed checks
  before insertion (bad records never half-publish; per-record savepoints).
- Idempotency: re-publishing the same batch (same canonical keys) is a no-op
  reporting skipped_existing; provenance is never duplicated.
- Transactional: the batch commits once; a failure rolls the whole batch back
  (records are staged then committed together).
- Audit: every run writes an ``ingestion_runs`` row and every publication
  writes a ``publication_batches`` row with the explicit approver identity.

Production safety: refuses paths ending in the production database name
(``data/spectra.db``), mirroring enrichment_pipeline.import_dev.
"""
from __future__ import annotations

import dataclasses
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.app.identity.lifecycle import APPROVED, PUBLISHED
from backend.app.importers.m3_validation import detect_conflicts, validate_record
from backend.app.migrations.runner import _current_version

_PROD_FORBIDDEN = "data/spectra.db"


def _is_prod_path(path: Path) -> bool:
    """True when the path points at the production-named database.

    Case-insensitive and separator-normalized: on Windows/macOS the
    filesystem is case-insensitive, so ``DATA/SPECTRA.DB`` opens the same
    file as ``data/spectra.db`` — the refusal must match both.
    """
    return (
        str(path).replace("\\", "/").casefold().endswith(_PROD_FORBIDDEN)
    )


def _check_db_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    if _is_prod_path(path):
        raise ValueError(
            f"publisher refuses production path {str(path)!r}; "
            "publication targets isolated dev databases only"
        )

_CATEGORY_TABLES = {
    "RAM": "ram_specifications",
    "STORAGE": "storage_specifications",
    "MOTHERBOARD": "motherboard_specifications",
    "PSU": "psu_specifications",
}

_LIFECYCLE_STAGES = (
    "DISCOVERED", "EXTRACTED", "NORMALIZED", "VALIDATED", "APPROVED",
)


@dataclass
class PublicationResult:
    published: int = 0
    rejected: int = 0
    skipped_existing: int = 0
    batch_no: int = 0
    run_id: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    # dry-run only:
    would_publish: int = 0
    provenance_rows_planned: int = 0


def _check_db_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    if _is_prod_path(path):
        raise ValueError(
            f"publisher refuses production path {str(path)!r}; "
            "publication targets isolated dev databases only"
        )
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path


def _next_batch_no(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(batch_no), 0) FROM publication_batches"
    ).fetchone()
    return int(row[0]) + 1


def _hardware_id_by_canonical_key(
    conn: sqlite3.Connection, canonical_key: str
) -> int | None:
    row = conn.execute(
        "SELECT id FROM hardware WHERE canonical_key = ?", (canonical_key,)
    ).fetchone()
    return row[0] if row else None


def _published_spec_by_key(
    conn: sqlite3.Connection, canonical_key: str, table: str
) -> dict:
    """Read an already-published record's spec values for conflict checks."""
    hardware_id = _hardware_id_by_canonical_key(conn, canonical_key)
    if hardware_id is None:
        return {}
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    spec_columns = [c for c in columns if c != "hardware_id"]
    if not spec_columns:
        return {}
    row = conn.execute(
        f"SELECT {', '.join(spec_columns)} FROM {table} "
        "WHERE hardware_id = ?",
        (hardware_id,),
    ).fetchone()
    return dict(zip(spec_columns, row))


def _conflict_message(
    incoming: dict, other_source: str, field_name: str
) -> str:
    return (
        f"{incoming.get('name', '?')}: unresolved source conflict on "
        f"'{field_name}' with {other_source!r}; same canonical_key with "
        "differing facts is never auto-merged — resolve and resubmit"
    )


def _norm_spec(spec: dict) -> dict:
    """Normalize a spec dict for conflict comparison.

    Bools become ints (SQLite stores True as 1 and reads it back as an
    int, so an incoming ``True`` must compare equal to a published ``1``)
    and NULL values are dropped (absent counts as absent on both sides).
    """
    return {
        key: int(value) if isinstance(value, bool) else value
        for key, value in spec.items()
        if value is not None
    }


def _apply_conflict_gate(
    conn: sqlite3.Connection,
    staged: list[dict],
) -> tuple[list[dict], list[str]]:
    """Reject ALL records involved in an intra-batch conflict (fail-closed).

    Two staged records with the same canonical_key but differing fact
    values are a source conflict (R2): never auto-merged, never published —
    both are rejected with a named reason. (Conflict against an
    already-published record is handled earlier, in the staging loop, so a
    differing-value re-import is a rejection rather than a silent skip.)
    """
    by_key: dict[str, list[dict]] = {}
    for record in staged:
        by_key.setdefault(record["canonical_key"], []).append(record)

    rejected_keys: set[str] = set()
    reasons: list[str] = []
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        conflicts = detect_conflicts(
            [
                {**_norm_spec(record.get("spec", {})),
                 "canonical_key": key,
                 "_type": str(record.get("category", "")).upper(),
                 "source_name": str(record.get("approved_by") or "batch")}
                for record in group
            ]
        )
        if conflicts:
            rejected_keys.add(key)
            # One named reason per involved record: the result must account
            # for EVERY rejected record, not just one per conflict group.
            for record in group:
                reasons.append(_conflict_message(
                    record, group[1].get("name", "?") if record is group[0]
                    else group[0].get("name", "?"),
                    conflicts[0].field,
                ))

    surviving: list[dict] = [
        record for record in staged
        if record["canonical_key"] not in rejected_keys
    ]
    return surviving, reasons


def _validate_lifecycle(record: dict) -> str | None:
    """Return a rejection reason when the record is not publishable."""
    status = record.get("record_status")
    if status != APPROVED:
        return (
            f"record_status is {status!r}; only {APPROVED} records may be "
            "published (no unreviewed publication)"
        )
    if not str(record.get("approved_by") or "").strip():
        return "record carries no approver identity"
    if not str(record.get("canonical_key") or "").strip():
        return "record has no canonical_key (valid identity required)"
    return None


def _insert_record(
    conn: sqlite3.Connection,
    record: dict,
    batch_no: int,
) -> None:
    """Insert one approved record + spec row + provenance rows."""
    category = str(record["category"]).upper()
    table = _CATEGORY_TABLES[category]
    spec: dict = record.get("spec", {})
    provenance: dict = record.get("provenance", {})

    cursor = conn.execute(
        "INSERT INTO hardware (name, manufacturer, type, canonical_key, "
        "product_family, identity_status, record_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            record["name"],
            record["manufacturer"],
            category,
            record["canonical_key"],
            record.get("product_family"),
            record.get("identity_status", "confirmed"),
            PUBLISHED,
        ),
    )
    hardware_id = cursor.lastrowid

    spec_columns = list(spec.keys())
    if spec_columns:
        col_list = ", ".join(["hardware_id", *spec_columns])
        placeholders = ", ".join(["?"] * (len(spec_columns) + 1))
        conn.execute(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
            (hardware_id, *[spec[c] for c in spec_columns]),
        )

    for field_name in spec_columns:
        prov = provenance.get(field_name)
        if not prov:
            # A populated spec field without provenance is a contract
            # violation (fail-closed): abort the batch.
            raise ValueError(
                f"record {record['name']!r}: field '{field_name}' has no "
                "provenance; refusing to publish unattributed values"
            )
        cursor = conn.execute(
            "INSERT INTO field_provenance (hardware_id, source_id, table_name, "
            "field_name, evidenced_value, source_url, license_name, "
            "evidence_status, access_date, match_method, batch_no, recorded_at) "
            "SELECT ?, id, ?, ?, ?, ?, ?, ?, ?, 'batch-publication', ?, ? "
            "FROM sources WHERE name = ?",
            (
                hardware_id,
                table,
                field_name,
                str(spec[field_name]),
                prov["source_url"],
                prov.get("license_name"),
                prov.get("evidence_status", "verified"),
                prov.get("access_date"),
                batch_no,
                datetime.now(timezone.utc).isoformat(),
                prov["source_name"],
            ),
        )
        if cursor.rowcount != 1:
            # Fail-closed (R1): INSERT..SELECT matched no source row. A
            # silently-skipped provenance insert would publish a spec value
            # with NO provenance — the exact contract violation the
            # rowcount check prevents. Abort the batch; the transaction
            # rollback removes everything this record wrote.
            raise ValueError(
                f"record {record['name']!r}: field '{field_name}' cites "
                f"unregistered source {prov['source_name']!r}; refusing to "
                "publish values whose source is not in the registry"
            )


def publish_batch(
    db_path: str | Path,
    records: list[dict],
    *,
    approved_by: str,
    run_notes: str = "",
) -> PublicationResult:
    """Publish a batch of APPROVED records (transactional, idempotent)."""
    path = _check_db_path(db_path)
    conn = sqlite3.connect(path, isolation_level=None)  # explicit tx control
    result = PublicationResult()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        started_at = datetime.now(timezone.utc).isoformat()

        cursor = conn.execute(
            "INSERT INTO ingestion_runs (run_type, category, mode, status, "
            "rows_seen, started_at, notes) VALUES ('publication', 'ALL', "
            "'apply', 'running', ?, ?, ?)",
            (len(records), started_at, run_notes),
        )
        result.run_id = cursor.lastrowid
        batch_no = _next_batch_no(conn)
        result.batch_no = batch_no

        staged: list[dict] = []
        for record in records:
            reason = _validate_lifecycle(record)
            if reason is None:
                outcome = validate_record(
                    record["category"].upper(),
                    {**record.get("spec", {}), "name": record["name"],
                     "manufacturer": record["manufacturer"]},
                    conflict_free=True,
                    identity_confirmed=record.get("identity_status", "confirmed")
                    == "confirmed",
                    # Evidence gate (M3 remediation): the publisher is the
                    # last fail-closed gate — a record claiming
                    # evidence_status='verified' without an MPN or per-SKU
                    # URL is rejected here, never published.
                    provenance=record.get("provenance"),
                )
                if not outcome.passed:
                    reason = "; ".join(outcome.blockers)
            if reason is not None:
                result.rejected += 1
                result.rejection_reasons.append(
                    f"{record.get('name', '?')}: {reason}"
                )
                continue

            existing_id = _hardware_id_by_canonical_key(
                conn, record["canonical_key"]
            )
            if existing_id is not None:
                # Same canonical_key as a published row: identical values are
                # an idempotent re-import (skipped_existing); differing fact
                # values are a source conflict — the incoming record is
                # rejected and the published row is untouched (R2: conflicts
                # are never auto-merged, and skip-existing must not hide a
                # conflict behind an identical key).
                table = _CATEGORY_TABLES[str(record["category"]).upper()]
                published_spec = _published_spec_by_key(
                    conn, record["canonical_key"], table
                )
                conflicts = (
                    detect_conflicts(
                        [
                            {**_norm_spec(record.get("spec", {})),
                             "canonical_key": record["canonical_key"],
                             "_type": str(record["category"]).upper(),
                             "source_name": "incoming"},
                            {**_norm_spec(published_spec),
                             "canonical_key": record["canonical_key"],
                             "_type": str(record["category"]).upper(),
                             "source_name": "published"},
                        ]
                    )
                    if published_spec
                    else []
                )
                if conflicts:
                    result.rejected += 1
                    result.rejection_reasons.append(_conflict_message(
                        record, "the published record", conflicts[0].field,
                    ))
                else:
                    result.skipped_existing += 1
                continue
            staged.append(record)

        # Conflict gate (R2/mission §6): the same canonical_key with
        # differing fact values is a conflict — never auto-merged and never
        # published. Intra-batch conflicts reject ALL involved records;
        # a conflict against an already-published record rejects the
        # incoming one. detect_conflicts compares spec fields only.
        staged, conflict_reasons = _apply_conflict_gate(conn, staged)
        result.rejected += len(conflict_reasons)
        result.rejection_reasons += conflict_reasons

        # Transactional batch: stage everything, commit once.
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO publication_batches (batch_no, category, "
                "record_count, approved_by, status, created_at) "
                "VALUES (?, 'ALL', ?, ?, 'prepared', ?)",
                (batch_no, len(staged), approved_by,
                 datetime.now(timezone.utc).isoformat()),
            )
            for record in staged:
                _insert_record(conn, record, batch_no)
            conn.execute(
                "UPDATE publication_batches SET status='published', "
                "published_at=? WHERE batch_no=?",
                (datetime.now(timezone.utc).isoformat(), batch_no),
            )
            conn.execute(
                "UPDATE ingestion_runs SET status='success', finished_at=?, "
                "rows_applied=?, rows_rejected=?, rows_quarantined=0 "
                "WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), len(staged),
                 result.rejected, result.run_id),
            )
            result.published = len(staged)
            conn.commit()
        except BaseException:
            conn.rollback()
            conn.execute(
                "UPDATE ingestion_runs SET status='rolled_back', finished_at=? "
                "WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), result.run_id),
            )
            raise
        return result
    finally:
        conn.close()


def _unregistered_sources(
    conn: sqlite3.Connection, record: dict
) -> list[str]:
    """Cited source names missing from the registry for this record."""
    cited = {
        prov.get("source_name")
        for prov in (record.get("provenance") or {}).values()
        if isinstance(prov, dict)
    }
    if not cited:
        return []
    placeholders = ", ".join("?" for _ in cited)
    rows = conn.execute(
        f"SELECT name FROM sources WHERE name IN ({placeholders})",
        tuple(cited),
    ).fetchall()
    known = {row[0] for row in rows}
    return sorted(name for name in cited if name and name not in known)


def dry_run_batch(
    db_path: str | Path, records: list[dict]
) -> PublicationResult:
    """Deterministic dry-run: report what would happen; write nothing."""
    path = _check_db_path(db_path)
    conn = sqlite3.connect(path)
    result = PublicationResult()
    try:
        result.would_publish = 0
        result.provenance_rows_planned = 0
        for record in records:
            reason = _validate_lifecycle(record)
            if reason is not None:
                result.rejected += 1
                result.rejection_reasons.append(
                    f"{record.get('name', '?')}: {reason}"
                )
                continue
            # Mirror apply-time fail-closed: cite an unregistered source and
            # the record WILL be rejected at publish — dry-run must say so
            # (never overstate success).
            unregistered = _unregistered_sources(conn, record)
            if unregistered:
                result.rejected += 1
                result.rejection_reasons.append(
                    f"{record.get('name', '?')}: cites unregistered source "
                    f"{unregistered[0]!r}"
                )
                continue
            # Mirror the evidence gate too (M3 remediation): a record claiming
            # evidence_status='verified' without an MPN/per-SKU URL WILL be
            # rejected at publish — dry-run must not overstate success.
            outcome = validate_record(
                record["category"].upper(),
                {**record.get("spec", {}), "name": record["name"],
                 "manufacturer": record["manufacturer"]},
                conflict_free=True,
                identity_confirmed=record.get("identity_status", "confirmed")
                == "confirmed",
                provenance=record.get("provenance"),
            )
            if not outcome.passed:
                result.rejected += 1
                result.rejection_reasons.append(
                    f"{record.get('name', '?')}: {'; '.join(outcome.blockers)}"
                )
                continue
            if _hardware_id_by_canonical_key(conn, record["canonical_key"]):
                result.skipped_existing += 1
                continue
            result.would_publish += 1
            result.provenance_rows_planned += len(record.get("spec", {}))
        return result
    finally:
        conn.close()
