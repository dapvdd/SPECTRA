"""Load reconciled provenance evidence into the ``field_provenance`` table.

Batch 008 Phase B: persist field-level provenance reconstructed from the
committed research artifacts of batches 001-006 and reconciled against the
live database.

Safety guarantees:

- Read-only reconciliation: no hardware specification value is modified.
- Additive changes only: creates the ``field_provenance`` table and registers
  new ``sources`` rows when missing; ``sources`` already present are reused.
- Idempotent: re-running produces the same row set (unique constraint on the
  table identity deduplicates).
- Seeds documented licence/attribution metadata from the research artifacts.

Run from the repository root:

    python data/research/batch008/load_provenance.py
"""

from __future__ import annotations

import sys
import sqlite3
from datetime import date as date_type
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.migrations.add_field_provenance import (  # noqa: E402
    create_field_provenance,
)
from backend.app.services.provenance_service import (  # noqa: E402
    get_or_create_source,
    insert_provenance_record,
)
from data.research.batch008 import evidence as evidence_module  # noqa: E402

# Canonical source identity: ("registered name", "landing URL"). Reusing the
# existing registered TechPowerUp / PassMark / Geekbench rows and adding new
# rows only for sources the enrichment evidence actually cites.
SOURCE_REGISTRY = {
    "GPU Ark": ("GPU Ark GPU specifications & benchmarks dataset",
                "https://gpuark.com/datasets/"),
    "Wikipedia": ("Wikipedia (English)", "https://en.wikipedia.org/"),
    "Intel ARK": ("Intel ARK (archived via Wayback Machine)",
                  "https://ark.intel.com/"),
    "TechPowerUp GPU Database": (
        "TechPowerUp GPU Database (gpu_1986-2026.csv)",
        "https://www.techpowerup.com/gpu-specs/",
    ),
    "PassMark": ("PassMark CPU benchmark catalog (benchmark-cpus.csv)",
                 "https://www.cpubenchmark.net/"),
    "Geekbench": ("Geekbench Browser - Geekbench 7 CPU",
                  "https://browser.geekbench.com/"),
    "Unknown (deliberately excluded)": (
        "Unknown (source not documented in artifact)",
        "",
    ),
}

STATUS_MAP = {
    "verified": "verified",
    "uncertain_not_present": "uncertain",
    "uncertain_value_differs": "uncertain",
    "excluded": "excluded",
    "unmatched": "unmatched",
    "invalid_reference": None,
}


def parse_access_date(value: str | None) -> date_type | None:
    if not value:
        return None
    try:
        return date_type.fromisoformat(value)
    except ValueError:
        return None


def register_sources(session) -> dict:
    name_to_id = {}
    for canonical, (registered_name, url) in SOURCE_REGISTRY.items():
        source_row = get_or_create_source(session, registered_name, url)
        name_to_id[canonical] = source_row.id
    return name_to_id


def main() -> int:
    connection = sqlite3.connect(evidence_module.DATA_DIR / "spectra.db")

    records = evidence_module.extract_all()
    reconciled = evidence_module.reconcile(records, connection)
    connection.close()

    create_field_provenance()

    inserted = 0
    skipped = 0
    invalid = 0
    by_status: dict[str, int] = {}

    with SessionLocal() as session:
        source_ids = register_sources(session)

        for record in reconciled:
            status = STATUS_MAP.get(record["reconciled_status"])
            if status is None:
                invalid += 1
                continue

            canonical = record["canonical_source"]
            source_id = source_ids.get(canonical)
            if source_id is None:
                invalid += 1
                continue

            _, created = insert_provenance_record(
                session,
                hardware_id=record["hardware_id"],
                table_name=record["table_name"],
                field_name=record["field_name"],
                source_id=source_id,
                source_url=record.get("source_url") or "",
                evidence_status=status,
                batch_no=int(record["batch"]),
                evidenced_value=record.get("evidenced_value") or "",
                license_name=record.get("license_name"),
                license_notes=record.get("license_notes"),
                attribution=record.get("attribution"),
                access_date=parse_access_date(record.get("access_date")),
                confidence=record.get("confidence"),
                source_reference=record.get("source_reference"),
                match_method=record.get("match_method"),
                notes=record.get("notes"),
            )
            by_status[status] = by_status.get(status, 0) + 1
            if created:
                inserted += 1
            else:
                skipped += 1

        session.commit()

    print(f"records reconciled: {len(reconciled)}")
    print(f"inserted: {inserted}")
    print(f"skipped (already present): {skipped}")
    print(f"rejected (invalid reference/source): {invalid}")
    print(f"by evidence status: {by_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())