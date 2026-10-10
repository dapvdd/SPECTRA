"""Backfill benchmark provenance from the Batch 009 reconciliation artifacts.

Batch 009 reconciled every Geekbench 7 benchmark record to a unique row of
``processor-benchmarks.csv`` but could not persist that provenance because the
schema restricted ``field_provenance`` to hardware specification fields. After
the Batch 010 schema upgrade, benchmark provenance can reference an exact
``benchmark_results`` record via ``benchmark_result_id``.

Backfill rules:

- Only evidence rows with status ``verified`` in
  ``data/research/batch009/evidence_reconciliation.csv`` (dataset
  ``geekbench``) are considered.
- Each CSV row is matched to a ``benchmark_results`` row by
  ``(hardware_id, score)``; the match must be unique (verified for the current
  dataset) or the row is skipped and counted.
- Inserts go through ``insert_provenance_record`` which is idempotent and
  validated; re-running the backfill produces no duplicates and never touches
  benchmark values.

Run from the repository root after the schema upgrade:

    python -m backend.app.migrations.add_field_provenance
    python data/research/batch010/load_benchmark_provenance.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models import BenchmarkResult  # noqa: E402
from backend.app.services.provenance_service import (  # noqa: E402
    get_or_create_source,
    insert_provenance_record,
)

BATCH009_CSV = REPO_ROOT / "data" / "research" / "batch009" / "evidence_reconciliation.csv"

GEEKBENCH_SOURCE_NAME = "Geekbench Browser - Geekbench 7 CPU"
GEEKBENCH_SOURCE_URL = "https://browser.geekbench.com/"

LICENSE_NOTES = (
    "Geekbench Browser catalog (processor-benchmarks.csv). Primate Labs "
    "terms could not be verified from automated access (403/404 on "
    "2026-10-10); redistribution rights unknown. This record documents source "
    "identity only and grants no redistribution rights."
)

BATCH_NO = 0
MATCH_METHOD = "Geekbench devices/id + exact score reconcile (batch 009)"


def main() -> int:
    with open(BATCH009_CSV, newline="", encoding="utf-8") as file:
        rows = [r for r in csv.DictReader(file)
                if r["dataset"] == "geekbench"
                and r["table"] == "benchmark_results"
                and r["status"] == "verified"]

    inserted = 0
    skipped = 0
    skipped_missing = 0
    skipped_ambiguous = 0

    with SessionLocal() as session:
        source = get_or_create_source(session, GEEKBENCH_SOURCE_NAME, GEEKBENCH_SOURCE_URL)

        for row in rows:
            hardware_id = int(row["entity_id"])
            try:
                score = float(row["db_value"])
            except (TypeError, ValueError):
                skipped += 1
                continue

            matches = session.scalars(
                select(BenchmarkResult).where(
                    BenchmarkResult.hardware_id == hardware_id,
                    BenchmarkResult.score == score,
                )
            ).all()

            if len(matches) != 1:
                if len(matches) == 0:
                    skipped_missing += 1
                else:
                    skipped_ambiguous += 1
                skipped += 1
                continue

            benchmark = matches[0]
            _, created = insert_provenance_record(
                session,
                hardware_id=benchmark.hardware_id,
                benchmark_result_id=benchmark.id,
                table_name="benchmark_results",
                field_name="score",
                source_id=source.id,
                source_url=GEEKBENCH_SOURCE_URL,
                evidence_status="verified",
                batch_no=BATCH_NO,
                evidenced_value=str(score),
                license_name=None,
                license_notes=LICENSE_NOTES,
                attribution=None,
                access_date=None,
                confidence=row["confidence"],
                source_reference=(
                    f"processor-benchmarks.csv#devices/id={row['source_reference']}"
                ),
                match_method=MATCH_METHOD,
                notes=(
                    f"Batch 010 backfill from batch 009 reconciliation. "
                    f"test_type={benchmark.test_type}; benchmark value unchanged."
                ),
            )
            if created:
                inserted += 1
            else:
                skipped += 1

        session.commit()

    print(f"geekbench evidence rows: {len(rows)}")
    print(f"inserted: {inserted}")
    print(f"skipped (already present): {skipped - skipped_missing - skipped_ambiguous}")
    print(f"skipped missing benchmark row: {skipped_missing}")
    print(f"skipped ambiguous benchmark row: {skipped_ambiguous}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())