"""Stage 5 — workload-evidence analyzer.

Reproduces the suitability service's evidence signals at catalog scale so we
can verify, per workload, how much of the hardware population actually has the
evidence a rating needs. This is the honest, measurable basis for "which
workloads are rated vs unrated" — especially the ai_ml boundary (no GPU
benchmarks -> no benchmark-driven AI/ML evidence).

Sources of truth mirrored from ``backend.app.services.suitability_service``:
- workload -> benchmark family (gaming/workstation/content_creation -> multi-core;
  productivity -> single-core; ai_ml -> None).
- attribution & workload_match are only True when a benchmark of the workload's
  family exists; ai_ml's family is None so it can never be benchmark-driven.

Nothing is invented: every number comes from SQL over the isolated dev copy.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(PROJECT_ROOT))

WORKLOADS = ("gaming", "workstation", "productivity",
             "content_creation", "ai_ml")

_WORKLOAD_FAMILY = {
    "gaming": "multi-core",
    "workstation": "multi-core",
    "productivity": "single-core",
    "content_creation": "multi-core",
    "ai_ml": None,
}


def workload_family(workload: str) -> str | None:
    return _WORKLOAD_FAMILY.get(workload)


def analyze_hardware_evidence(
    *,
    hardware_type: str,
    workload: str,
    benchmark_families: set | frozenset,
    spec_ok: bool,
    provenance_ok: bool,
) -> dict:
    """Reproduce the four evidence signals + verdict for one hardware.

    Mirrors suitability_service.score_evidence_quality semantics:
    - attribution / workload_match: a benchmark of the workload's family exists.
    - spec: the workload's key spec fields are non-null.
    - provenance: a verified field_provenance row exists.
    Verdict: ``rated`` when there is any evidence; ``unrated`` when there is
    none or the workload has no supported family (ai_ml).

    Returns a deterministic dict with ``signals`` and ``verdict``.
    """
    family = workload_family(workload)
    family_set = set(benchmark_families or ())
    attribution = family is not None and family in family_set
    workload_match = attribution

    verdict = "rated" if (attribution or spec_ok or provenance_ok) else "unrated"
    # ai_ml is never benchmark-driven; hard boundary matches the service.
    if family is None:
        verdict = "unrated"

    return {
        "workload": workload,
        "hardware_type": hardware_type,
        "verdict": verdict,
        "signals": {
            "attribution": attribution,
            "spec": bool(spec_ok),
            "provenance": bool(provenance_ok),
            "workload_match": workload_match,
        },
    }


# ---------------------------------------------------------------------------
# Catalog-scale aggregation (dev DB, read-only)
# ---------------------------------------------------------------------------

_DEV_DB = Path(__file__).resolve().parents[3] / "data" / "dev" / "spectra_dev.db"

# Key spec fields per hardware type, matching the suitability service.
_CPU_SPEC_FIELDS = ("cores", "threads", "base_clock_ghz")
_GPU_SPEC_FIELDS = ("memory_gb", "memory_type", "core_clock_mhz")


def _open():
    conn = sqlite3.connect(str(_DEV_DB))
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def aggregate_by_workload(session_factory=None, conn=None):
    """Count per (type, workload) how many rows have each evidence signal.

    When ``session_factory`` is given (SQLAlchemy), counts come from that
    engine (used by tests with an isolated in-memory engine). Otherwise falls
    back to the dev-DB sqlite ``conn`` or the default dev DB path.

    Return dict: ``{"cpu": [row...], "gpu": [row...]}`` where each row has:
    total, with_benchmark_evidence, with_spec_evidence, with_provenance,
    unrated_boundary (True when workload has no benchmark family).
    """
    if session_factory is not None:
        return _aggregate_sqlalchemy(session_factory)

    own = conn is None
    if own:
        conn = _open()
    try:
        return _aggregate_sqlite(conn)
    finally:
        if own:
            conn.close()


def _aggregate_sqlite(conn) -> dict:
    out = {}
    for spec_type, table, hw_type, fields in (
        ("cpu", "cpu_specifications", "CPU", _CPU_SPEC_FIELDS),
        ("gpu", "gpu_specifications", "GPU", _GPU_SPEC_FIELDS),
    ):
        rows = []
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type=?", (hw_type,)
        ).fetchone()[0]
        spec_ok = conn.execute(
            "SELECT COUNT(*) FROM hardware h JOIN {} s ON s.hardware_id = h.id "
            "WHERE h.type=? AND {} IS NOT NULL AND {} IS NOT NULL AND {} IS NOT NULL"
            .format(table, fields[0], fields[1], fields[2]), (hw_type,)
        ).fetchone()[0]
        prov_ok = conn.execute(
            "SELECT COUNT(DISTINCT hardware_id) FROM field_provenance fp "
            "JOIN hardware h ON h.id=fp.hardware_id WHERE h.type=? "
            "AND fp.evidence_status='verified'", (hw_type,)
        ).fetchone()[0]

        for workload in WORKLOADS:
            family = workload_family(workload)
            with_family_bench = 0
            if family is not None:
                with_family_bench = conn.execute(
                    "SELECT COUNT(DISTINCT br.hardware_id) FROM benchmark_results br "
                    "JOIN hardware h ON h.id=br.hardware_id "
                    "WHERE h.type=? AND br.test_type=?", (hw_type, family)
                ).fetchone()[0]
            rows.append({
                "workload": workload,
                "total": total,
                "with_benchmark_evidence": with_family_bench,
                "with_spec_evidence": spec_ok,
                "with_provenance": prov_ok,
                "unrated_boundary": family is None,
            })
        out[spec_type] = rows
    return out


def _aggregate_sqlalchemy(session_factory) -> dict:
    from backend.app.models import (
        BenchmarkResult,
        CPUSpecification,
        FieldProvenance,
        GPUSpecification,
        Hardware,
    )
    from sqlalchemy import func, select

    def hw_type(name):
        return "CPU" if name == "cpu" else "GPU"

    out = {}
    for spec_type, spec_model, hw_t, fields in (
        ("cpu", CPUSpecification, "CPU", _CPU_SPEC_FIELDS),
        ("gpu", GPUSpecification, "GPU", _GPU_SPEC_FIELDS),
    ):
        with session_factory() as session:
            total = session.scalar(
                select(func.count(Hardware.id)).where(
                    Hardware.type == hw_t)
            ) or 0
            spec_ok = session.scalar(
                select(func.count(Hardware.id))
                .join(spec_model, spec_model.hardware_id == Hardware.id)
                .where(Hardware.type == hw_t)
                .where(*[getattr(spec_model, f).is_not(None) for f in fields])
            ) or 0
            prov_ok = session.scalar(
                select(func.count(func.distinct(FieldProvenance.hardware_id)))
                .join(Hardware, Hardware.id == FieldProvenance.hardware_id)
                .where(Hardware.type == hw_t,
                       FieldProvenance.evidence_status == "verified")
            ) or 0

        rows = []
        for workload in WORKLOADS:
            family = workload_family(workload)
            with_family_bench = 0
            if family is not None:
                with session_factory() as session:
                    with_family_bench = session.scalar(
                        select(func.count(func.distinct(
                            BenchmarkResult.hardware_id)))
                        .join(Hardware, Hardware.id ==
                              BenchmarkResult.hardware_id)
                        .where(Hardware.type == hw_t,
                               BenchmarkResult.test_type == family)
                    ) or 0
            rows.append({
                "workload": workload,
                "total": total,
                "with_benchmark_evidence": with_family_bench,
                "with_spec_evidence": spec_ok,
                "with_provenance": prov_ok,
                "unrated_boundary": family is None,
            })
        out[spec_type] = rows
    return out


def make_catalog_report() -> dict:
    """Deterministic Stage-5 report dict (totals + per-type aggregation)."""
    conn = _open()
    try:
        totals = {
            "hardware": conn.execute(
                "SELECT COUNT(*) FROM hardware").fetchone()[0],
            "cpu": conn.execute(
                "SELECT COUNT(*) FROM hardware WHERE type='CPU'").fetchone()[0],
            "gpu": conn.execute(
                "SELECT COUNT(*) FROM hardware WHERE type='GPU'").fetchone()[0],
            "benchmark_results": conn.execute(
                "SELECT COUNT(*) FROM benchmark_results").fetchone()[0],
        }
        agg = aggregate_by_workload(conn=conn)
    finally:
        conn.close()
    return {
        "tool": "workload_evidence",
        "target": str(_DEV_DB),
        "totals": totals,
        "by_type": agg,
    }


def main() -> int:
    import json
    report = make_catalog_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
