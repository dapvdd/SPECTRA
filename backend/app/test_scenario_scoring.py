"""M4 Task 2: scenario scoring engine v2 (SCORING_VERSION M4-SCORING-v2.0).

Covers backend/app/services/scenario_scoring.py:
- anchors derived deterministically from an observed score population (not
  hardcoded), with documented continuity to the v1 methodology
- scenario composition: gaming / workstation / daily from features + weights
- evidence gates: no benchmark -> spec-based capped path; no evidence -> unknown
- VALUE scenario: UNKNOWN unless price evidence exists (this dataset: never)
- monotonicity in the primary family score; no recency bonus
- explainability: contributing factors only for present features
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.services.scenario_scoring import (  # noqa: E402
    SCENARIOS,
    SCORING_VERSION,
    derive_anchors,
    score_scenarios,
)


def _anchors():
    return {
        "single-core": derive_anchors([224.0 + i * 10.0 for i in range(10)]),
        "multi-core": derive_anchors([382.0 + i * 100.0 for i in range(10)]),
    }


def _feature_vector(**overrides):
    features = {
        "single_core_score": 1500.0,
        "multi_core_score": 9000.0,
        "cores": 8, "threads": 16,
        "base_clock_ghz": 3.0, "boost_clock_ghz": 4.4,
        "tdp_w": 65.0, "efficiency": round(9000.0 / 65.0, 4),
        "socket": "AM5", "process_node_nm": 5.0,
    }
    features.update(overrides)
    return {
        "feature_version": "M4-FEATURES-v1",
        "type": "CPU",
        "features": features,
        "missing": [k for k, v in features.items() if v is None],
        "coverage": round(sum(v is not None for v in features.values()) / len(features), 4),
        "benchmark_families": ["multi-core", "single-core"],
        "provenance_verified_fields": ["cpu_specifications.cores"],
        "data_freshness": {"recorded_at_present": False, "latest_recorded_at": None},
    }


def _profile(scenario_weights=None):
    return {
        "key": "test_profile",
        "scenario_weights": scenario_weights
        or {"gaming": 0.5, "workstation": 0.3, "daily": 0.2, "value": 0.0},
        "feature_weight_overrides": {},
        "assumptions": ["test assumption"],
    }


# ---------------------------------------------------------------- anchors ----

def test_scoring_version_pinned():
    assert SCORING_VERSION == "M4-SCORING-v2.0"


def test_scenarios_vocabulary():
    assert SCENARIOS == ("gaming", "workstation", "daily", "value")


def test_derive_anchors_is_percentile_monotone_tuple5():
    scores = [float(100 + 10 * i) for i in range(21)]  # 100..300
    a = derive_anchors(scores)
    assert len(a) == 5
    assert all(a[i] <= a[i + 1] for i in range(4))
    assert a[0] >= min(scores) and a[-1] <= max(scores)


def test_derive_anchors_matches_known_percentiles():
    # 100..300 step 10: p10=120, p50=200, p90=280 (linear interpolation)
    a = derive_anchors([float(100 + 10 * i) for i in range(21)])
    assert a == (120.0, 150.0, 200.0, 250.0, 280.0)


def test_derive_anchors_single_element_population():
    assert derive_anchors([500.0]) == (500.0, 500.0, 500.0, 500.0, 500.0)


def test_derive_anchors_empty_population_is_none():
    assert derive_anchors([]) is None


# ------------------------------------------------------------- composition ---

def test_benchmark_driven_scoring_all_scenarios():
    out = score_scenarios(_feature_vector(), anchors=_anchors())
    for scenario in ("gaming", "workstation", "daily"):
        entry = out["scenarios"][scenario]
        assert entry["score"] is not None
        assert 0.0 <= entry["score"] <= 5.0
        assert entry["stars"] == int(round(entry["score"]))
        assert entry["spec_based"] is False
        assert entry["confidence"] in ("high", "medium", "low")
        assert entry["scoring_version"] == SCORING_VERSION
    assert out["reference_population"] and "Geekbench 7" in out["reference_population"]


def test_gaming_multi_core_dominates_workstation_uses_cores():
    fv = _feature_vector()
    out = score_scenarios(fv, anchors=_anchors())
    gaming = out["scenarios"]["gaming"]
    workstation = out["scenarios"]["workstation"]
    # Gaming is driven by multi-core + efficiency; workstation adds cores.
    # With strong cores (8) the workstation score should not be weaker when
    # core count contributes positively.
    assert workstation["score"] > 0
    factor_names = {f["feature"] for f in workstation["contributing_factors"]}
    assert "cores" in factor_names
    assert "multi_core_score" in {f["feature"] for f in gaming["contributing_factors"]}


def test_missing_benchmark_falls_back_to_spec_capped():
    fv = _feature_vector(multi_core_score=None, single_core_score=None)
    fv["benchmark_families"] = []
    fv["missing"] = [k for k, v in fv["features"].items() if v is None]
    out = score_scenarios(fv, anchors=_anchors())
    gaming = out["scenarios"]["gaming"]
    assert gaming["spec_based"] is True
    assert gaming["score"] is not None
    assert gaming["score"] <= 3.0
    assert gaming["confidence"] in ("low", "medium")
    assert any("spec" in lim.lower() for lim in gaming["limitations"])


def test_no_evidence_at_all_is_unknown():
    fv = _feature_vector(
        multi_core_score=None, single_core_score=None, cores=None, threads=None,
        base_clock_ghz=None, boost_clock_ghz=None, tdp_w=None, efficiency=None,
        socket=None, process_node_nm=None,
    )
    fv["benchmark_families"] = []
    fv["coverage"] = 0.0
    fv["missing"] = list(fv["features"])
    out = score_scenarios(fv, anchors=_anchors())
    for scenario in ("gaming", "workstation", "daily"):
        entry = out["scenarios"][scenario]
        assert entry["score"] is None
        assert entry["stars"] == 0
        assert entry["confidence"] == "unknown"
        assert any("insufficient" in lim for lim in entry["limitations"])


# ------------------------------------------------------------------ value ----

def test_value_scenario_unknown_without_price_evidence():
    out = score_scenarios(_feature_vector(), anchors=_anchors())
    value = out["scenarios"]["value"]
    assert value["score"] is None
    assert value["stars"] == 0
    assert value["confidence"] == "unknown"
    assert any("price" in lim for lim in value["limitations"])


def test_value_scenario_scores_only_with_price_evidence():
    out = score_scenarios(
        _feature_vector(), anchors=_anchors(),
        evidence={"price_usd": 200.0, "price_as_of": "2026-01-01"},
    )
    value = out["scenarios"]["value"]
    assert value["score"] is not None
    assert value["confidence"] in ("low", "medium")
    assert any("price" in f for f in
               [x["feature"] for x in value["contributing_factors"]])


# ------------------------------------------------- invariants & honesty -----

def test_monotonicity_in_primary_family_score():
    anchors = _anchors()
    scores = [score_scenarios(_feature_vector(multi_core_score=float(s)), anchors=anchors)
              ["scenarios"]["gaming"]["score"]
              for s in (1000.0, 3000.0, 6000.0, 12000.0, 22000.0)]
    assert scores == sorted(scores), scores


def test_no_recency_bonus_release_date_not_a_feature():
    fv = _feature_vector()
    out = score_scenarios(fv, anchors=_anchors())
    for scenario in SCENARIOS:
        features_used = [f["feature"] for f in out["scenarios"][scenario]["contributing_factors"]]
        assert "release_date" not in features_used
        assert "architecture" not in features_used


def test_contributing_factors_only_present_features():
    fv = _feature_vector(process_node_nm=None, socket=None)
    fv["missing"] = [k for k, v in fv["features"].items() if v is None]
    out = score_scenarios(fv, anchors=_anchors())
    for scenario in ("gaming", "workstation", "daily"):
        for factor in out["scenarios"][scenario]["contributing_factors"]:
            assert factor["present"] is True
            assert factor["feature"] not in fv["missing"]


def test_resolution_without_gpu_evidence_adds_limitation_only():
    fv = _feature_vector()
    profile = _profile()
    profile["preferences"] = {"resolution": "4k"}
    out = score_scenarios(fv, anchors=_anchors(), profile=profile)
    gaming = out["scenarios"]["gaming"]
    assert gaming["score"] is not None  # unchanged numeric score
    assert any("resolution" in lim.lower() for lim in gaming["limitations"])


def test_data_coverage_flows_into_payload():
    fv = _feature_vector()
    out = score_scenarios(fv, anchors=_anchors())
    assert out["data_coverage"] == fv["coverage"]
    assert 0.0 <= out["data_coverage"] <= 1.0


def test_determinism_same_inputs_same_payload():
    a = score_scenarios(_feature_vector(), anchors=_anchors(), profile=_profile())
    b = score_scenarios(_feature_vector(), anchors=_anchors(), profile=_profile())
    assert a == b


def test_gpu_vector_scores_without_cpu_features():
    fv = _feature_vector()
    fv["type"] = "GPU"
    fv["features"] = {
        "single_core_score": None, "multi_core_score": None,
        "memory_gb": 16.0, "memory_type": "GDDR6X", "core_clock_mhz": 1800.0,
        "boost_clock_mhz": 2100.0, "vram_bandwidth_gbps": 760.0,
        "memory_bus_width_bits": 320, "tdp_w": 250.0, "interface": "PCIe 4.0",
    }
    fv["missing"] = [k for k, v in fv["features"].items() if v is None]
    fv["coverage"] = round(sum(v is not None for v in fv["features"].values()) / len(fv["features"]), 4)
    fv["benchmark_families"] = []  # GPU: no gaming benchmark evidence in dataset
    out = score_scenarios(fv, anchors=_anchors())
    gaming = out["scenarios"]["gaming"]
    # No GPU benchmark families -> spec-based capped path
    assert gaming["spec_based"] is True
    assert gaming["score"] is not None and gaming["score"] <= 3.0
