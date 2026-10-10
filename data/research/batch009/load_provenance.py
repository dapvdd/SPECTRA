"""Load reconstructed base-import provenance into ``field_provenance``.

Batch 009 Phase C: persist the reconciled base-import provenance records
described in ``evidence_reconciliation.csv`` using the existing
``provenance_service`` and schema. Only cells whose stored value reconciles
exactly to ONE documented base-import dataset (``verified``) and that are
persistable (hardware/cpu_specifications/gpu_specifications fields) are
loaded. Uncertain (multi-source) and unmatched cells are left in the
reconciliation artifacts.

Safety guarantees:

- Read-only on hardware values: no specification, benchmark, identifier or
  build row is modified.
- Guarded, idempotent inserts via ``insert_provenance_record``; re-running
  produces the same row set.
- Existing verified provenance is preserved and overlapping cells are
  skipped.
- New provenance carries license metadata that records the unresolved or
  restricted reuse status of every base-import source.

Run from the repository root (after computing the reconciliation CSV):

    python data/research/batch009/evidence.py
    python data/research/batch009/load_provenance.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.services.provenance_service import (  # noqa: E402
    get_or_create_source,
    insert_provenance_record,
)

BATCH_DIR = REPO_ROOT / "data" / "research" / "batch009"
RECONCILIATION_CSV = BATCH_DIR / "evidence_reconciliation.csv"

# Dataset id -> (registered source name, landing URL, license notes).
SOURCE_REGISTRY = {
    "intel": (
        "Intel ARK (intel-cpus.csv snapshot)",
        "https://ark.intel.com/",
        "Intel ARK content snapshot (intel-cpus.csv) distributed via "
        "felixsteinke/cpu-spec-dataset (repository licence AGPL-3.0 applies "
        "to the code; the dataset CSVs carry no separate data licence). No "
        "data reuse or redistribution grant is documented. Redistribution "
        "status unresolved.",
    ),
    "amd": (
        "AMD product specifications (amd-cpus.csv snapshot)",
        "https://www.amd.com/en/products/specifications/processors",
        "AMD processor specification snapshot (amd-cpus.csv) exported from "
        "amd.com product specification pages (felixsteinke/cpu-spec-dataset). "
        "No data reuse or redistribution grant is documented. Redistribution "
        "status unresolved.",
    ),
    "passmark": (
        "PassMark CPU benchmark catalog (benchmark-cpus.csv)",
        "https://www.cpubenchmark.net/",
        "PassMark website terms permit reproduction of material in unaltered "
        "form only for personal, non-commercial use or use within an "
        "organisation; reproduction for general publication or commercial "
        "purposes requires PassMark permission. No redistribution licence.",
    ),
    "techpowerup": (
        "TechPowerUp GPU Database (gpu_1986-2026.csv)",
        "https://www.techpowerup.com/gpu-specs/",
        "TechPowerUp robots.txt restricts use to personal, non-commercial "
        "purposes and prohibits data mining, dataset creation and commercial "
        "use without prior written permission. These records document source "
        "identity only and grant no redistribution rights.",
    ),
}

MATCH_METHOD = "exact normalized base-import value reconcile (unique source dataset)"
BATCH_NO = 0  # base import / original ingestion, no enrichment batch


def main() -> int:
    with open(RECONCILIATION_CSV, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    candidates = [
        row for row in rows
        if row["status"] == "verified"
        and row["persistable"] == "True"
        and row["already_covered_verified"] != "True"
    ]
    print(f"reconciliation rows: {len(rows)}")
    print(f"verified persistable candidates (not already covered): {len(candidates)}")

    inserted = skipped = 0
    by_dataset = {}
    with SessionLocal() as session:
        source_ids = {
            dataset: get_or_create_source(session, name, url).id
            for dataset, (name, url, _notes) in SOURCE_REGISTRY.items()
        }

        for row in candidates:
            dataset = row["dataset"]
            if dataset not in source_ids:
                skipped += 1
                continue
            source_id = source_ids[dataset]
            _, created = insert_provenance_record(
                session,
                hardware_id=int(row["entity_id"]),
                table_name=row["table"],
                field_name=row["field"],
                source_id=source_id,
                source_url=SOURCE_REGISTRY[dataset][1],
                evidence_status="verified",
                batch_no=BATCH_NO,
                evidenced_value=str(row["db_value"]),
                license_name=None,
                license_notes=SOURCE_REGISTRY[dataset][2],
                attribution=None,
                access_date=None,
                confidence=row["confidence"],
                source_reference=row["source_reference"],
                match_method=MATCH_METHOD,
                notes=(
                    "Batch 009 base-import provenance reconstruction. "
                    "Source artifact hashes recorded in "
                    "provenance_reconciliation.json. Hardware value unchanged."
                ),
            )
            by_dataset[dataset] = by_dataset.get(dataset, 0) + (1 if created else 0)
            if created:
                inserted += 1
            else:
                skipped += 1

        session.commit()

    print(f"inserted: {inserted}")
    print(f"skipped (already present / rejected): {skipped}")
    print(f"by dataset: {by_dataset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())