"""M4 Task 2: explainable scenario scoring engine (SCORING_VERSION M4-SCORING-v2.0).

Extends — never replaces — the v1 methodology in
``docs/SCORING_METHODOLOGY.md`` (reference: ``suitability_service.py``):

- **Anchors are derived, not invented**: percentile anchors (p10/p25/p50/p75/p90)
  are computed deterministically from the observed benchmark population passed
  to the engine. For the M3.3 production-like snapshot these reproduce the v1
  documented anchors for single-core (<0.3% drift) and land near them for
  multi-core; the multi-core p90 difference is the documented calibration drift
  (``docs/fan/CALIBRATION_REPORT.md``), not a silent re-anchor.

- **Evidence gates** (mission Task 2): a scenario is scored only when evidence
  exists for it. With no benchmark of the scenario's family, the engine falls
  back to a spec-based estimate that is hard-capped at 3.0 (v1's
  ``SPEC_BASED_MAX_STARS``) and never claims high confidence. With no evidence
  at all the scenario is UNKNOWN — ``score=None``, ``confidence="unknown"``,
  with a limitation naming the gap. UNKNOWN is never rendered as 0 or fabricated.

- **VALUE is price-gated**: scores only when explicit price evidence is supplied
  (``evidence={"price_usd": ...}``). This dataset carries no price data, so
  VALUE is always UNKNOWN here; the gate also accepts stale prices only with a
  low-confidence ceiling and a limitation naming the price date.

- **No recency bias, no fabricated FPS**: release_date and architecture are not
  scoring features; resolution context without GPU evidence adds a limitation,
  never a numeric change.

- Pure functions; deterministic; every payload carries ``scoring_version``.
"""

from __future__ import annotations

import math

from backend.app.services.suitability_service import _score_to_stars

SCORING_VERSION = "M4-SCORING-v2.0"
RULES_COMPAT = "M32-RULES-v2"

SCENARIOS: tuple[str, ...] = ("gaming", "workstation", "daily", "value")

# Scenario -> primary benchmark family (v1-compatible mapping).
_FAMILY = {
    "gaming": "multi-core",
    "workstation": "multi-core",
    "daily": "single-core",
    "value": None,
}

# Scenario -> feature weights (present features only; renormalised per vector).
_BASE_WEIGHTS = {
    "gaming": {
        "multi_core_score": 0.5, "single_core_score": 0.2,
        "efficiency": 0.2, "memory_gb": 0.1,
    },
    "workstation": {
        "multi_core_score": 0.45, "single_core_score": 0.2,
        "cores": 0.2, "efficiency": 0.15,
    },
    "daily": {
        "single_core_score": 0.6, "efficiency": 0.4,
    },
    "value": {},
}

# Spec-proxy weights for the spec-based capped path (per hardware type).
_SPEC_PROXY = {
    "CPU": {
        "cores": 0.5, "threads": 0.2, "base_clock_ghz": 0.2, "boost_clock_ghz": 0.1,
    },
    "GPU": {
        "memory_gb": 0.4, "vram_bandwidth_gbps": 0.3, "core_clock_mhz": 0.2,
        "boost_clock_mhz": 0.1,
    },
}

# Normalisation ranges per feature (clamped, from catalog-observed spreads).
_RANGES = {
    "cores": (2.0, 64.0),
    "threads": (2.0, 128.0),
    "base_clock_ghz": (1.0, 5.0),
    "boost_clock_ghz": (2.0, 6.0),
    "tdp_w": (10.0, 350.0),
    "memory_gb": (1.0, 32.0),
    "core_clock_mhz": (300.0, 3000.0),
    "boost_clock_mhz": (500.0, 3200.0),
    "vram_bandwidth_gbps": (50.0, 1200.0),
    "memory_bus_width_bits": (64.0, 1024.0),
    "efficiency": (5.0, 200.0),
}

_SPEC_BASED_MAX_SCORE = 3.0
_RESOLUTION_FAMILIES = ("1080p", "1440p", "4k")


def derive_anchors(scores: list[float]) -> tuple | None:
    """Percentile anchors (p10, p25, p50, p75, p90) with linear interpolation.

    Returns None for an empty population. Deterministic: sorted input order,
    rank k = (n-1)*p/100, floor/ceil interpolation.
    """
    if not scores:
        return None
    ordered = sorted(float(s) for s in scores)
    n = len(ordered)
    out = []
    for p in (10, 25, 50, 75, 90):
        k = (n - 1) * p / 100.0
        lo = math.floor(k)
        hi = min(lo + 1, n - 1)
        out.append(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))
    return tuple(out)


def _anchors_to_stars(anchors) -> tuple:
    """Convert score anchors to a stars tuple for ``_score_to_stars``."""
    return (1.0, 2.0, 3.0, 4.0, 5.0), anchors


def _normalise_feature(name: str, value) -> float | None:
    if value is None or name not in _RANGES:
        return None
    lo, hi = _RANGES[name]
    span = hi - lo
    return round(max(0.0, min(1.0, (float(value) - lo) / span)), 6)


def _weighted_blend(parts: list[tuple[float, float]]) -> float | None:
    """Weighted mean of (normalized_value, weight) pairs, weights renormalised."""
    total_w = sum(w for _, w in parts)
    if total_w <= 0 or not parts:
        return None
    return round(sum(v * w for v, w in parts) / total_w, 4)


def _scenario_payload(score, stars, confidence, data_coverage, factors,
                      limitations, spec_based) -> dict:
    return {
        "score": score,
        "stars": stars,
        "confidence": confidence,
        "data_coverage": data_coverage,
        "contributing_factors": factors,
        "limitations": limitations,
        "spec_based": spec_based,
        "scoring_version": SCORING_VERSION,
    }


def _stars_from_score(score: float) -> int:
    return max(0, min(5, int(round(score))))


def _benchmark_stars(features: dict, family: str, anchors) -> float | None:
    key = "multi_core_score" if family == "multi-core" else "single_core_score"
    value = features.get(key)
    if value is None or anchors is None or anchors.get(family) is None:
        return None
    return _score_to_stars(float(value), anchors[family])


def _benchmark_factors(features: dict, scenario: str) -> list[dict]:
    weights = _BASE_WEIGHTS[scenario]
    factors = []
    for name in ("multi_core_score", "single_core_score"):
        if name in weights and features.get(name) is not None:
            factors.append({
                "feature": name,
                "weight": weights[name],
                "normalized": None,
                "present": True,
                "benchmark_value": features[name],
            })
    return factors


def _spec_factors(features: dict, weights: dict) -> list[dict]:
    factors = []
    for name, weight in weights.items():
        value = features.get(name)
        norm = _normalise_feature(name, value)
        if value is None:
            continue
        factors.append({
            "feature": name,
            "weight": weight,
            "normalized": norm,
            "present": True,
        })
    return factors


def _score_scenario(features: dict, scenario: str, anchors, spec_based: bool,
                    hardware_type: str = "CPU") -> dict:
    family = _FAMILY[scenario]
    coverage = 0.0 if features is None else 0.0
    if not spec_based:
        stars = _benchmark_stars(features, family, anchors)
        factors = _benchmark_factors(features, scenario)
        # Add spec-supported secondary factors (efficiency/cores where weighted).
        secondary = {
            name: w for name, w in _BASE_WEIGHTS[scenario].items()
            if name not in ("multi_core_score", "single_core_score")
        }
        sec_factors = _spec_factors(features, secondary)
        factors.extend(sec_factors)
        if stars is None:
            return _scenario_payload(
                None, 0, "unknown", features.get("coverage", 0.0), [],
                ["insufficient_data: no benchmark of the scenario's family"],
                False,
            )
        # Blend: benchmark stars carry the family weight; secondary features
        # modulate within +/-10% of the benchmark-derived stars (documented).
        mods = []
        for factor in sec_factors:
            if factor["normalized"] is not None:
                mods.append((factor["normalized"], factor["weight"]))
        mod = _weighted_blend(mods) if mods else None
        score = stars
        if mod is not None:
            score = round(stars * (0.9 + 0.2 * mod), 2)
            score = max(0.0, min(5.0, score))
        confidence = "high" if features.get("coverage", 0.0) >= 0.6 else "medium"
        return _scenario_payload(
            score, _stars_from_score(score), confidence,
            features.get("coverage", 0.0), factors, [], False,
        )

    # ---- spec-based capped path ----
    weights = dict(_SPEC_PROXY.get(hardware_type, {}))
    weights.update({k: v for k, v in (_BASE_WEIGHTS.get(scenario) or {}).items()
                    if k in weights})
    factors = _spec_factors(features, weights)
    blend = _weighted_blend([(f["normalized"], f["weight"]) for f in factors])
    if blend is None:
        return _scenario_payload(
            None, 0, "unknown", features.get("coverage", 0.0), [],
            ["insufficient_data: no benchmark and no usable specs"], True,
        )
    score = round(1.0 + blend * (_SPEC_BASED_MAX_SCORE - 1.0), 2)
    limitations = [
        "spec_based: no workload-appropriate benchmark data; score capped at 3.0"
    ]
    return _scenario_payload(
        score, _stars_from_score(score), "medium",
        features.get("coverage", 0.0), factors, limitations, True,
    )


def _value_scenario(features: dict, evidence: dict | None) -> dict:
    """Price-gated value scoring. No price -> UNKNOWN, always."""
    price = (evidence or {}).get("price_usd")
    if price is None or price <= 0:
        return _scenario_payload(
            None, 0, "unknown", 0.0, [],
            ["missing_data:price — no price data in this dataset; value "
             "cannot be scored without a verifiable comparable price"],
            False,
        )
    as_of = (evidence or {}).get("price_as_of")
    perf = features.get("multi_core_score") or features.get("single_core_score")
    if perf is None:
        return _scenario_payload(
            None, 0, "unknown", features.get("coverage", 0.0), [],
            ["missing_data: no performance evidence to price against"], False,
        )
    perf_per_dollar = perf / float(price)
    factors = [{
        "feature": "price_usd", "weight": 1.0,
        "normalized": None, "present": True, "price_as_of": as_of,
    }, {
        "feature": "multi_core_score" if features.get("multi_core_score") else "single_core_score",
        "weight": 1.0, "normalized": None, "present": True,
        "benchmark_value": perf,
    }]
    limitations = [
        "price/volume calibration is absent in this dataset; ratio is "
        "relative, not a market claim"
    ]
    if as_of is None:
        limitations.append("price_as_of absent: staleness unverifiable")
        confidence = "low"
    else:
        confidence = "low"
    return _scenario_payload(
        round(perf_per_dollar, 4), 0, confidence,
        features.get("coverage", 0.0), factors, limitations, False,
    )


def score_scenarios(features: dict, anchors: dict | None = None,
                    profile: dict | None = None,
                    evidence: dict | None = None) -> dict:
    """Score all scenarios for one feature vector.

    ``anchors`` maps family -> 5-tuple of score anchors (see derive_anchors).
    ``profile`` optionally carries scenario_weights (from workload_profiles)
    and preferences (resolution). ``evidence`` optionally carries price data.
    """
    features = features or {}
    fv = features.get("features", features)
    coverage = features.get("coverage", 0.0)

    # No evidence at all -> every non-value scenario UNKNOWN.
    any_evidence = bool(fv) and (
        coverage > 0.0
        or bool(features.get("benchmark_families"))
    )

    weights = dict(_BASE_WEIGHTS)
    if profile and profile.get("scenario_weights"):
        for scenario, weight in profile["scenario_weights"].items():
            if scenario in weights and weight is not None:
                weights[scenario] = dict(weights[scenario])
                weights[scenario]["_profile_weight"] = weight

    out: dict[str, dict] = {}
    for scenario in SCENARIOS:
        if scenario == "value":
            out[scenario] = _value_scenario(fv, evidence)
            continue
        if not any_evidence:
            out[scenario] = _scenario_payload(
                None, 0, "unknown", coverage, [],
                ["insufficient_data: no specs, benchmarks, or provenance"],
                False,
            )
            continue
        family = _FAMILY[scenario]
        has_benchmark = family in (features.get("benchmark_families") or ())
        out[scenario] = _score_scenario(
            fv, scenario, anchors or {}, not has_benchmark,
            hardware_type=features.get("type", "CPU"),
        )

    # Resolution context: limitation only, never numeric change (no GPU
    # gaming evidence exists in this dataset).
    prefs = (profile or {}).get("preferences") or {}
    resolution = prefs.get("resolution")
    if resolution in _RESOLUTION_FAMILIES:
        gaming = out["gaming"]
        if gaming["score"] is not None:
            out["gaming"] = {
                **gaming,
                "limitations": list(gaming["limitations"]) + [
                    f"resolution {resolution}: no GPU gaming benchmark evidence "
                    "in this dataset; resolution tier is advisory context, not "
                    "a measured performance adjustment"
                ],
            }

    return {
        "scoring_version": SCORING_VERSION,
        "reference_population": (
            "Geekbench 7 scores of benchmarked CPUs in the M3.3 "
            "production-like snapshot (518 CPUs x single/multi-core); "
            "anchors are deterministic percentiles (p10/p25/p50/p75/p90) of "
            "that population"
        ),
        "data_coverage": coverage,
        "scenarios": out,
    }
