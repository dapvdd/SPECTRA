"""Stage 4 — CPU/GPU coverage verification + feasibility of filling gaps.

Reads the isolated dev DB (and standard spec-field lists) to classify every
CPU/GPU spec field gap as either *fillable by a clear-licensed source* or
*blocked*, with an explicit reason. Nothing is written here and nothing is
invented: every number comes from SQL over the dev copy.

Feasibility rule: a (table, field) is fillable only when it maps to a
clear-licensed adapter in the Stage 2 registry (e.g. GPU Ark -> GPU specs).
CPU-field sources (Intel ARK, AMD csv, Geekbench) are still unknown-licensed
so empty CPU values stay honestly blocked until a clear CPU source is proven.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Make backend importable when run as a script (same as other scripts).
if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import enrichment_pipeline as ep

# The isolated dev copy. Never touched as a write target here — read-only.
COVERAGE_DB = (
    Path(__file__).resolve().parents[3] / "data" / "dev" / "spectra_dev.db"
)

CPU_FIELDS = [
    "cores", "threads", "base_clock_ghz", "boost_clock_ghz",
    "tdp_w", "process_node_nm", "socket",
]
GPU_FIELDS = [
    "memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
    "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface",
    "length_mm",
]

# ---------------------------------------------------------------------------
# Feasibility: does a clear-license source cover (table, field)?
# ---------------------------------------------------------------------------
# GPU Ark adapter maps (from Stage 2 registration):
#   boost_clock_mhz -> boost_clock_mhz   (GPU Ark covers ~65% of rows)
#   tdp_w            -> tdp_w            (GPU Ark tdp is well-populated)
#   memory_size_gb   -> memory_gb
# No CPU-field source is clear-licensed today (CPU sources unknown/restricted).
_CLEAR_MAP = {
    "gpu_specifications": {
        "boost_clock_mhz": True,
        "tdp_w": True,
        "memory_gb": True,
    },
    "cpu_specifications": {},
}


def has_clear_source(table_name: str, field_name: str) -> bool:
    """True when a registered clear-license adapter maps that spec field."""
    return _CLEAR_MAP.get(table_name, {}).get(field_name, False)


def classify_feasibility() -> dict:
    """Classify each spec field's current gap as fillable/blocked (dev DB)."""
    conn = sqlite3.connect(str(COVERAGE_DB))
    try:
        out = {}
        for table, hw_type, fields in (
            ("cpu_specifications", "CPU", CPU_FIELDS),
            ("gpu_specifications", "GPU", GPU_FIELDS),
        ):
            out[table] = []
            for field in fields:
                missing = conn.execute(
                    f"SELECT COUNT(*) FROM hardware h JOIN {table} s "
                    f"ON s.hardware_id = h.id WHERE h.type = ? "
                    f"AND s.{field} IS NULL",
                    (hw_type,),
                ).fetchone()[0]
                fillable = has_clear_source(table, field)
                if fillable:
                    reason = (
                        "clear-licensed adapter covers this field; NULL can be "
                        "filled where the source has a value"
                    )
                elif table.startswith("cpu"):
                    reason = (
                        "no clear-licensed CPU source (CPU sources are "
                        "unknown/restricted license) - blocked"
                    )
                else:
                    reason = (
                        "no clear-licensed adapter maps this field - blocked"
                    )
                out[table].append(
                    {"field": field, "missing": missing,
                     "fillable": fillable, "reason": reason}
                )
        return out
    finally:
        conn.close()


def build_report() -> dict:
    """Full Stage-4 coverage report (deterministic, derived from dev DB)."""
    feasibility = classify_feasibility()
    conn = sqlite3.connect(str(COVERAGE_DB))
    try:
        totals = {
            "hardware": conn.execute(
                "SELECT COUNT(*) FROM hardware").fetchone()[0],
            "cpu": conn.execute(
                "SELECT COUNT(*) FROM hardware WHERE type='CPU'").fetchone()[0],
            "gpu": conn.execute(
                "SELECT COUNT(*) FROM hardware WHERE type='GPU'").fetchone()[0],
            "cpu_specifications": conn.execute(
                "SELECT COUNT(*) FROM cpu_specifications").fetchone()[0],
            "gpu_specifications": conn.execute(
                "SELECT COUNT(*) FROM gpu_specifications").fetchone()[0],
            "benchmark_results": conn.execute(
                "SELECT COUNT(*) FROM benchmark_results").fetchone()[0],
        }
    finally:
        conn.close()

    return {
        "tool": "coverage_verification",
        "target": str(COVERAGE_DB),
        "totals": totals,
        "feasibility": feasibility,
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
