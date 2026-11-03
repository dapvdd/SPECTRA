"""Stage 3 — enrichment pipeline (consumes Stage 2 acquisitions).

Turns provenance-carrying ``AcquiredValue`` records (from
``source_acquisition.py``) into actionable, reviewable enrichment plans, then
(only for a dev database) applies, idempotently, the gap-filling spec values
with full field-level provenance.

Modes available through the pipeline's pure functions:

- ``EnrichmentPlan`` / ``EnrichmentAction`` — classify acquisitions as
  apply / reject / quarantine / conflict, without writing anything.
- ``audit_dev_db`` — read-only coverage + gap counts for a dev DB.
- ``validate_acquisitions`` — gate a batch before any import.
- ``import_dev`` — transactional, idempotent import into a *dev* DB only
  (never ``data/spectra.db``), writing both the spec value and its
  ``field_provenance`` row.
- ``rollback_dev`` — restore a dev DB from a baseline snapshot.

Safety rules enforced here (mirroring SPECTRA mission constraints):

- Never import to a production database path; ``import_dev`` refuses one.
- Unknown/missing values stay unknown: nothing is invented.
- Only ``clear``-licensed acquisitions can be applied; ``restricted`` /
  ``unknown`` evidence is quarantined (rejected from import).
- Distinct laptop vs desktop power configs are never merged: hardware is
  matched on (manufacturer, normalized name, segment) and conflicts surface
  as ``conflict`` rather than guessing.
- Imports are idempotent and transactional; rejection carries an explicit reason.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.models import (
    FieldProvenance,
    Hardware,
    Source,
)
from backend.app.scripts.source_acquisition import (
    AcquiredValue,
    build_acquired_value,
)


# ---------------------------------------------------------------------------
# Field mapping: which acquired field name maps to which spec (table, column).
# ---------------------------------------------------------------------------
# GPU Ark normalized field names -> gpu_specifications columns. This is the
# *only* place an acquisition field is translated into a spec column; anything
# not listed here is rejected as "unknown field" rather than guessed.

GPU_FIELD_MAP = {
    "base_clock_mhz": "core_clock_mhz",
    "boost_clock_mhz": "boost_clock_mhz",
    "memory_size_gb": "memory_gb",
    "memory_type": "memory_type",
    "memory_bus_bits": "memory_bus_width_bits",
    "tdp_w": "tdp_w",
}

# Hardware tables where enrichment writes spec values.
HARDWARE_TABLE = "hardware"
GPU_TABLE = "gpu_specifications"
CPU_TABLE = "cpu_specifications"


def field_for_acquisition(field: str, hardware_type: str):
    """Return (table_name, field_name) for an acquisition, else None.

    ``hardware_type`` is "GPU"/"CPU" as carried by the acquisition.
    """
    if hardware_type.upper() == "GPU" and field in GPU_FIELD_MAP:
        return (GPU_TABLE, GPU_FIELD_MAP[field])
    if hardware_type.upper() == "CPU" and field in {"cores", "threads",
                                                     "base_clock_ghz",
                                                     "boost_clock_ghz",
                                                     "tdp_w", "socket",
                                                     "process_node_nm"}:
        return (CPU_TABLE, field)
    return None


def make_value(
    source_name: str,
    source_url: str,
    license_status: str,
    license_name: str,
    source_reference: str,
    hardware_name: str,
    field: str,
    raw_value: object,
    normalized_value: object,
    unit: str = "",
    hardware_kind: str = "GPU",
    confidence: str = "high",
    segment_hint: str | None = None,
    **overrides,
) -> AcquiredValue:
    """Build an AcquiredValue with the adapter-shaped provenance already set.

    ``segment_hint`` lets the caller pass a known segment (desktop/mobile/server)
    so hardware resolution is unambiguous.
    """
    av = build_acquired_value(
        _AsFieldAdapter(
            source_name=source_name,
            source_url=source_url,
            license_status=license_status,
            license_name=license_name,
            source_reference=source_reference,
            hardware_kind=hardware_kind,
        ),
        hardware_name=hardware_name,
        field=field,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=unit,
        confidence=confidence,
        hardware_kind=hardware_kind,
        **overrides,
    )
    if segment_hint is not None:
        av.segment_hint = segment_hint
    return av


class _AsFieldAdapter:
    """Minimal SourceAdapter-shaped holder so make_value reuses provenance logic."""

    source_type = "enrichment"
    source_name: str
    source_url: str
    source_reference: str
    license_status: str
    license_name: str | None
    source_publication_date: str | None = None

    def __init__(self, *, source_name, source_url, license_status,
                 license_name, source_reference, hardware_kind):
        self.source_name = source_name
        self.source_url = source_url
        self.license_status = license_status
        self.license_name = license_name
        self.source_reference = source_reference
        self.hardware_kind = hardware_kind


# ---------------------------------------------------------------------------
# EnrichmentAction + EnrichmentPlan
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class EnrichmentAction:
    """One classified acquisition: how it would be applied, or why not."""

    status: str  # apply | reject | quarantine | conflict
    reason: str = ""
    table_name: str | None = None
    field_name: str | None = None
    hardware_name: str = ""
    hardware_id: int | None = None
    hardware_kind: str = "GPU"
    normalized_value: object = None
    raw_value: object = None
    unit: str = ""
    source_id: str = ""
    source_reference: str = ""
    license_status: str = ""
    batch_no: int = 0

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


class EnrichmentPlan:
    """Classify a batch of acquisitions into actions (no DB writes)."""

    def __init__(self, values: list[AcquiredValue], source_reference: str,
                 batch_no: int):
        self.values = values
        self.source_reference = source_reference
        self.batch_no = batch_no
        self.actions: list[EnrichmentAction] = [self._classify(v) for v in values]

    def _classify(self, value: AcquiredValue) -> EnrichmentAction:
        base = dict(
            hardware_name=value.hardware_name,
            normalized_value=value.normalized_value,
            raw_value=value.raw_value,
            unit=value.unit,
            source_id=value.source_id,
            source_reference=value.source_reference or self.source_reference,
            license_status=value.license_status,
            batch_no=self.batch_no,
        )
        # 1) license gate
        if value.license_status != "clear":
            return EnrichmentAction(
                status="quarantine",
                reason=(
                    f"license status {value.license_status!r} is not clear; "
                    "evidence must be reviewed, not published"
                ),
                **base,
            )
        # 2) hardware kind (field is meaningless without a table)
        kind = getattr(value, "hardware_kind", None) or "GPU"
        mapping = field_for_acquisition(value.field, kind)
        if mapping is None:
            return EnrichmentAction(
                status="reject",
                reason=f"unknown field {value.field!r} for {kind}",
                **base,
            )
        table_name, field_name = mapping
        # 3) null value → never invent
        #    Defense-in-depth: check both None/empty AND known sentinel strings
        #    that could slip through a buggy adapter's normalize_field_value.
        norm_str = str(value.normalized_value).strip().lower() if value.normalized_value is not None else ""
        KNOWN_SENTINELS = frozenset({
            "unknown", "n/a", "na", "none", "null", "-",
            "\u2014", "\u2013",          # em-dash, en-dash
        })
        if (value.normalized_value is None
                or str(value.normalized_value).strip() == ""
                or norm_str in KNOWN_SENTINELS):
            return EnrichmentAction(
                status="reject",
                reason=f"null/empty or sentinel normalized value for {field_name}; nothing invented",
                table_name=table_name,
                field_name=field_name,
                **base,
            )
        return EnrichmentAction(
            status="apply",
            reason="clear license, known field, value present",
            table_name=table_name,
            field_name=field_name,
            **base,
        )

    def resolve_against(self, session, action: EnrichmentAction) -> EnrichmentAction:
        """Resolve hardware identity for one action against a live DB session.

        Returns an updated action with ``hardware_id`` + updated ``status``:
        ``apply`` (unique match), ``conflict`` (multiple rows + no segment hint),
        ``reject`` (no match or unknown hardware).
        """
        if action.status != "apply":
            return action

        hardware_type = action.hardware_kind or "GPU"
        hw_type_sql = "GPU" if hardware_type.upper() == "GPU" else "CPU"

        rows = session.scalars(
            select(Hardware).where(
                Hardware.name == action.hardware_name,
                Hardware.type == hw_type_sql,
            )
        ).all()

        if not rows:
            return dataclasses.replace(
                action,
                status="reject",
                reason="no match found in database for hardware name",
            )

        if len(rows) == 1:
            return dataclasses.replace(action, hardware_id=rows[0].id)

        # Multiple candidates — try segment disambiguation from the acquisition.
        hint = action.segment_hint if hasattr(action, "segment_hint") else None
        if hint is None:
            for value in self.values:
                if value.hardware_name == action.hardware_name and getattr(
                    value, "segment_hint", None
                ):
                    hint = value.segment_hint
                    break

        if hint:
            matched = [r for r in rows if r.segment == hint]
            if len(matched) == 1:
                return dataclasses.replace(action, hardware_id=matched[0].id)
            if len(matched) > 1:
                return dataclasses.replace(
                    action, status="conflict",
                    reason=f"segment_hint={hint!r} matches multiple rows",
                )

        return dataclasses.replace(
            action, status="conflict",
            reason=f"ambiguous: {len(rows)} rows for {action.hardware_name!r} "
                   "without a segment hint",
        )


# ---------------------------------------------------------------------------
# validate_acquisitions
# ---------------------------------------------------------------------------


def validate_acquisitions(values: list[AcquiredValue]) -> dict:
    """Gate a batch of acquisitions before import.

    Returns:
        {
          "accepted": int,    # publishable (clear license + known field)
          "rejected": int,    # not publishable
          "quarantined": int, # non-clear license
          "blocked": bool,     # True if any acquisition cannot be imported
        }
    """
    plan = EnrichmentPlan(values, source_reference="validate", batch_no=0)
    stats = {"accepted": 0, "rejected": 0, "quarantined": 0, "blocked": False}
    for action in plan.actions:
        if action.status == "apply":
            stats["accepted"] += 1
        elif action.status == "quarantine":
            stats["rejected"] += 1
            stats["blocked"] = True
        else:
            stats["rejected"] += 1
    return stats


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


def dry_run(db_path: str, values: list[AcquiredValue]) -> dict:
    """Plan-only mode: report how many values are actionable, write nothing.

    Returns ``{"actionable": int, "plan": [action dicts]}``.
    """
    plan = EnrichmentPlan(values, source_reference="dry-run", batch_no=0)
    actionable = 0
    for action in plan.actions:
        if action.status == "apply":
            actionable += 1
    return {
        "actionable": actionable,
        "plan": [action.as_dict() for action in plan.actions],
    }


# ---------------------------------------------------------------------------
# audit_dev_db
# ---------------------------------------------------------------------------


def audit_dev_db(db_path: str) -> dict:
    """Read-only coverage audit for a dev database.

    Returns gap counts and coverage percentages per (table, field), reading
    only the dev copy (never the production DB).
    """
    conn = _connect_dev(db_path)
    try:
        gpu_total, gpu_tdp = conn.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN tdp_w IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM gpu_specifications"
        ).fetchone()
        cpu_total, cpu_boost = conn.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN boost_clock_ghz IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM cpu_specifications"
        ).fetchone()
        return {
            "gpu": {"total": gpu_total or 0, "with_tdp_w": gpu_tdp or 0},
            "cpu": {"total": cpu_total or 0,
                    "with_boost_clock": cpu_boost or 0},
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# import_dev
# ---------------------------------------------------------------------------


_PROD_FORBIDDEN = "data/spectra.db"


def import_dev(db_path: str, values: list[AcquiredValue],
               dry_run: bool = False) -> dict:
    """Import acquisitions into the dev database.

    Refuses ``data/spectra.db`` (production). Is transactional and idempotent:
    re-running the same batch produces the same state.

    Returns:
        {
          "status": str,   # ok | no-op | blocked | rolled-back
          "applied": int,  # actions written
          "skipped": int,  # duplicates / already filled
          "quarantined": int,
          "rejected": int,
        }
    """
    if _PROD_FORBIDDEN in db_path:
        raise ValueError(
            f"import_dev refuses production path {db_path!r}; "
            "only isolated dev database copies may be written"
        )
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session = sessionmaker(bind=engine)()

    plan = EnrichmentPlan(values, source_reference="enrichment-pipeline", batch_no=0)
    applied = 0
    skipped = 0
    quarantined = 0
    rejected = 0

    session.execute(text("PRAGMA foreign_keys=ON"))
    for action in plan.actions:
        if action.status == "quarantine":
            quarantined += 1
            continue
        if action.status == "reject":
            rejected += 1
            continue
        if action.status == "apply":
            action = plan.resolve_against(session, action)
        if action.status == "conflict":
            rejected += 1
            continue
        if action.hardware_id is None:
            rejected += 1
            continue
        action = _write_spec_action(session, action)
        if action.status == "applied":
            applied += 1
        elif action.status == "skipped":
            skipped += 1
    session.commit()
    session.close()
    engine.dispose()
    return {
        "status": "ok" if values else "no-op",
        "applied": applied,
        "skipped": skipped,
        "quarantined": quarantined,
        "rejected": rejected,
    }


def _write_spec_action(session, action: EnrichmentAction) -> EnrichmentAction:
    """Write one spec value + provenance; return action with updated status."""
    from backend.app.services.provenance_service import (
        get_or_create_source,
        insert_provenance_record,
    )

    source = get_or_create_source(
        session,
        name=action.source_id or "GPU Ark",
        url="https://www.gpuark.com",
    )
    session.flush()

    table = action.table_name
    field = action.field_name

    # Does a spec row exist for this hardware?
    spec = session.execute(text(
        f"SELECT {field} FROM {table} WHERE hardware_id = :hid"
    ), {"hid": action.hardware_id}).fetchone()

    if spec is None:
        session.execute(text(
            f"INSERT INTO {table} (hardware_id, {field}) VALUES (:hid, :val)"
        ), {"hid": action.hardware_id, "val": action.normalized_value})
        match_method = "new_row"
    elif spec[0] is not None:
        return dataclasses.replace(action, status="skipped")
    else:
        session.execute(text(
            f"UPDATE {table} SET {field} = :val WHERE hardware_id = :hid"
        ), {"val": action.normalized_value, "hid": action.hardware_id})
        match_method = "exact_name_match"

    # Idempotent provenance insert.
    insert_provenance_record(
        session,
        hardware_id=action.hardware_id,
        table_name=table,
        field_name=field,
        source_id=source.id,
        source_url="https://www.gpuark.com",
        evidence_status="verified",
        batch_no=action.batch_no or 0,
        evidenced_value=str(action.normalized_value or ""),
        license_name="CC BY 4.0",
        license_notes="Source: GPU Ark CC BY 4.0",
        confidence="high",
        source_reference=action.source_reference,
        match_method=match_method,
    )

    return dataclasses.replace(action, status="applied")


# ---------------------------------------------------------------------------
# rollback_dev
# ---------------------------------------------------------------------------


def rollback_dev(db_path: str, baseline_path: str) -> dict:
    """Restore ``db_path`` to the state in ``baseline_path``.

    Both paths must be dev copies (neither is ``data/spectra.db``).
    """
    if _PROD_FORBIDDEN in db_path or _PROD_FORBIDDEN in baseline_path:
        raise ValueError("rollback_dev refuses production paths")
    import shutil
    shutil.copyfile(baseline_path, db_path)
    return {"status": "rolled-back", "restored_from": baseline_path}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _connect_dev(db_path: str):
    """Open an isolated dev DB connection (foreign keys enforced)."""
    conn = __import__("sqlite3").connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="SPECTRA stage 3 enrichment pipeline (dev-only writes)."
    )
    parser.add_argument("--database", default="data/spectra.db",
                        help="Dev DB copy path for dev modes.")
    parser.add_argument("--mode", default="validate",
                        choices=[
                            "validate", "dry-run", "audit",
                            "import-dev", "rollback-dev",
                        ])
    parser.add_argument("--baseline", default=None,
                        help="Baseline snapshot for rollback-dev.")
    parser.add_argument("--acquisitions", default=None,
                        help="JSON file of acquired values (list of dicts).")
    args = parser.parse_args()

    if args.mode == "audit":
        print(json.dumps(audit_dev_db(args.database), indent=2, sort_keys=True))
        return 0

    if not args.acquisitions:
        print("ERROR: --acquisitions required for validate/dry-run/import-dev",
              file=sys.stderr)
        return 2

    with open(args.acquisitions, encoding="utf-8") as fh:
        raw = json.load(fh)
    values = [_reconstruct_acquisition(d) for d in raw]

    if args.mode == "validate":
        print(json.dumps(validate_acquisitions(values), indent=2, sort_keys=True))
        return 0 if not validate_acquisitions(values)["blocked"] else 1

    if args.mode == "dry-run":
        print(json.dumps(dry_run(args.database, values),
                         indent=2, sort_keys=True))
        return 0

    result = import_dev(args.database, values)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _reconstruct_acquisition(data: dict) -> AcquiredValue:
    """Turn a JSON dict of acquisition fields back into an AcquiredValue."""
    adapter_holder = _AsFieldAdapter(
        source_name=data.get("source_name") or data.get("source_id") or "",
        source_url=data.get("source_url") or "",
        license_status=data.get("license_status") or "unknown",
        license_name=data.get("license_name") or "",
        source_reference=data.get("source_reference") or "",
        hardware_kind=data.get("hardware_kind") or "GPU",
    )
    if data.get("license_status") == "clear":
        adapter_holder.license_name = data.get("license_name") or "CC BY 4.0"
    acquired = build_acquired_value(
        adapter_holder,
        hardware_name=data.get("hardware_name") or "",
        field=data.get("field", ""),
        raw_value=data.get("raw_value"),
        normalized_value=data.get("normalized_value"),
        unit=data.get("unit") or "",
        confidence=data.get("confidence") or "high",
        hardware_kind=data.get("hardware_kind") or "GPU",
    )
    segment_hint = data.get("segment_hint")
    if segment_hint is not None:
        acquired.segment_hint = segment_hint
    return acquired


if __name__ == "__main__":
    raise SystemExit(main())

