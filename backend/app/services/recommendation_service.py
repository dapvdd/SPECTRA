"""Deterministic, evidence-grounded hardware recommendation engine (Objective E).

Recommendations rank hardware for a workload. Ranking is derived ONLY from the
suitability rating and evidence quality we can actually observe; no benchmark
score, FPS, or price is ever fabricated. Candidates must clear an evidence
threshold to be recommended at all, so hardware we cannot rate confidently is
excluded rather than guessed at.

Budget filtering is deliberately NOT implemented in this delivery: this dataset
carries no price data, so ``budget_max`` is accepted but has no effect
(documented as deferred in docs/EVIDENCE_GAPS.md).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.database import SessionLocal
from backend.app.models import Hardware
from backend.app.schemas.suitability import rating_to_response
from backend.app.services.suitability_service import rate_suitability

def _load_candidates(session, hardware_type: str):
    """Load hardware of a given type with specs + benchmarks eager-loaded."""
    return list(
        session.scalars(
            select(Hardware)
            .where(Hardware.type == hardware_type)
            .options(
                selectinload(Hardware.cpu_specification),
                selectinload(Hardware.gpu_specification),
                selectinload(Hardware.benchmark_results),
                selectinload(Hardware.field_provenance),
                selectinload(Hardware.external_identifiers),
            )
        ).all()
    )


def _passes_threshold(rating: dict) -> bool:
    """A candidate is recommended only if we can rate it with usable evidence.

    Excludes ``unrated`` hardware outright. Otherwise requires either high
    evidence confidence OR a solid suitability score (>= 3 stars) — we never
    recommend hardware where both the evidence and the score are weak.
    """
    if rating["confidence"] == "unrated":
        return False
    if rating["confidence"] == "high":
        return True
    return rating["stars"] >= 3


def recommend(
    hardware_type: str,
    workload: str,
    budget_max: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return top ``limit`` hardware recommendations for a workload.

    Filtering: hardware of ``hardware_type`` (CPU/GPU) whose suitability for
    ``workload`` passes the evidence threshold. Ranking: stars descending,
    then evidence-quality score descending. ``budget_max`` is accepted for API
    compatibility but has no effect (no price data in this dataset).
    """
    with SessionLocal() as session:
        hardware_list = _load_candidates(session, hardware_type)

    rated: list[dict] = []
    for hardware in hardware_list:
        rating = rate_suitability(hardware, workload)
        if _passes_threshold(rating):
            explanation = list(rating["rationale"])
            rated.append(
                {
                    "hardware": {
                        "id": hardware.id,
                        "name": hardware.name,
                        "type": hardware.type,
                    },
                    "suitability": rating,
                    "evidence_score": rating["evidence_quality"]["score"],
                    "explanation": explanation,
                }
            )

    # Rank: stars desc, then evidence-quality score desc.
    ranked = sorted(
        rated,
        key=lambda item: (
            item["suitability"]["stars"],
            item["evidence_score"],
        ),
        reverse=True,
    )

    return ranked[:limit]


def recommend_response(
    hardware_type: str,
    workload: str,
    budget_max: int | None = None,
    limit: int = 10,
) -> dict:
    """Build the full recommendation response payload (service -> wire)."""
    ranked = recommend(
        hardware_type, workload, budget_max=budget_max, limit=limit
    )

    candidates = [
        {
            "hardware_id": item["hardware"]["id"],
            "hardware_name": item["hardware"]["name"],
            "hardware_type": item["hardware"]["type"],
            "suitability": rating_to_response(item["suitability"]),
            "explanation": item["explanation"],
        }
        for item in ranked
    ]

    filter_reason = None
    if not candidates:
        if workload == "ai_ml":
            filter_reason = (
                "no candidates passed evidence threshold: "
                "ai_ml has no GPU/VRAM benchmark evidence"
            )
        else:
            filter_reason = (
                "no candidates passed evidence threshold"
            )

    return {
        "candidates": candidates,
        "filter_reason": filter_reason,
        "budget_max": budget_max,
    }


# ---------------------------------------------------------------------------
# M4 Task 4: intelligent recommendations (M4-REC-v2.0) — additive layer.
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402

from backend.app.services.compatibility_rules import (  # noqa: E402
    rule_cpu_motherboard_socket,
)
from backend.app.services.scenario_scoring import SCENARIOS, score_scenarios  # noqa: E402
from backend.app.services.workload_profiles import (  # noqa: E402
    apply_preferences,
    resolve_profile,
)
from backend.app.services.intelligence_features import features_from_hardware  # noqa: E402

RANKING_VERSION = "M4-REC-v2.0"

# Alternatives = candidates ranked after the primary list (same ranking).
_ALTERNATIVES_POOL = 5


@dataclass
class RecommendationConstraints:
    """Internal (non-wire) constraint object used by recommend_intelligent."""

    hardware_type: str
    profile_key: str | None = None
    budget_max: float | None = None
    resolution: str | None = None
    power_limit_w: float | None = None
    priority: str | None = None
    existing_components: dict = field(default_factory=dict)
    limit: int = 10


def _load_candidates_v2(session, hardware_type: str):
    """Eager-load candidates with the relationships the feature layer reads."""
    return list(
        session.scalars(
            select(Hardware)
            .where(Hardware.type == hardware_type)
            .options(
                selectinload(Hardware.cpu_specification),
                selectinload(Hardware.gpu_specification),
                selectinload(Hardware.benchmark_results),
                selectinload(Hardware.field_provenance),
            )
        ).all()
    )


def _load_motherboard_specs(session, motherboard_id: int):
    row = session.execute(
        select(Hardware).where(
            (Hardware.id == motherboard_id) & (Hardware.type == "MOTHERBOARD")
        )
    ).scalars().first()
    if row is None:
        return None
    spec = row.motherboard_specification
    if spec is None:
        return {"hardware_id": row.id, "name": row.name}
    return {
        "hardware_id": row.id, "name": row.name, "socket": spec.socket,
    }


def _socket_exclude(session, constraints, candidates):
    """Hard-exclude socket mismatches vs an existing motherboard.

    Reuses the M32-RULES-v2 rule function verbatim (no duplicated logic).
    Missing socket data -> NO exclusion (UNKNOWN is disclosed, never guessed).
    """
    motherboard_id = (constraints.existing_components or {}).get("motherboard")
    if not motherboard_id or not candidates:
        return [], []
    board = _load_motherboard_specs(session, motherboard_id)
    if board is None:
        return [], [{
            "constraint": "existing_components.motherboard",
            "note": f"motherboard id {motherboard_id} not found or not a "
                    "MOTHERBOARD; socket compatibility not evaluated",
        }]
    excluded, unknown_notes = [], []
    for cand in candidates:
        cpu_socket = (cand["features"].get("features") or {}).get("socket")
        ids = {"cpu": cand["hardware_id"], "motherboard": board["hardware_id"]}
        result = rule_cpu_motherboard_socket(
            {"socket": cpu_socket}, {"socket": board.get("socket")}, ids=ids,
        )
        if result.state.value == "INCOMPATIBLE":
            excluded.append({
                "hardware_id": cand["hardware_id"],
                "hardware_name": cand["hardware_name"],
                "reason_code": "SOCKET_MISMATCH",
                "reason": result.explanation,
            })
        elif result.state.value == "UNKNOWN":
            unknown_notes.append(
                f"{cand['hardware_name']}: socket compatibility unknown "
                f"({result.reason_code})"
            )
    return excluded, unknown_notes


def _power_exclude(candidates, power_limit_w):
    """Advisory power filter: exclude only with documented TDP evidence."""
    excluded, unknown_notes = [], []
    if power_limit_w is None:
        return excluded, unknown_notes
    for cand in candidates:
        tdp = (cand["features"].get("features") or {}).get("tdp_w")
        if tdp is None:
            unknown_notes.append(
                f"{cand['hardware_name']}: TDP unknown; power limit not applied"
            )
        elif float(tdp) > float(power_limit_w):
            excluded.append({
                "hardware_id": cand["hardware_id"],
                "hardware_name": cand["hardware_name"],
                "reason_code": "POWER_LIMIT_EXCEEDED",
                "reason": (
                    f"listed TDP {tdp:g} W exceeds requested power limit "
                    f"{power_limit_w:g} W (listed TDP, not measured draw)"
                ),
            })
    return excluded, unknown_notes


def _score_candidates(candidates, anchors, profile, prefs):
    """Score each candidate via scenario_scoring; returns scored list."""
    scored = []
    profile_payload = None
    if profile is not None:
        profile_payload = {
            "key": profile.key,
            "label": profile.label,
            "assumptions": list(profile.assumptions),
            "scenario_weights": dict(profile.scenario_weights),
        }
    for cand in candidates:
        payload = score_scenarios(
            cand["features"], anchors=anchors,
            profile={"scenario_weights": profile.scenario_weights,
                     "preferences": prefs} if profile else None,
        )
        scenarios = payload["scenarios"]
        weighted = 0.0
        weight_total = 0.0
        for scenario, weight in (profile.scenario_weights if profile else
                                 {"gaming": 0.5, "workstation": 0.3,
                                  "daily": 0.2, "value": 0.0}).items():
            entry = scenarios.get(scenario)
            if entry is None or entry["score"] is None or not weight:
                continue
            weighted += entry["score"] * weight
            weight_total += weight
        effective = round(weighted / weight_total, 4) if weight_total else None
        scored.append({**cand, "scenario_payload": payload,
                       "effective_score": effective})
    return scored, profile_payload


def _rank_explanation(cand, profile) -> list[str]:
    explanation = []
    effective = cand.get("effective_score")
    if effective is not None:
        explanation.append(
            f"weighted scenario score {effective:g} across the profile's "
            "scenarios (score=None scenarios excluded from the blend)"
        )
    scores = cand["scenario_payload"]["scenarios"]
    for scenario in SCENARIOS:
        entry = scores.get(scenario) or {}
        if entry.get("score") is not None:
            explanation.append(
                f"{scenario}: score {entry['score']:g} "
                f"({entry['confidence']}"
                f"{', spec-based' if entry.get('spec_based') else ''})"
            )
        elif entry.get("limitations"):
            explanation.append(f"{scenario}: unknown — {entry['limitations'][0]}")
    if cand.get("features", {}).get("data_freshness", {}).get(
            "recorded_at_present"):
        explanation.append("benchmark freshness recorded (see data_freshness)")
    return explanation


def _trade_offs(cand) -> list[str]:
    trade_offs = []
    scenarios = cand["scenario_payload"]["scenarios"]
    fv = cand.get("features", {}).get("features") or {}
    if fv.get("efficiency") is not None:
        trade_offs.append(
            f"efficiency {fv['efficiency']:g} score/W (derived from listed TDP)"
        )
    if fv.get("tdp_w") is not None:
        trade_offs.append(f"listed TDP {fv['tdp_w']:g} W")
    if scenarios.get("value", {}).get("confidence") == "unknown":
        trade_offs.append("value unknown: no price data in this dataset")
    return trade_offs


# Candidate-level confidence = the strongest confidence among SCORED
# scenarios (ordered high > medium > low > unknown). Unknown scenarios
# never dominate the aggregate; a fully-unknown candidate stays unknown.
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "unknown": 0}


def _aggregate_confidence(scenarios: dict) -> str:
    scored = [
        entry.get("confidence")
        for entry in scenarios.values()
        if entry.get("score") is not None
    ]
    if not scored:
        return "unknown"
    return max(scored, key=lambda c: _CONFIDENCE_RANK.get(c, -1))


def recommend_intelligent(session_factory, constraints, anchors=None):
    """Deterministic, explainable ranked recommendations (M4-REC-v2.0).

    Adds to v1: constraint classification, profile integration, exclusion
    ledger with reason codes, alternatives, deterministic tie-breaks.
    The v1 functions above remain byte-identical in behavior.
    """
    profile = resolve_profile(constraints.profile_key)
    prefs = dict(profile.preferences or {})
    if constraints.resolution:
        prefs["resolution"] = constraints.resolution
    if constraints.priority and constraints.priority != "balanced":
        profile = apply_preferences(profile, {"priority": constraints.priority})
        prefs.update(profile.preferences or {})

    with session_factory() as session:
        raw = _load_candidates_v2(session, constraints.hardware_type)
        motherboard_note = None
        if (constraints.existing_components or {}).get("motherboard"):
            board = _load_motherboard_specs(
                session, constraints.existing_components["motherboard"]
            )
            if board is None:
                motherboard_note = (
                    f"motherboard id "
                    f"{constraints.existing_components['motherboard']} not "
                    "found or not a MOTHERBOARD; socket compatibility not "
                    "evaluated"
                )

    candidates = []
    excluded: list[dict] = []
    for hw in raw:
        features = features_from_hardware(hw)
        fv = features["features"]
        # Evidence gate (v1-compatible): need at least one benchmark family
        # or a usable spec/provenance signal.
        if features["coverage"] <= 0.0 and not features["benchmark_families"]:
            excluded.append({
                "hardware_id": hw.id,
                "hardware_name": hw.name,
                "reason_code": "insufficient_data:no_evidence",
                "reason": "no specs, benchmarks, or provenance evidence",
            })
            continue
        candidates.append({
            "hardware_id": hw.id,
            "hardware_name": hw.name,
            "hardware_type": hw.type,
            "features": features,
        })

    socket_excluded, socket_notes = _socket_exclude(session, constraints, candidates)
    excluded.extend(socket_excluded)
    power_excluded, power_notes = _power_exclude(
        candidates, constraints.power_limit_w
    )
    excluded.extend(power_excluded)
    excluded_ids = {e["hardware_id"] for e in excluded}
    candidates = [c for c in candidates if c["hardware_id"] not in excluded_ids]

    scored, profile_payload = _score_candidates(
        candidates, anchors, profile, prefs
    )

    def sort_key(item):
        eff = item["effective_score"]
        coverage = item["features"]["coverage"]
        return (
            -(eff if eff is not None else -1.0),
            -coverage,
            item["hardware_id"],  # deterministic tie-break
        )

    scored.sort(key=sort_key)
    ranked = scored[: constraints.limit]
    alternatives = scored[constraints.limit:
                          constraints.limit + _ALTERNATIVES_POOL]

    def to_candidate(item, rank):
        return {
            "rank": rank,
            "hardware_id": item["hardware_id"],
            "hardware_name": item["hardware_name"],
            "hardware_type": item["hardware_type"],
            "scenario_scores": item["scenario_payload"]["scenarios"],
            "stars": max(
                (s.get("stars", 0)
                 for s in item["scenario_payload"]["scenarios"].values()),
                default=0,
            ),
            "confidence": _aggregate_confidence(
                item["scenario_payload"]["scenarios"]
            ),
            "rank_explanation": _rank_explanation(item, profile),
            "trade_offs": _trade_offs(item),
            "evidence": {
                "coverage": item["features"]["coverage"],
                "benchmark_families": item["features"]["benchmark_families"],
                "provenance_verified_fields":
                    item["features"]["provenance_verified_fields"],
                "data_freshness": item["features"]["data_freshness"],
            },
        }

    candidates_out = [to_candidate(item, i + 1)
                      for i, item in enumerate(ranked)]
    alternatives_out = [
        to_candidate(item, constraints.limit + i + 1)
        for i, item in enumerate(alternatives)
    ]

    # ---- constraints echo (classification vocabulary: hard/soft/unknown) ----
    echo: dict[str, dict] = {
        "hardware_type": {"value": constraints.hardware_type,
                          "classification": "hard", "notes": []},
        "profile_key": {"value": constraints.profile_key or "general_productivity",
                        "classification": "hard", "notes": []},
        "budget_max": {
            "value": constraints.budget_max,
            "classification": "soft",
            "notes": [
                "no price data in this dataset; budget never filters "
                "candidates and value scenario is UNKNOWN"
            ] if constraints.budget_max is not None else [],
        },
        "resolution": {
            "value": constraints.resolution,
            "classification": "soft",
            "notes": [
                "advisory context; no GPU gaming benchmark evidence, so "
                "resolution never adjusts numeric scores"
            ] if constraints.resolution else [],
        },
        "power_limit_w": {
            "value": constraints.power_limit_w,
            "classification": "soft",
            "notes": power_notes or (
                ["advisory: excludes only candidates with documented listed "
                 "TDP above the limit"] if constraints.power_limit_w else []
            ),
        },
        "priority": {
            "value": constraints.priority,
            "classification": "soft",
            "notes": ["reweights profile scenario weights (documented bounds)"]
            if constraints.priority else [],
        },
        "existing_components": {
            "value": constraints.existing_components,
            "classification": "unknown" if motherboard_note else "hard",
            "notes": [motherboard_note] if motherboard_note else (
                ["socket compatibility evaluated via M32-RULES-v2 where data "
                 "allows; UNKNOWN never excludes"]
                if constraints.existing_components else []
            ),
        },
    }

    return {
        "candidates": candidates_out,
        "alternatives": alternatives_out,
        "excluded": excluded[:25],
        "constraints_echo": echo,
        "profile": profile_payload or {
            "key": profile.key, "label": profile.label,
            "assumptions": list(profile.assumptions),
            "scenario_weights": dict(profile.scenario_weights),
        },
        "ranking_version": RANKING_VERSION,
        "deterministic": True,
    }
