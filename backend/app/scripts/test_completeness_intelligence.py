"""Tests for the Stage 1 comprehensive completeness-intelligence audit.

The audit is read-only and derives every figure from a SQLite database. These
tests seed an in-memory DB using the real SQLAlchemy schema, insert known rows,
and pin the audit's outputs: coverage, gaps, duplicates, unit inconsistency,
provenance and licensing summaries, and prioritised gap lists.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

from backend.app.database import Base
import backend.app.models  # noqa: F401  (register all tables on Base)
from backend.app.scripts.completeness_intelligence import (
    DeviceClass,
    audit_report,
    rate_missing_field_impact,
)


def _engine():
    return sa.create_engine("sqlite://")


def _seed(engine, rows: dict[str, list[tuple]]) -> None:
    """Insert raw rows by table name from a lightweight dict-of-tuples DSL."""
    with engine.begin() as conn:
        for table, tuples in rows.items():
            meta = Base.metadata.tables[table]
            conn.execute(meta.insert(), [dict(zip(tuple(meta.columns.keys())[1:], t)) for t in tuples])


def test_audit_reports_vendor_and_type_coverage():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "hardware": [
                ("Intel Core i5-12600K", "Intel", "CPU", None, None, None),
                ("Intel Core i7-13700K", "Intel", "CPU", None, None, None),
                ("AMD Ryzen 7 7700X", "AMD", "CPU", None, None, None),
                ("NVIDIA GeForce RTX 4070", "NVIDIA", "GPU", None, None, None),
            ]
        },
    )
    report = audit_report(Path(":memory:") if False else engine)
    assert report["totals"]["hardware"] == 4
    assert report["totals"]["cpu"] == 3
    assert report["totals"]["gpu"] == 1
    vendors = {v["manufacturer"] for v in report["vendor_coverage"]["rows"]}
    assert vendors == {"Intel", "AMD", "NVIDIA"}


def test_audit_reports_missing_spec_field_counts():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "hardware": [("AMD Ryzen 5 5600X", "AMD", "CPU", None, None, None)],
            "cpu_specifications": [
                (1, 6, 12, 3.7, None, 65.0, None, "AM4")
            ],
        },
    )
    report = audit_report(engine)
    cpu_fields = {f["field"]: f for f in report["missing_spec_fields"]["cpu"]}
    assert cpu_fields["boost_clock_ghz"]["missing"] == 1
    assert cpu_fields["cores"]["missing"] == 0


def test_audit_flags_duplicate_name_manufacturer_conflicts():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "hardware": [
                ("GeForce RTX 3060", "NVIDIA", "GPU", None, None, None),
                ("GeForce RTX 3060", "NVIDIA", "GPU", None, None, None),
                ("GeForce RTX 3060 Ti", "NVIDIA", "GPU", None, None, None),
                ("Radeon RX 6800", "AMD", "GPU", None, None, None),
            ]
        },
    )
    report = audit_report(engine)
    dup = report["duplicate_conflicts"]["rows"]
    assert len(dup) == 1
    assert dup[0]["name"] == "GeForce RTX 3060"
    assert dup[0]["count"] == 2


def test_audit_detects_inconsistent_benchmark_units():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "hardware": [
                ("AMD Ryzen 9 7900X", "AMD", "CPU", None, None, None),
                ("Intel Core i9-13900K", "Intel", "CPU", None, None, None),
            ],
            "benchmark_results": [
                (1, "Geekbench 7", 20000.0, "points", "multi-core", None),
                (1, "Geekbench 7", 2200.0, "points", "single-core", None),
                (2, "Geekbench 7", 15000.0, "points", "multi-core", None),
                (2, "Cinebench", 30000.0, "cb", "multi-core", None),
            ],
        },
    )
    report = audit_report(engine)
    units = report["unit_inconsistency"]["pairs"]
    assert any(u["benchmark_name"] == "Cinebench" for u in units)


def test_audit_reports_provenance_and_licensing():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "sources": [
                ("GPU Ark", "https://gpu.ark.example", None, None, "CC BY 4.0",
                 "https://creativecommons.org/licenses/by/4.0/", "clear",
                 None, None, None, None),
                ("PassMark", "https://cpubenchmark.example", None, None, None,
                 None, "restricted", None, None, None, None),
                ("Intel ARK", "https://ark.intel.example", None, None, None,
                 None, "unknown", None, None, None, None),
            ],
            "hardware": [
                ("Radeon RX 6800 XT", "AMD", "GPU", None, None, None),
                ("Core i5-12400", "Intel", "CPU", None, None, None),
            ],
            "field_provenance": [
                # hardware_id, source_id, table_name, field_name, evidenced_value,
                # source_url, license_name, license_notes, attribution, access_date,
                # confidence, evidence_status, source_reference, match_method,
                # batch_no, notes, recorded_at, benchmark_result_id
                (1, 1, "gpu_specifications", "memory_gb", "16",
                 "https://gpu.ark.example/6800", "CC BY 4.0", None, None, None,
                 "high", "verified", None, "exact", 1, None,
                 datetime(2026, 11, 1), None),
            ],
        },
    )
    report = audit_report(engine)
    assert report["provenance_summary"]["hardware_with_provenance"] == 1
    licensing = {r["license_status"]: r for r in report["licensing_summary"]["rows"]}
    assert licensing["clear"]["count"] == 1
    assert licensing["restricted"]["count"] == 1


def test_audit_prioritises_high_impact_missing_benchmarks():
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed(
        engine,
        {
            "hardware": [
                ("AMD Ryzen 7 7800X3D", "AMD", "CPU", None, "Zen 4", "gaming"),
                ("Intel Core i5-12400", "Intel", "CPU", None, "Alder Lake", None),
            ]
        },
    )
    report = audit_report(engine)
    assert report["benchmark_coverage"]["gpu"]["with_benchmarks"] == 0
    assert len(report["priority_gaps"]["cpu"]) >= 1


def test_missing_field_impact_rating_is_stable():
    assert rate_missing_field_impact("cores", "cpu_specifications") >= \
        rate_missing_field_impact("interface", "gpu_specifications")
