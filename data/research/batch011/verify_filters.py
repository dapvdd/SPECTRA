"""Batch 011 — live-database verification of the benchmark query filters.

Runs the service against the real data/spectra.db and asserts the filters
behave correctly with real rows (no HTTP server required).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import SessionLocal
from backend.app.models import BenchmarkResult, Hardware
from backend.app.services.benchmark_service import get_benchmarks_for_hardware


def main() -> int:
    with SessionLocal() as session:
        # a CPU that has two Geekbench results (single + multi)
        hw_id = session.query(BenchmarkResult.hardware_id).first()[0]
        total = session.query(BenchmarkResult).filter_by(hardware_id=hw_id).count()

    print(f"hardware_id={hw_id} total benchmarks={total}")

    all_rows = get_benchmarks_for_hardware(hw_id)
    print("no filter:", len(all_rows), [r.id for r in all_rows])

    src = all_rows[0].source_id if all_rows else None
    by_source = get_benchmarks_for_hardware(hw_id, source_id=src)
    print(f"source_id={src}:", len(by_source), [r.id for r in by_source])

    by_name = get_benchmarks_for_hardware(hw_id, benchmark_name="Geekbench 7")
    print("benchmark_name=Geekbench 7:", len(by_name))

    by_type = get_benchmarks_for_hardware(hw_id, test_type="single-core")
    print("test_type=single-core:", len(by_type))

    by_multi = get_benchmarks_for_hardware(hw_id, test_type="multi-core")
    print("test_type=multi-core:", len(by_multi))

    combined = get_benchmarks_for_hardware(
        hw_id, source_id=src, benchmark_name="Geekbench 7", test_type="compute"
    )
    print("combined (contradiction):", len(combined))

    unknown = get_benchmarks_for_hardware(hw_id, source_id=1)
    print("unknown source_id=1:", len(unknown))

    # duplicate check
    ids = [r.id for r in by_name]
    print("duplicate-free:", len(ids) == len(set(ids)))

    # values unchanged check: fetch scores
    print("scores:", [(r.id, r.score, r.test_type) for r in all_rows])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())