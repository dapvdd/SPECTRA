"""M4 Task 3: workload profiles (eight configurable profiles).

Covers backend/app/services/workload_profiles.py:
- exactly the eight mission profile keys, weights sum to 1.0
- resolve_profile default + unknown-key error
- preference validation (resolution gaming-only; priority bounded reweight;
  budget_max/power_limit_w/existing_components accepted)
- every profile carries documented assumptions
- integration with scenario_scoring.score_scenarios
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.services.workload_profiles import (  # noqa: E402
    PROFILES,
    PROFILE_KEYS,
    WORKLOAD_PROFILE_VERSION,
    apply_preferences,
    resolve_profile,
)
from backend.app.services.scenario_scoring import (  # noqa: E402
    SCENARIOS,
    score_scenarios,
)

EXPECTED_KEYS = (
    "esports_gaming", "aaa_gaming", "general_productivity",
    "software_development", "video_editing", "rendering_3d",
    "virtualization_homelab", "ai_ml_experimentation",
)


def test_profile_version_pinned():
    assert WORKLOAD_PROFILE_VERSION == "M4-PROFILES-v1.0"


def test_eight_profile_keys_exact():
    assert set(PROFILE_KEYS) == set(EXPECTED_KEYS)
    assert len(PROFILES) == 8


def test_every_profile_weights_sum_to_one():
    for key, profile in PROFILES.items():
        total = sum(profile.scenario_weights.get(s, 0.0) for s in SCENARIOS)
        assert abs(total - 1.0) < 1e-9, f"{key}: {total}"
        # unknown scenario keys never appear
        assert set(profile.scenario_weights) <= set(SCENARIOS)


def test_every_profile_documents_assumptions():
    for key, profile in PROFILES.items():
        assert profile.assumptions, key
        assert len(profile.assumptions) >= 2, key
        assert any("no " in a.lower() or "not " in a.lower() or "never" in a.lower()
                   for a in profile.assumptions), key


def test_gaming_profiles_declare_resolution_support():
    for key in ("esports_gaming", "aaa_gaming"):
        assert "resolution" in PROFILES[key].supported_preferences
    for key in ("video_editing", "ai_ml_experimentation"):
        assert "resolution" not in PROFILES[key].supported_preferences


def test_resolve_profile_default_is_general_productivity():
    assert resolve_profile(None).key == "general_productivity"
    assert resolve_profile(None) is PROFILES["general_productivity"]


def test_resolve_profile_unknown_key_raises():
    with pytest.raises(KeyError):
        resolve_profile("quantum_mining")


def test_apply_preferences_resolution_on_non_gaming_raises():
    with pytest.raises(ValueError):
        apply_preferences(PROFILES["video_editing"], {"resolution": "4k"})


def test_apply_preferences_resolution_accepted_on_gaming():
    p = apply_preferences(PROFILES["esports_gaming"], {"resolution": "1440p"})
    assert p.preferences == {"resolution": "1440p"}


def test_apply_preferences_budget_and_power_accepted():
    p = apply_preferences(PROFILES["general_productivity"], {"budget_max": 900})
    assert p.preferences == {"budget_max": 900}
    p2 = apply_preferences(PROFILES["rendering_3d"], {"power_limit_w": 500})
    assert p2.preferences == {"power_limit_w": 500}


def test_apply_preferences_unknown_pref_raises():
    with pytest.raises(ValueError):
        apply_preferences(PROFILES["general_productivity"], {"vibes": "max"})


def test_apply_preferences_priority_reweights_within_bounds():
    base = PROFILES["general_productivity"]
    p = apply_preferences(base, {"priority": "performance"})
    for scenario in SCENARIOS:
        base_w = base.scenario_weights.get(scenario, 0.0)
        new_w = p.scenario_weights.get(scenario, 0.0)
        if base_w > 0:
            assert new_w > 0
    # priorities differ between performance and efficiency
    pe = apply_preferences(base, {"priority": "efficiency"})
    diffs = [
        abs(p.scenario_weights[s] - pe.scenario_weights[s])
        for s in SCENARIOS
        if s in p.scenario_weights and s in pe.scenario_weights
    ]
    assert max(diffs) > 0
    for profile in (p, pe):
        assert abs(sum(profile.scenario_weights.values()) - 1.0) < 1e-9


def test_apply_preferences_frozen_returns_new_profile():
    base = PROFILES["esports_gaming"]
    p = apply_preferences(base, {"resolution": "4k"})
    assert p is not base
    assert base.preferences == {}


def test_profiles_integrate_with_scenario_scoring():
    profile = PROFILES["software_development"]
    payload = score_scenarios(
        {
            "feature_version": "M4-FEATURES-v1", "type": "CPU",
            "features": {"single_core_score": 1500.0, "multi_core_score": 9000.0,
                         "cores": 8, "threads": 16, "base_clock_ghz": 3.0,
                         "boost_clock_ghz": 4.4, "tdp_w": 65.0,
                         "efficiency": 138.46, "socket": "AM5",
                         "process_node_nm": 5.0},
            "missing": [], "coverage": 1.0,
            "benchmark_families": ["multi-core", "single-core"],
            "provenance_verified_fields": [], 
            "data_freshness": {"recorded_at_present": False, "latest_recorded_at": None},
        },
        anchors={
            "single-core": (666.6, 982.2, 1324.5, 1637.0, 2016.4),
            "multi-core": (1408.1, 2792.0, 4996.5, 7999.0, 12311.2),
        },
        profile=profile.__dict__,
    )
    assert payload["scenarios"]["workstation"]["score"] is not None


def test_ai_ml_profile_documents_absent_gpu_evidence():
    profile = PROFILES["ai_ml_experimentation"]
    joined = " ".join(profile.assumptions).lower()
    assert "gpu" in joined or "no gpu" in joined
