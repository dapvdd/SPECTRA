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

import math

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


# ---------------------------------------------------------------------------
# Suitability rating (Objective B)
# ---------------------------------------------------------------------------

# Workload -> primary benchmark family used for the rating signal.
_WORKLOAD_PRIMARY_FAMILY = {
    "gaming": "multi-core",
    "workstation": "multi-core",
    "productivity": "single-core",
}

# Star anchors: score -> stars, derived from the observed Geekbench 7
# percentile distribution of the benchmarked population (p10..p90). These are
# deterministic reference baselines, documented in docs/SCORING_METHODOLOGY.md.
_SINGLE_CORE_ANCHORS = (667.0, 983.0, 1325.0, 1637.0, 2020.0)  # stars 1..5
_MULTI_CORE_ANCHORS = (1409.0, 2809.0, 5001.0, 8017.0, 16347.0)  # stars 1..5

# content_creation is a blend of the two CPU families.
_CONTENT_BLEND_MULTI = 0.6
_CONTENT_BLEND_SINGLE = 0.4

# Spec-based ratings are never awarded flagship-tier stars on weak evidence.
_SPEC_BASED_MAX_STARS = 3

# GPU gaming spec-based estimate: weight memory capacity vs clock speed.
_GPU_GB_WEIGHT = 0.6
_GPU_CLOCK_WEIGHT = 0.4
_GPU_GB_FLOOR_LOG2 = 33  # ~16GB maps to ~0.85, 8GB to ~0.69
_GPU_CLOCK_LO = 400.0
_GPU_CLOCK_HI = 2400.0

_UNRATED_REASON_AI_ML = "insufficient_data:no_gpu_benchmarks"
_UNRATED_REASON_NO_EVIDENCE = "insufficient_data:no_evidence"


def _pick_score(hardware, family: str) -> float | None:
    """Best benchmark score of the given family present on the hardware."""
    best = None
    for benchmark in getattr(hardware, "benchmark_results", ()) or ():
        if getattr(benchmark, "test_type", None) == family:
            value = getattr(benchmark, "score", None)
            if value is not None and (best is None or value > best):
                best = value
    return best


def _score_to_stars(score: float, anchors: tuple) -> float:
    """Map a benchmark score to continuous stars 1..5 via anchor interpolation."""
    if score <= anchors[0]:
        return 1.0
    if score >= anchors[-1]:
        return 5.0
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i + 1]
        if lo <= score <= hi:
            frac = (score - lo) / (hi - lo)
            return round(i + 1 + frac, 2)
    return 1.0


def _cpu_spec_star_estimate(hardware) -> float:
    """Spec-only estimate for a CPU based on cores and boost clock."""
    spec = getattr(hardware, "cpu_specification", None)
    if spec is None:
        return 1.0
    cores = getattr(spec, "cores", None) or 0
    boost = getattr(spec, "boost_clock_ghz", None) or getattr(spec, "base_clock_ghz", None) or 0
    cores_strength = min(1.0, cores / 16.0)
    clock_strength = min(1.0, max(0.0, (boost - 2.0) / 3.0))
    return 1.0 + (0.6 * cores_strength + 0.4 * clock_strength) * 3.0


def _gpu_spec_star_estimate(hardware) -> float:
    """Spec-only estimate for a GPU based on memory capacity and clock."""
    spec = getattr(hardware, "gpu_specification", None)
    if spec is None:
        return 1.0
    memory_gb = getattr(spec, "memory_gb", None) or 0
    clock = getattr(spec, "core_clock_mhz", None) or 0
    gb_strength = min(1.0, math.log2(memory_gb + 1) / math.log2(_GPU_GB_FLOOR_LOG2))
    clock_strength = min(1.0, max(0.0, (clock - _GPU_CLOCK_LO) / (_GPU_CLOCK_HI - _GPU_CLOCK_LO)))
    return 1.0 + (_GPU_GB_WEIGHT * gb_strength + _GPU_CLOCK_WEIGHT * clock_strength) * 3.0


def _spec_star_estimate(hardware) -> float:
    if hardware.type == "GPU":
        return _gpu_spec_star_estimate(hardware)
    return _cpu_spec_star_estimate(hardware)


def rate_suitability(hardware, workload: str, detail=None) -> dict:
    """Return a deterministic suitability rating for one hardware+workload.

    Result keys: ``stars`` (int 0..5), ``raw_score`` (float 0..5),
    ``confidence``, ``evidence_quality``, ``spec_based`` (bool), ``category``,
    ``rationale`` (list[str]), ``caveats`` (list[str]), ``unrated_reason``.
    """
    evidence = score_evidence_quality(hardware, workload)
    category = workload

    # ---- Unrated states ----------------------------------------------
    if workload == "ai_ml":
        return {
            "stars": 0,
            "raw_score": 0.0,
            "confidence": "unrated",
            "evidence_quality": evidence,
            "spec_based": False,
            "category": category,
            "rationale": [],
            "caveats": [
                "insufficient_data: no GPU/VRAM benchmark evidence in this "
                "dataset to rate AI/ML suitability",
            ],
            "unrated_reason": _UNRATED_REASON_AI_ML,
        }

    if evidence["score"] == 0.0:
        return {
            "stars": 0,
            "raw_score": 0.0,
            "confidence": "unrated",
            "evidence_quality": evidence,
            "spec_based": False,
            "category": category,
            "rationale": [],
            "caveats": ["insufficient_data: no spec, benchmark, or provenance "
                        "evidence available"],
            "unrated_reason": _UNRATED_REASON_NO_EVIDENCE,
        }

    # ---- Rated states ------------------------------------------------
    family = _WORKLOAD_PRIMARY_FAMILY.get(category)
    benchmark_score = _pick_score(hardware, family) if family else None
    spec_based = benchmark_score is None

    if not spec_based:
        # benchmark-driven rating
        if category == "content_creation":
            mc = _pick_score(hardware, "multi-core")
            sc = _pick_score(hardware, "single-core")
            raw = (_CONTENT_BLEND_MULTI * _score_to_stars(mc or 0, _MULTI_CORE_ANCHORS)
                   + _CONTENT_BLEND_SINGLE * _score_to_stars(sc or 0, _SINGLE_CORE_ANCHORS))
        else:
            anchors = (
                _SINGLE_CORE_ANCHORS
                if family == "single-core"
                else _MULTI_CORE_ANCHORS
            )
            raw = _score_to_stars(benchmark_score, anchors)
        confidence = "high" if evidence["confidence"] == "high" else "medium"
        rationale_base = (
            f"Benchmark evidence present: {family} score {benchmark_score:g}"
        )
    else:
        raw = _spec_star_estimate(hardware)
        # Spec-based ratings are capped and never claim high confidence.
        if raw > _SPEC_BASED_MAX_STARS:
            raw = float(_SPEC_BASED_MAX_STARS)
        confidence = "low" if evidence["confidence"] == "low" else "medium"
        rationale_base = (
            "No driver/benchmark evidence; rating based on specifications only"
        )

    stars = int(round(raw))
    stars = max(0, min(stars, 5))

    rationale = [rationale_base]
    caveats = _build_caveats(
        hardware, category, spec_based, evidence, benchmark_score
    )

    return {
        "stars": stars,
        "raw_score": round(raw, 2),
        "confidence": confidence,
        "evidence_quality": evidence,
        "spec_based": spec_based,
        "category": category,
        "rationale": rationale,
        "caveats": caveats,
        "unrated_reason": None,
    }


def _build_caveats(
    hardware, category, spec_based, evidence, benchmark_score
) -> list[str]:
    """Explain evidence limitations and missing dimensions for a rating."""
    caveats: list[str] = []
    if spec_based:
        caveats.append(
            "No workload-appropriate benchmark data; rating is spec-based "
            "and capped at 3 stars"
        )
    else:
        caveats.append(f"Based on the available {category} benchmark evidence")
    if not evidence["signals"]["provenance"]:
        caveats.append("No verified field-level provenance for this hardware")
    if category in ("gaming",):
        caveats.append(
            "Rating reflects raw compute suitability, not a measured gaming "
            "FPS figure (no such data is available)"
        )
    if hardware.type == "GPU":
        caveats.append(
            "This GPU rating describes the GPU alone, not a complete laptop/PC"
        )
    return caveats
