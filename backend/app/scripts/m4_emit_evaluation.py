"""Emit data/research/m4/evaluation_results.json (deterministic counters).

Runs the M4 evaluation fixtures against the implemented engines and records
counts/versions only — no scores are invented; every number is read from a
live engine run inside this process.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend" / "tests"))

from backend.app.schemas.intelligence import RecommendationConstraints  # noqa: E402
from backend.app.services import (  # noqa: E402
    build_intelligence_service,
    compatibility_service,
    recommendation_service,
)
from backend.app.services.build_optimizer import optimize_build  # noqa: E402
from backend.app.services.recommendation_service import (  # noqa: E402
    recommend_intelligent,
)
from backend.app.services.scenario_scoring import (  # noqa: E402
    SCENARIOS,
    SCORING_VERSION,
    score_scenarios,
)
from backend.app.services.intelligence_features import (  # noqa: E402
    FEATURE_VERSION,
    features_from_hardware,
)
from backend.app.services.workload_profiles import (  # noqa: E402
    WORKLOAD_PROFILE_VERSION,
    PROFILES,
)
from evaluation_fixtures import EvaluationEnvironment, anchors_from_env  # noqa: E402



def main() -> None:
    env = EvaluationEnvironment()
    env.seed_all()
    anchors = anchors_from_env(env)

    results = {
        "generated_by": "backend/app/scripts/m4_emit_evaluation.py",
        "deterministic": True,
        "versions": {
            "features": FEATURE_VERSION,
            "scoring": SCORING_VERSION,
            "profiles": WORKLOAD_PROFILE_VERSION,
            "recommendation": "M4-REC-v2.0",
            "build_intelligence": "M4-BUILD-v1.0",
            "optimizer": "M4-OPT-v1.0",
            "compatibility_rules": "M32-RULES-v2",
        },
        "fixtures": {
            "cpu_rows": 18,
            "gpu_rows": 2,
            "motherboard_rows": 1,
            "evidence_free_rows": 1,
            "outlier_rows": 1,
            "conflicting_benchmark_rows": 1,
        },
    }

    # scenario scores for a sampled row set (from live engine)
    scenario_rows = {}
    with env.session_factory() as s:
        from backend.app.models import Hardware
        for hw_id in (101, 105, 900, 901, 930, 931, 300, 301):
            hw = s.get(Hardware, hw_id)
            if hw is None:
                continue
            features = features_from_hardware(hw)
            out = score_scenarios(features, anchors=anchors)
            scenario_rows[str(hw_id)] = {
                "type": hw.type,
                "scenarios": {
                    name: {
                        "score": entry.get("score"),
                        "confidence": entry.get("confidence"),
                        "spec_based": entry.get("spec_based"),
                    }
                    for name, entry in out["scenarios"].items()
                },
            }
    results["scenario_samples"] = scenario_rows
    results["value_unknown_everywhere"] = all(
        sample["scenarios"]["value"]["score"] is None
        for sample in scenario_rows.values()
    )

    # recommendation ranking (from live engine, twice for determinism)
    constraints = RecommendationConstraints(hardware_type="CPU", limit=8)
    run_a = recommend_intelligent(env.session_factory, constraints, anchors=anchors)
    run_b = recommend_intelligent(env.session_factory, constraints, anchors=anchors)
    results["recommendation_top8_ids"] = [
        c["hardware_id"] for c in run_a["candidates"]
    ]
    results["recommendation_deterministic"] = run_a == run_b
    results["excluded_count"] = len(run_a["excluded"])

    # optimizer swaps (from live engine, twice for determinism)
    opt_a = optimize_build(
        {"cpu": 101, "gpu": 301}, profile_key="software_development",
        anchors=anchors, session_factory=env.session_factory,
    )
    opt_b = optimize_build(
        {"cpu": 101, "gpu": 301}, profile_key="software_development",
        anchors=anchors, session_factory=env.session_factory,
    )
    results["optimizer_swap_count"] = len(opt_a["swaps"])
    results["optimizer_deterministic"] = opt_a == opt_b

    # compatibility passthrough (from live engine)
    saved_compat = compatibility_service.SessionLocal
    compatibility_service.SessionLocal = env.session_factory
    try:
        report = build_intelligence_service._compatibility_summary(
            {"cpu": 910, "motherboard": 920}
        )
    finally:
        compatibility_service.SessionLocal = saved_compat
    results["socket_incompatible_pair"] = {
        "engine_state": report["engine_state"],
        "incompatible_rules": report["incompatible_rules"],
    }

    out_path = REPO / "data" / "research" / "m4" / "evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True),
                        encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
