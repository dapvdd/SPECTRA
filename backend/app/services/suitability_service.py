"""Workload-aware hardware suitability & evidence-quality scoring.

Two SEPARATE, deterministic dimensions (both versioned — see
docs/SCORING_METHODOLOGY.md):

1. **Evidence quality** (Objective C): how trustworthy our data is for a
   ``(hardware, workload)`` pair. A float 0..1 from weighted 0/1 signals, plus
   a confidence label. Independent of whether the hardware is any good.

2. **Suitability rating** (Objective B): how suitable the hardware is for a
   specific workload, as 0..5 stars with rationale and explicit caveats.

Neither dimension fabricates values: when the evidence bar is not met the
result is ``unrated`` / 0 stars with an explanatory reason. Scores are pure
functions of the input objects (duck-typed, so tests pass lightweight
stand-ins) and are deterministic: the same input always yields the same
output. They are heuristic ratings, NOT empirically calibrated probabilities.
"""

from __future__ import annotations

# Workload categories (closed vocabulary shared with the API).
WORKLOADS = frozenset(
    {"gaming", "workstation", "productivity", "content_creation", "ai_ml"}
)

# Benchmark family each CPU-oriented workload relies on. ``ai_ml`` has no
# supported family in this dataset (no GPU benchmark rows), so its family is
# None and its evidence bar is never met.
_WORKLOAD_BENCHMARK_FAMILY = {
    "gaming": "multi-core",
    "workstation": "multi-core",
    "content_creation": "multi-core",
    "productivity": "single-core",
    "ai_ml": None,
}

# ---------------------------------------------------------------------------
# Evidence quality signals (weights sum to 1.0)
# ---------------------------------------------------------------------------

_ATTR_WEIGHT = 0.35       # a benchmark of the workload's family exists
_SPEC_WEIGHT = 0.25       # the workload's key spec fields are non-null
_PROVENANCE_WEIGHT = 0.20  # a verified field_provenance row exists
_WORKLOAD_MATCH_WEIGHT = 0.20  # a benchmark of the workload's family exists

_CONF_HIGH = 0.6
_CONF_MEDIUM = 0.35


# Core spec fields required per workload (for the spec-coverage signal).
_CPU_SPEC_FIELDS = ("cores", "threads", "base_clock_ghz")
_GPU_SPEC_FIELDS = ("memory_gb", "memory_type", "core_clock_mhz")


def _workload_benchmark_family(workload: str) -> str | None:
    return _WORKLOAD_BENCHMARK_FAMILY.get(workload)


def _has_relevant_benchmark(hardware, workload: str) -> bool:
    family = _workload_benchmark_family(workload)
    if family is None:
        return False
    for benchmark in getattr(hardware, "benchmark_results", ()) or ():
        if getattr(benchmark, "test_type", None) == family:
            return True
    return False


def _has_any_benchmark(hardware) -> bool:
    return bool(getattr(hardware, "benchmark_results", ()) or ())


def _has_key_spec_fields(hardware, workload: str) -> bool:
    if workload == "ai_ml":
        return False  # AI/ML has no spec-only evidence bar in this dataset
    if hardware.type == "GPU":
        spec = getattr(hardware, "gpu_specification", None)
        fields = _GPU_SPEC_FIELDS
    else:
        spec = getattr(hardware, "cpu_specification", None)
        fields = _CPU_SPEC_FIELDS
    if spec is None:
        return False
    return all(getattr(spec, field, None) is not None for field in fields)


def _has_verified_provenance(hardware) -> bool:
    for record in getattr(hardware, "field_provenance", ()) or ():
        if getattr(record, "evidence_status", None) == "verified":
            return True
    return False


def _confidence_label(score: float) -> str:
    if score >= _CONF_HIGH:
        return "high"
    if score >= _CONF_MEDIUM:
        return "medium"
    return "low"


def score_evidence_quality(hardware, workload: str) -> dict:
    """Return a deterministic evidence-quality payload for one hardware+workload.

    Signals (each 0/1, weights sum to 1.0):
      - attribution       : a benchmark of the workload's family exists (0.35)
      - spec              : the workload's key spec fields are non-null (0.25)
      - provenance        : a verified field_provenance row exists (0.20)
      - workload_match    : a benchmark of the workload's family exists (0.20)

    ``ai_ml`` has no supported benchmark family, so attribution and
    workload_match are always False for it — its evidence quality is at most
    ``spec`` + ``provenance`` and is never ``high`` in this dataset.

    Returned dict: ``score`` (0..1), ``confidence``, ``signals``, ``reason``.
    """
    relevant = _has_relevant_benchmark(hardware, workload)
    any_benchmark = _has_any_benchmark(hardware)
    spec_ok = _has_key_spec_fields(hardware, workload)
    prov_ok = _has_verified_provenance(hardware)

    # Attribution requires a benchmark of the workload's family: a single-core
    # benchmark is evidence that the hardware is benchmarked at all, but not
    # evidence for a multi-core workload. Note that attribution and
    # workload_match are both family-specific and move together; they are kept
    # as separate signals so the payload transparently reports both facets.
    attribution = relevant
    workload_match = relevant

    contribution = 0.0
    contribution += _ATTR_WEIGHT if attribution else 0.0
    contribution += _SPEC_WEIGHT if spec_ok else 0.0
    contribution += _PROVENANCE_WEIGHT if prov_ok else 0.0
    contribution += _WORKLOAD_MATCH_WEIGHT if workload_match else 0.0
    score = round(contribution, 4)

    return {
        "score": score,
        "confidence": _confidence_label(score),
        "signals": {
            "attribution": attribution,
            "spec": spec_ok,
            "provenance": prov_ok,
            "workload_match": workload_match,
            "any_benchmark": any_benchmark,
        },
        "reason": None,
    }
