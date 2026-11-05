"""Read-only database completeness audit for the SPECTRA hardware catalog.

Produces a reproducible, deterministic JSON snapshot of catalog completeness:
spec coverage, benchmark coverage, evidence tiers, and high-priority gaps —
all derived from the database, nothing invented.

Run against a disposable copy::

    python backend/app/scripts/completeness_audit.py --database data/spectra_copy.db

Exit 0. Output is sorted for stable diffing.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _spec_completeness(cur: sqlite3.Cursor, hw_type: str) -> dict:
    """Fraction of rows with a spec row and with all key spec fields non-null."""
    # All hardware of this type
    total = cur.execute(
        "SELECT COUNT(*) FROM hardware WHERE type = ?", (hw_type,)
    ).fetchone()[0]

    if total == 0:
        return {"total": 0, "with_spec": 0, "complete_spec": 0, "complete_pct": 0.0}

    with_spec = cur.execute(
        """
        SELECT COUNT(*)
        FROM hardware h
        JOIN {}_specifications s ON s.hardware_id = h.id
        WHERE h.type = ?
        """.format(hw_type.lower()),
        (hw_type,),
    ).fetchone()[0]

    if hw_type == "CPU":
        complete = cur.execute(
            """
            SELECT COUNT(*)
            FROM hardware h
            JOIN cpu_specifications c ON c.hardware_id = h.id
            WHERE h.type = ?
              AND c.cores IS NOT NULL
              AND c.threads IS NOT NULL
              AND c.base_clock_ghz IS NOT NULL
              AND c.socket IS NOT NULL
              AND c.tdp_w IS NOT NULL
            """,
            (hw_type,),
        ).fetchone()[0]
        key_fields = ["cores", "threads", "base_clock_ghz", "socket", "tdp_w"]
    else:  # GPU
        complete = cur.execute(
            """
            SELECT COUNT(*)
            FROM hardware h
            JOIN gpu_specifications g ON g.hardware_id = h.id
            WHERE h.type = ?
              AND g.memory_gb IS NOT NULL
              AND g.memory_type IS NOT NULL
              AND g.core_clock_mhz IS NOT NULL
              AND g.memory_bus_width_bits IS NOT NULL
              AND g.tdp_w IS NOT NULL
            """,
            (hw_type,),
        ).fetchone()[0]
        key_fields = [
            "memory_gb", "memory_type", "core_clock_mhz",
            "memory_bus_width_bits", "tdp_w",
        ]

    return {
        "total": total,
        "with_spec": with_spec,
        "complete_spec": complete,
        "complete_pct": round(complete / total * 100, 1),
        "key_fields": key_fields,
    }


def _benchmark_coverage(cur: sqlite3.Cursor, hw_type: str) -> dict:
    total = cur.execute(
        "SELECT COUNT(*) FROM hardware WHERE type = ?", (hw_type,)
    ).fetchone()[0]
    with_benchmarks = cur.execute(
        """
        SELECT COUNT(DISTINCT hardware_id)
        FROM benchmark_results br
        JOIN hardware h ON h.id = br.hardware_id
        WHERE h.type = ?
        """,
        (hw_type,),
    ).fetchone()[0]
    return {
        "total": total,
        "with_benchmarks": with_benchmarks,
        "coverage_pct": round(with_benchmarks / total * 100, 1) if total > 0 else 0.0,
    }


def _benchmark_distribution(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT benchmark_name, unit, test_type, COUNT(*) AS count
        FROM benchmark_results
        GROUP BY benchmark_name, unit, test_type
        ORDER BY count DESC
        """
    ).fetchall()
    return [
        {"benchmark_name": r[0], "unit": r[1], "test_type": r[2], "count": r[3]}
        for r in rows
    ]


def _no_evidence_tier(cur: sqlite3.Cursor) -> dict:
    """Hardware rows with no spec row AND no field_provenance at all."""
    rows = cur.execute(
        """
        SELECT h.id, h.name, h.type, h.manufacturer
        FROM hardware h
        LEFT JOIN cpu_specifications c ON c.hardware_id = h.id
        LEFT JOIN gpu_specifications g ON g.hardware_id = h.id
        LEFT JOIN field_provenance fp ON fp.hardware_id = h.id
        LEFT JOIN benchmark_results br ON br.hardware_id = h.id
        WHERE h.type = 'CPU'
          AND c.id IS NULL
          AND g.id IS NULL
          AND (SELECT COUNT(*) FROM field_provenance fp2 WHERE fp2.hardware_id = h.id) = 0
          AND (SELECT COUNT(*) FROM benchmark_results br2 WHERE br2.hardware_id = h.id) = 0
        ORDER BY h.id
        """
    ).fetchall()
    gpu_rows = cur.execute(
        """
        SELECT h.id, h.name, h.type, h.manufacturer
        FROM hardware h
        LEFT JOIN cpu_specifications c ON c.hardware_id = h.id
        LEFT JOIN gpu_specifications g ON g.hardware_id = h.id
        LEFT JOIN field_provenance fp ON fp.hardware_id = h.id
        LEFT JOIN benchmark_results br ON br.hardware_id = h.id
        WHERE h.type = 'GPU'
          AND c.id IS NULL
          AND g.id IS NULL
          AND (SELECT COUNT(*) FROM field_provenance fp2 WHERE fp2.hardware_id = h.id) = 0
          AND (SELECT COUNT(*) FROM benchmark_results br2 WHERE br2.hardware_id = h.id) = 0
        ORDER BY h.id
        """
    ).fetchall()
    return {
        "cpu_count": len(rows),
        "gpu_count": len(gpu_rows),
        "cpu_rows": [{"id": r[0], "name": r[1], "manufacturer": r[3]} for r in rows[:20]],
        "gpu_rows": [{"id": r[0], "name": r[1], "manufacturer": r[3]} for r in gpu_rows[:20]],
    }


def _segment_benchmark_coverage(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT
            h.segment,
            COUNT(*) AS total,
            SUM(CASE WHEN
                (SELECT COUNT(*) FROM benchmark_results br2 WHERE br2.hardware_id = h.id) > 0
                THEN 1 ELSE 0 END) AS benchmarked
        FROM hardware h
        WHERE h.type = 'CPU' AND h.segment IS NOT NULL
        GROUP BY h.segment
        ORDER BY total DESC
        """
    ).fetchall()
    return [
        {
            "segment": r[0],
            "total": r[1],
            "with_benchmarks": r[2],
            "pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0.0,
        }
        for r in rows
    ]


def _priority_gaps(cur: sqlite3.Cursor) -> list[dict]:
    """CPU hardware with specs present but no benchmarks, ordered by segment relevance."""
    rows = cur.execute(
        """
        SELECT h.id, h.name, h.manufacturer, h.segment, h.release_date
        FROM hardware h
        JOIN cpu_specifications c ON c.hardware_id = h.id
        WHERE h.type = 'CPU'
          AND (SELECT COUNT(*) FROM benchmark_results br WHERE br.hardware_id = h.id) = 0
        ORDER BY
            CASE
                WHEN h.segment IN ('Enthusiast Desktop', 'Extreme Performance',
                                   'Premium Mobile', 'High Performance') THEN 1
                WHEN h.segment IN ('Mainstream Desktop', 'Performance Mobile',
                                   'Standard Mobile') THEN 2
                ELSE 3
            END,
            h.id DESC
        LIMIT 30
        """
    ).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "manufacturer": r[2],
            "segment": r[3], "release_date": str(r[4]) if r[4] else None,
        }
        for r in rows
    ]


def _source_summary(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT s.id, s.name, s.url,
               s.license_name, s.license_status,
               COUNT(fp.id) AS provenance_records,
               COUNT(DISTINCT fp.hardware_id) AS hardware_covered,
               COUNT(DISTINCT br.id) AS benchmark_records
        FROM sources s
        LEFT JOIN field_provenance fp ON fp.source_id = s.id
        LEFT JOIN benchmark_results br ON br.source_id = s.id
        GROUP BY s.id
        ORDER BY s.id
        """
    ).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "url": r[2],
            "license_name": r[3], "license_status": r[4],
            "provenance_records": r[5],
            "hardware_covered": r[6],
            "benchmark_records": r[7],
        }
        for r in rows
    ]


def run_audit(db_path: Path) -> dict:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()

        total_hw = cur.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
        total_cpu = cur.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='CPU'"
        ).fetchone()[0]
        total_gpu = cur.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='GPU'"
        ).fetchone()[0]

        return {
            "tool": "completeness_audit",
            "database": str(db_path),
            "totals": {
                "hardware": total_hw,
                "cpu": total_cpu,
                "gpu": total_gpu,
            },
            "spec_completeness": {
                "cpu": _spec_completeness(cur, "CPU"),
                "gpu": _spec_completeness(cur, "GPU"),
            },
            "benchmark_coverage": {
                "cpu": _benchmark_coverage(cur, "CPU"),
                "gpu": _benchmark_coverage(cur, "GPU"),
            },
            "benchmark_distribution": _benchmark_distribution(cur),
            "no_evidence_tier": _no_evidence_tier(cur),
            "segment_benchmark_coverage": _segment_benchmark_coverage(cur),
            "priority_gaps": _priority_gaps(cur),
            "source_summary": _source_summary(cur),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only SPECTRA catalog completeness audit."
    )
    parser.add_argument(
        "--database",
        default="data/spectra.db",
        help="Path to a disposable copy of the SPECTRA database.",
    )
    args = parser.parse_args()

    report = run_audit(Path(args.database))
    # Deterministic output
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
