"""M4 Task 1: deterministic hardware feature layer (FEATURE_VERSION M4-FEATURES-v1).

Pure functions over duck-typed hardware objects. Design contract (plan + mission
Task 1):

- **missing is not zero**: every absent value stays ``None`` and is additionally
  listed in ``missing`` so consumers can distinguish "no data" from "measured 0".
- Type-applicable feature sets: CPU and GPU vectors carry disjoint feature keys
  (a GPU vector has no ``cores``; a CPU vector has no ``memory_gb``).
- Benchmark scores are picked per family as the MAXIMUM observed score; only
  families actually present on the row appear in ``benchmark_families``.
- Derived features are guarded: ``efficiency`` is None unless both inputs are
  present and positive.
- ``normalise`` maps a value into 0..1 with clamping; None passes through; a
  degenerate range returns 0.0 rather than dividing by zero.
- ``coverage`` is the non-null share of the applicable feature set (0..1).
- Provenance and freshness are summaries of rows that already exist; nothing is
  inferred, nothing is fabricated.

No DB access, no I/O; deterministic by construction.
"""

from __future__ import annotations

FEATURE_VERSION = "M4-FEATURES-v1"

# Type-applicable feature sets (order = presentation order).
CPU_FEATURES: tuple[str, ...] = (
    "single_core_score", "multi_core_score",
    "cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w",
    "efficiency", "socket", "process_node_nm",
)
GPU_FEATURES: tuple[str, ...] = (
    "single_core_score", "multi_core_score",
    "memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
    "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface",
)

# The two benchmark families SPECTRA currently stores (Geekbench 7 split).
BENCHMARK_FAMILIES: tuple[str, ...] = ("single-core", "multi-core")

_BENCH_KEY = {
    "single-core": "single_core_score",
    "multi-core": "multi_core_score",
}

# Which spec table/fields back the provenance summary key, per type.
_SPEC_FIELDS_BY_TYPE = {
    "GPU": ("memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
            "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface"),
    "CPU": ("cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w",
            "socket", "process_node_nm"),
}


def normalise(value, lo: float, hi: float) -> float | None:
    """Min-max normalise into 0..1 with clamping; None in -> None out.

    A value outside [lo, hi] clamps to the boundary (never extrapolates).
    A degenerate range (hi <= lo) returns 0.0 for any present value.
    """
    if value is None:
        return None
    if hi <= lo:
        return 0.0
    span = hi - lo
    return round(max(0.0, min(1.0, (value - lo) / span)), 6)


def derive_efficiency(score, tdp) -> float | None:
    """Score-per-watt; None unless both inputs present and tdp > 0."""
    if score is None or tdp is None or tdp <= 0:
        return None
    return round(score / tdp, 4)


def _best_score_by_family(benchmarks) -> dict[str, float]:
    best: dict[str, float] = {}
    for benchmark in benchmarks or ():
        family = getattr(benchmark, "test_type", None)
        value = getattr(benchmark, "score", None)
        if family is None or value is None:
            continue
        if family not in best or value > best[family]:
            best[family] = value
    return best


def _verified_provenance_fields(hardware) -> list[str]:
    fields: list[str] = []
    for record in getattr(hardware, "field_provenance", ()) or ():
        if getattr(record, "evidence_status", None) != "verified":
            continue
        field_name = getattr(record, "field_name", None)
        if field_name is None:
            continue
        key = f"{getattr(record, 'table_name', '')}.{field_name}"
        if key not in fields:
            fields.append(key)
    return fields


def _freshness(benchmarks) -> dict:
    stamps = [
        getattr(b, "recorded_at", None)
        for b in benchmarks or ()
        if getattr(b, "recorded_at", None) is not None
    ]
    if stamps:
        latest = max(stamps)
        return {
            "recorded_at_present": True,
            "latest_recorded_at": latest.isoformat()
            if hasattr(latest, "isoformat") else str(latest),
        }
    return {"recorded_at_present": False, "latest_recorded_at": None}


def features_from_hardware(hardware) -> dict:
    """Build the M4 feature vector for one hardware row (pure, deterministic)."""
    hardware_type = getattr(hardware, "type", None)
    raw_benchmarks = getattr(hardware, "benchmark_results", None) or ()
    benchmark_scores = _best_score_by_family(raw_benchmarks)
    families = sorted(benchmark_scores)  # deterministic family order

    if hardware_type == "GPU":
        applicable = GPU_FEATURES
        spec_obj = getattr(hardware, "gpu_specification", None)
    else:
        # CPU is the default; unknown types degrade to the CPU view.
        applicable = CPU_FEATURES
        spec_obj = getattr(hardware, "cpu_specification", None)

    features: dict = {}
    for key in applicable:
        if key in ("single_core_score", "multi_core_score", "efficiency"):
            continue  # filled below from benchmarks / derivation
        features[key] = getattr(spec_obj, key, None) if spec_obj is not None else None

    for family in BENCHMARK_FAMILIES:
        key = _BENCH_KEY[family]
        if key in applicable:
            features[key] = benchmark_scores.get(family)

    if "efficiency" in applicable:
        features["efficiency"] = derive_efficiency(
            features.get("multi_core_score"), features.get("tdp_w")
        )

    missing = [k for k, v in features.items() if v is None]

    coverage = (
        round(sum(1 for v in features.values() if v is not None) / len(features), 4)
        if features else 0.0
    )

    return {
        "feature_version": FEATURE_VERSION,
        "type": hardware_type,
        "features": features,
        "missing": missing,
        "coverage": coverage,
        "benchmark_families": families,
        "provenance_verified_fields": _verified_provenance_fields(hardware),
        "data_freshness": _freshness(raw_benchmarks),
    }
