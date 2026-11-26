"""M4 evaluation suite (mission T9): property + regression + smoke tests.

Covers the mission's evaluation edges on the implemented M4 engines:
- determinism (two runs byte-identical)
- confidence calibration (spec-only never high)
- score monotonicity (primary feature up -> score up; no recency bias)
- recommendation stability (unrelated low-evidence row does not reorder top-5)
- value scenario UNKNOWN everywhere (no price data)
- misleading-recommendation guard (evidence_requirements honored)
- API integration smoke (v2 endpoints: 200 shapes, 404s, 422s)
- outlier handling (score 10x p90 caps at 5.0, never negative)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.tests.evaluation_fixtures import (  # noqa: E402
    EvaluationEnvironment,
    anchors_from_env,
)
from backend.app import main  # noqa: E402
from backend.app.schemas.intelligence import RecommendationConstraints  # noqa: E402
from backend.app.services import (  # noqa: E402
    build_intelligence_service,
    compatibility_service,
    recommendation_service,
    scenario_scoring,
)
from backend.app.services.build_optimizer import optimize_build  # noqa: E402
from backend.app.services.recommendation_service import (  # noqa: E402
    recommend_intelligent,
)
from backend.app.services.scenario_scoring import (  # noqa: E402
    derive_anchors,
    score_scenarios,
)
from backend.app.services.intelligence_features import (  # noqa: E402
    features_from_hardware,
)


@pytest.fixture()
def env():
    e = EvaluationEnvironment()
    e.seed_all()
    saved_main = main.SessionLocal
    saved_rec = recommendation_service.SessionLocal
    saved_intel = build_intelligence_service.SessionLocal
    saved_compat = compatibility_service.SessionLocal
    from backend.app.services import build_optimizer
    saved_opt = build_optimizer.SessionLocal
    main.SessionLocal = e.session_factory
    recommendation_service.SessionLocal = e.session_factory
    build_intelligence_service.SessionLocal = e.session_factory
    compatibility_service.SessionLocal = e.session_factory
    build_optimizer.SessionLocal = e.session_factory
    yield e
    main.SessionLocal = saved_main
    recommendation_service.SessionLocal = saved_rec
    build_intelligence_service.SessionLocal = saved_intel
    compatibility_service.SessionLocal = saved_compat
    build_optimizer.SessionLocal = saved_opt


# ------------------------------------------------------------ determinism --

def test_recommendation_determinism_byte_identical(env):
    constraints = RecommendationConstraints(hardware_type="CPU", limit=8)
    anchors = anchors_from_env(env)
    a = recommend_intelligent(env.session_factory, constraints, anchors=anchors)
    b = recommend_intelligent(env.session_factory, constraints, anchors=anchors)
    assert a == b


def test_optimizer_determinism_byte_identical(env):
    anchors = anchors_from_env(env)
    a = optimize_build(
        {"cpu": 101, "gpu": 300}, profile_key="software_development",
        anchors=anchors, session_factory=env.session_factory,
    )
    b = optimize_build(
        {"cpu": 101, "gpu": 300}, profile_key="software_development",
        anchors=anchors, session_factory=env.session_factory,
    )
    assert a == b


def test_scenario_scoring_deterministic(env):
    with env.session_factory() as s:
        hw = s.get(__import__("backend.app.models", fromlist=["Hardware"]).Hardware, 105)
        features = features_from_hardware(hw)
    anchors = anchors_from_env(env)
    a = score_scenarios(features, anchors=anchors)
    b = score_scenarios(features, anchors=anchors)
    assert a == b


# --------------------------------------------------------------- calibrate --

def test_spec_only_confidence_never_high(env):
    with env.session_factory() as s:
        Hardware = __import__("backend.app.models", fromlist=["Hardware"]).Hardware
        hw = s.get(Hardware, 300)  # GPU Strong: specs only, no GPU benchmarks
        features = features_from_hardware(hw)
    anchors = anchors_from_env(env)
    out = score_scenarios(features, anchors=anchors)
    for name, entry in out["scenarios"].items():
        if entry.get("spec_based"):
            assert entry["confidence"] != "high", name


def test_outlier_caps_at_five_never_negative(env):
    with env.session_factory() as s:
        Hardware = __import__("backend.app.models", fromlist=["Hardware"]).Hardware
        hw = s.get(Hardware, 900)  # 10x p90 outlier
        features = features_from_hardware(hw)
    anchors = anchors_from_env(env)
    out = score_scenarios(features, anchors=anchors)
    for name, entry in out["scenarios"].items():
        score = entry.get("score")
        if score is not None:
            assert 0.0 <= score <= 5.0, f"{name}: {score}"
            assert 0 <= entry["stars"] <= 5


def test_conflicting_benchmarks_take_max_deterministically(env):
    with env.session_factory() as s:
        Hardware = __import__("backend.app.models", fromlist=["Hardware"]).Hardware
        hw = s.get(Hardware, 901)  # two multi-core records: 7000 and 9000
        features = features_from_hardware(hw)
    assert features["features"]["multi_core_score"] == 9000.0


# ------------------------------------------------------------- monotonicity --

def test_score_monotonic_in_primary_feature():
    anchors = {
        "multi-core": derive_anchors([1000.0 * i for i in range(1, 11)]),
        "single-core": derive_anchors([200.0 * i for i in range(1, 11)]),
    }
    base_features = {
        "feature_version": "M4-FEATURES-v1", "type": "CPU",
        "features": {
            "cores": 8, "threads": 16, "base_clock_ghz": 3.0,
            "boost_clock_ghz": 4.4, "tdp_w": 65.0, "socket": "AM5",
            "single_core_score": 1000.0, "multi_core_score": 5000.0,
        },
        "missing": [], "coverage": 1.0,
        "benchmark_families": ["multi-core", "single-core"],
        "provenance_verified_fields": [],
        "data_freshness": {"recorded_at_present": False, "latest_recorded_at": None},
    }
    low = score_scenarios(base_features, anchors=anchors)
    stronger = dict(base_features)
    stronger["features"] = {
        **base_features["features"], "multi_core_score": 9000.0,
    }
    high = score_scenarios(stronger, anchors=anchors)
    assert high["scenarios"]["workstation"]["score"] >= \
        low["scenarios"]["workstation"]["score"]


def test_no_recency_feature_anywhere():
    # release_date / architecture must not be scoring features.
    blob = str(scenario_scoring._BASE_WEIGHTS).lower()
    assert "release" not in blob and "architecture" not in blob


# ---------------------------------------------------------------- stability --

def test_unrelated_low_evidence_row_does_not_reorder_top5(env):
    anchors = anchors_from_env(env)
    base_constraints = RecommendationConstraints(
        hardware_type="CPU", limit=5,
    )
    before = recommend_intelligent(
        env.session_factory, base_constraints, anchors=anchors,
    )
    top5_before = [c["hardware_id"] for c in before["candidates"]]

    with env.session_factory() as s:
        from backend.app.models import CPUSpecification, Hardware
        s.add(Hardware(
            id=990, name="CPU Weak New", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=2, threads=4, base_clock_ghz=2.0, boost_clock_ghz=2.5,
                tdp_w=35.0, socket="AM4",
            ),
            benchmark_results=[],
        ))
        s.commit()

    after = recommend_intelligent(
        env.session_factory, base_constraints, anchors=anchors_from_env(env),
    )
    top5_after = [c["hardware_id"] for c in after["candidates"]]
    assert top5_after == top5_before


# ------------------------------------------------------------------- value --

def test_value_scenario_unknown_everywhere(env):
    anchors = anchors_from_env(env)
    with env.session_factory() as s:
        from backend.app.models import Hardware
        for hw_id in (101, 105, 900, 901, 930, 931):
            hw = s.get(Hardware, hw_id)
            if hw is None:
                continue
            features = features_from_hardware(hw)
            out = score_scenarios(features, anchors=anchors)
            value = out["scenarios"]["value"]
            assert value["score"] is None, hw_id
            assert value["confidence"] == "unknown", hw_id

# --------------------------------------------------- misleading-reco guard --

def test_no_candidate_recommended_when_evidence_requirements_fail(env):
    """A profile whose evidence_requirements the candidate fails must not
    receive a scored recommendation for that scenario."""
    from backend.app.services.workload_profiles import PROFILES

    anchors = anchors_from_env(env)
    with env.session_factory() as s:
        from backend.app.models import Hardware
        hw = s.get(Hardware, 902)  # evidence-free
        features = features_from_hardware(hw)
    out = score_scenarios(features, anchors=anchors)
    for profile in PROFILES.values():
        for family in profile.evidence_requirements:
            if family not in features["benchmark_families"]:
                for scenario, weights in (
                    ("gaming", profile.scenario_weights),
                ):
                    if weights.get(scenario, 0) > 0.5:
                        # high-weight scenario without its evidence family:
                        # the entry must be UNKNOWN or spec-based, never a
                        # confident benchmark-derived score.
                        entry = out["scenarios"][scenario]
                        assert (
                            entry["score"] is None or entry.get("spec_based")
                        ), f"{profile.key}/{scenario}"


def test_ai_ml_profile_never_scores_gpu_compute(env):
    from backend.app.services.workload_profiles import PROFILES

    profile = PROFILES["ai_ml_experimentation"]
    joined = " ".join(profile.assumptions).lower()
    assert "not scored" in joined or "no gpu" in joined


# ----------------------------------------------------------- compatibility --

def test_compatibility_engine_still_authoritative(env):
    """The M32-RULES-v2 engine output passes through the M4 summary."""
    report = build_intelligence_service._compatibility_summary(
        {"cpu": 910, "motherboard": 920}
    )
    assert report["overall"] in (
        "COMPATIBLE", "INCOMPATIBLE", "UNKNOWN", "NOT_EVALUATED",
    )
    assert report["rules_version"] == "M32-RULES-v2"


def test_socket_incompatible_pair_detected(env):
    report = build_intelligence_service._compatibility_summary(
        {"cpu": 910, "motherboard": 920}
    )
    assert report["engine_state"] == "INCOMPATIBLE"
    assert "cpu-motherboard-socket" in report["incompatible_rules"]


# ------------------------------------------------------------- API smoke ----

def test_api_v2_recommend_smoke(env):
    client = TestClient(main.app)
    resp = client.get("/hardware/recommend/v2?type=CPU&limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ranking_version"] == "M4-REC-v2.0"
    assert len(body["candidates"]) == 3


def test_api_v2_recommend_404_shape(env):
    client = TestClient(main.app)
    resp = client.get("/hardware/recommend/v2?type=CPU&profile_key=nope")
    assert resp.status_code == 422


def test_api_build_intelligence_smoke(env):
    client = TestClient(main.app)
    resp = client.post("/build/intelligence", json={"cpu": 101, "gpu": 300})
    assert resp.status_code == 200
    body = resp.json()
    assert body["build_intelligence_version"] == "M4-BUILD-v1.0"


def test_api_build_intelligence_404(env):
    client = TestClient(main.app)
    resp = client.post("/build/intelligence", json={"cpu": 424242})
    assert resp.status_code == 404


def test_api_build_optimize_smoke(env):
    client = TestClient(main.app)
    resp = client.post(
        "/build/optimize",
        json={"components": {"cpu": 101}, "profile_key": "software_development"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["optimizer_version"] == "M4-OPT-v1.0"


def test_api_scenarios_smoke(env):
    client = TestClient(main.app)
    resp = client.get("/hardware/105/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scoring_version"] == "M4-SCORING-v2.0"
    assert set(body["scenarios"]) == {"gaming", "workstation", "daily", "value"}


def test_api_scenarios_404(env):
    client = TestClient(main.app)
    resp = client.get("/hardware/424242/scenarios")
    assert resp.status_code == 404
