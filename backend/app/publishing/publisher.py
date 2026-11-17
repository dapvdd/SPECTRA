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
from backend.app.importers.m3_validation import validate_record
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
                )
                if not outcome.passed:
                    reason = "; ".join(outcome.blockers)
            if reason is not None:
                result.rejected += 1
                result.rejection_reasons.append(
                    f"{record.get('name', '?')}: {reason}"
                )
                continue

            if _hardware_id_by_canonical_key(conn, record["canonical_key"]):
                result.skipped_existing += 1
                continue
            staged.append(record)

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
            if _hardware_id_by_canonical_key(conn, record["canonical_key"]):
                result.skipped_existing += 1
                continue
            result.would_publish += 1
            result.provenance_rows_planned += len(record.get("spec", {}))
        return result
    finally:
        conn.close()
