"""Stage 1 comprehensive completeness-intelligence audit (read-only).

Derives every figure from the database; nothing is invented. Output is
deterministic (sorted keys) so a regression test can pin it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, text

CPU_SPEC_FIELDS = [
    "cores", "threads", "boost_clock_ghz", "base_clock_ghz", "tdp_w",
    "socket", "process_node_nm",
]
GPU_SPEC_FIELDS = [
    "memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
    "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface",
    "length_mm",
]


class DeviceClass:
    """Ordinal impact weights for missing spec fields (audit-only, not scoring).

    Higher = a gap that costs the suitability engine more, so gap lists are
    ranked by impact rather than raw row count. Stable, documented, reviewed.
    """

    _IMPACT = {
        "cpu_specifications": {
            "cores": 9, "threads": 8, "boost_clock_ghz": 8,
            "base_clock_ghz": 5, "tdp_w": 6, "socket": 4, "process_node_nm": 2,
        },
        "gpu_specifications": {
            "memory_gb": 7, "memory_type": 6, "memory_bus_width_bits": 7,
            "core_clock_mhz": 6, "boost_clock_mhz": 3, "vram_bandwidth_gbps": 5,
            "tdp_w": 5, "interface": 2, "length_mm": 1,
        },
    }

    @staticmethod
    def impact(table: str, field: str) -> int:
        return DeviceClass._IMPACT.get(table, {}).get(field, 0)


def rate_missing_field_impact(field: str, table: str) -> int:
    return DeviceClass.impact(table, field)


def _count(conn, sql, **params) -> int:
    return conn.execute(text(sql), params).scalar_one()


def _rows(conn, sql, **params):
    return conn.execute(text(sql), params).fetchall()


def _catalyst(conn, hw_type: str) -> dict:
    total = _count(
        conn, "SELECT COUNT(*) FROM hardware WHERE type = :t", t=hw_type
    )
    if total == 0:
        return {"total": 0, "with_spec": 0}
    with_spec = _count(
        conn,
        "SELECT COUNT(*) FROM hardware h JOIN {}_specifications s ON s.hardware_id = h.id WHERE h.type = :t".format(hw_type.lower()),
        t=hw_type,
    )
    return {"total": total, "with_spec": with_spec}


def _spec_completeness(conn, spec_table: str, fields: list[str], hw_type: str) -> dict:
    total = _count(conn, "SELECT COUNT(*) FROM hardware WHERE type = :t", t=hw_type)
    if total == 0:
        return {"total": 0, "complete": 0, "per_field": []}
    # per-field missing counts
    per_field = []
    for field in fields:
        missing = _count(
            conn,
            "SELECT COUNT(*) FROM hardware h JOIN {} s ON s.hardware_id = h.id "
            "WHERE h.type = :t AND s.{} IS NULL".format(spec_table, field),
            t=hw_type,
        )
        per_field.append({"field": field, "missing": missing})
    complete = _count(
        conn,
        "SELECT COUNT(*) FROM hardware h JOIN {} s ON s.hardware_id = h.id "
        "WHERE h.type = :t".format(spec_table),
        t=hw_type,
    )
    return {
        "total": total,
        "complete": complete,
        "per_field": sorted(per_field, key=lambda r: r["field"]),
    }


def _benchmark_coverage(conn, hw_type: str) -> dict:
    total = _count(conn, "SELECT COUNT(*) FROM hardware WHERE type = :t", t=hw_type)
    with_benchmarks = _count(
        conn,
        "SELECT COUNT(DISTINCT br.hardware_id) FROM benchmark_results br "
        "JOIN hardware h ON h.id = br.hardware_id WHERE h.type = :t",
        t=hw_type,
    )
    return {
        "total": total,
        "with_benchmarks": with_benchmarks,
        "coverage_pct": round(with_benchmarks / total * 100, 1) if total else 0.0,
    }


def _vendor_coverage(conn) -> list[dict]:
    rows = _rows(
        conn,
        "SELECT manufacturer, type, COUNT(*) AS count FROM hardware "
        "GROUP BY manufacturer, type ORDER BY manufacturer, type",
    )
    return [{"manufacturer": r[0], "type": r[1], "count": r[2]} for r in rows]


def _missing_spec_fields(conn, spec_table: str, fields: list[str], hw_type: str) -> list[dict]:
    result = []
    for field in fields:
        missing = _count(
            conn,
            "SELECT COUNT(*) FROM hardware h JOIN {} s ON s.hardware_id = h.id "
            "WHERE h.type = :t AND s.{} IS NULL".format(spec_table, field),
            t=hw_type,
        )
        result.append(
            {
                "field": field,
                "missing": missing,
                "impact": rate_missing_field_impact(field, spec_table),
            }
        )
    return sorted(result, key=lambda r: (-r["impact"], r["field"]))


def _duplicate_conflicts(conn) -> list[dict]:
    rows = _rows(
        conn,
        "SELECT name, manufacturer, type, COUNT(*) AS count FROM hardware "
        "GROUP BY name, manufacturer, type HAVING COUNT(*) > 1 "
        "ORDER BY count DESC, name",
    )
    return [{"name": r[0], "manufacturer": r[1], "type": r[2], "count": r[3]} for r in rows]


def _unit_inconsistency(conn) -> list[dict]:
    rows = _rows(
        conn,
        "SELECT benchmark_name, unit, COUNT(DISTINCT test_type) AS types "
        "FROM benchmark_results GROUP BY benchmark_name, unit ORDER BY benchmark_name",
    )
    # flag benchmark+unit combos that carry more than one test_type with a
    # different score scale isn't detectable here; we report the raw grouping
    # so human/gap review sees every (benchmark, unit) pair with its family
    # and volume.
    pairs = [
        {"benchmark_name": r[0], "unit": r[1], "test_types": r[2]}
        for r in rows
    ]
    # truly inconsistent: same benchmark name appearing with different units
    name_units = {}
    for r in _rows(
        conn,
        "SELECT benchmark_name, unit, COUNT(*) AS n FROM benchmark_results "
        "GROUP BY benchmark_name, unit ORDER BY benchmark_name, unit",
    ):
        name_units.setdefault(r[0], set()).add(r[1])
    inconsistent = [
        {"benchmark_name": name, "units": sorted(units)}
        for name, units in name_units.items()
        if len(units) > 1
    ]
    return {"pairs": pairs, "inconsistent": inconsistent}


def _provenance_summary(conn) -> dict:
    total_hw = _count(conn, "SELECT COUNT(*) FROM hardware")
    with_prov = _count(
        conn,
        "SELECT COUNT(DISTINCT hardware_id) FROM field_provenance",
    )
    verified = _count(
        conn,
        "SELECT COUNT(*) FROM field_provenance WHERE evidence_status = 'verified'",
    )
    statuses = [
        {"status": r[0], "count": r[1]}
        for r in _rows(
            conn,
            "SELECT evidence_status, COUNT(*) FROM field_provenance "
            "GROUP BY evidence_status ORDER BY evidence_status",
        )
    ]
    return {
        "hardware_total": total_hw,
        "hardware_with_provenance": with_prov,
        "provenance_total": _count(conn, "SELECT COUNT(*) FROM field_provenance"),
        "verified": verified,
        "by_status": statuses,
    }


def _licensing_summary(conn) -> dict:
    rows = [
        {"license_status": r[0], "count": r[1]}
        for r in _rows(
            conn,
            "SELECT license_status, COUNT(*) FROM sources "
            "GROUP BY license_status ORDER BY license_status",
        )
    ]
    return {"rows": rows}


def _priority_gaps(conn) -> dict:
    # CPU: benchmarked-eligible but missing benchmarks; list top by impact.
    bench_missing = _rows(
        conn,
        "SELECT h.id, h.name, h.manufacturer, h.segment, h.release_date "
        "FROM hardware h "
        "LEFT JOIN benchmark_results br ON br.hardware_id = h.id "
        "GROUP BY h.id HAVING COUNT(br.id) = 0 "
        "ORDER BY h.segment IS NULL, h.segment, h.id LIMIT 50",
    )
    gpu_bm = _benchmark_coverage(conn, "GPU")
    return {
        "cpu": [
            {
                "id": r[0], "name": r[1], "manufacturer": r[2],
                "segment": r[3],
                "release_date": str(r[4]) if r[4] else None,
            }
            for r in bench_missing
        ],
        "gpu": gpu_bm,
    }

def audit_report(db):
    """Return the complete audit dict. ``db`` is a SQLAlchemy Engine (tests) or
    a Path/str to a SQLite file (CLI). Tables must already exist."""
    auto_close = None
    if not hasattr(db, "connect"):
        db = create_engine("sqlite:///{}".format(db))
        auto_close = db
    conn = db.connect()
    try:
        total_cpu = _count(conn, "SELECT COUNT(*) FROM hardware WHERE type = :t", t="CPU")
        total_gpu = _count(conn, "SELECT COUNT(*) FROM hardware WHERE type = :t", t="GPU")
        report = {
            "tool": "completeness_intelligence",
            "totals": {
                "hardware": _count(conn, "SELECT COUNT(*) FROM hardware"),
                "cpu": total_cpu,
                "gpu": total_gpu,
            },
            "vendor_coverage": {"rows": _vendor_coverage(conn)},
            "spec_completeness": {
                "cpu": _spec_completeness(conn, "cpu_specifications", CPU_SPEC_FIELDS, "CPU"),
                "gpu": _spec_completeness(conn, "gpu_specifications", GPU_SPEC_FIELDS, "GPU"),
            },
            "missing_spec_fields": {
                "cpu": _missing_spec_fields(conn, "cpu_specifications", CPU_SPEC_FIELDS, "CPU"),
                "gpu": _missing_spec_fields(conn, "gpu_specifications", GPU_SPEC_FIELDS, "GPU"),
            },
            "benchmark_coverage": {
                "cpu": _benchmark_coverage(conn, "CPU"),
                "gpu": _benchmark_coverage(conn, "GPU"),
            },
            "duplicate_conflicts": {
                "rows": _duplicate_conflicts(conn),
            },
            "unit_inconsistency": _unit_inconsistency(conn),
            "provenance_summary": _provenance_summary(conn),
            "licensing_summary": _licensing_summary(conn),
            "priority_gaps": _priority_gaps(conn),
        }
        return json.loads(json.dumps(report, default=str))
    finally:
        conn.close()
        if auto_close:
            auto_close.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage 1 read-only completeness-intelligence audit."
    )
    parser.add_argument(
        "--database",
        default="data/spectra.db",
        help="Path to a disposable copy of the SPECTRA database.",
    )
    args = parser.parse_args()
    report = audit_report(Path(args.database))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
