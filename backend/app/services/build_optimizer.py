"""M4 Task 6: bounded build optimizer (M4-OPT-v1.0).

Single-component swap suggestions over an existing build context. Bounds:

- **One swap at a time**: each suggestion changes exactly one slot; the
  after-score is the targeted scenario score of the candidate in isolation.
  No multi-swap simulation is claimed.
- **Evidence-gated**: a CPU swap needs measured benchmark evidence; a GPU
  swap (no GPU benchmark data in this dataset) is spec-based and explicitly
  labeled, never presented as measured.
- **No fabrication**: no prices (budget never filters; VALUE scenario is
  UNKNOWN in this dataset), no FPS, no availability claims.
- **Compatibility passthrough**: candidate hints carry socket_compatible
  (True/False/None) from the same data the M32-RULES-v2 socket rule reads;
  a False candidate is labeled, never silently offered as compatible.
- **Deterministic**: ordering by (improvement desc, scenario score desc,
  hardware_id asc); identical inputs produce identical output.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware
from backend.app.services import build_intelligence_service
from backend.app.services.build_intelligence_service import (
    BUILD_INTELLIGENCE_VERSION,
    _load_hardware,
    _load_slot,
)
from backend.app.services.intelligence_features import features_from_hardware
from backend.app.services.scenario_scoring import score_scenarios
from backend.app.services.workload_profiles import (
    PROFILES,
    apply_preferences,
    resolve_profile,
)

OPTIMIZER_VERSION = "M4-OPT-v1.0"

_MAX_SWAPS_PER_SLOT = 3


def _candidate_universe(session, slot: str):
    return _load_slot(session, slot)


def _relevant_scenario(profile_key: str | None) -> str:
    profile = resolve_profile(profile_key)
    weights = profile.scenario_weights or {}
    positive = {s: w for s, w in weights.items() if w}
    if not positive:
        return "daily"
    return max(positive, key=positive.get)


def _scenario_weighted(profile, scenarios: dict) -> float | None:
    weighted = 0.0
    total = 0.0
    for scenario, weight in profile.scenario_weights.items():
        entry = scenarios.get(scenario)
        if entry is None or entry.get("score") is None or not weight:
            continue
        weighted += entry["score"] * weight
        total += weight
    return round(weighted / total, 4) if total else None


def _swap_for_slot(session, slot: str, components: dict, profile,
                   anchors, power_limit_w) -> list[dict]:
    component = components.get(slot) or {}
    features = component.get("_features")
    if features is None:
        return []
    relevant = _relevant_scenario(profile.key)
    current_payload = score_scenarios(
        features, anchors=anchors,
        profile={"scenario_weights": profile.scenario_weights},
    )
    current_scenarios = current_payload["scenarios"]
    current_entry = current_scenarios.get(relevant, {})
    current_score = current_entry.get("score")
    if current_score is None:
        return []
    current_effective = _scenario_weighted(profile, current_scenarios)
    evidence_basis = "benchmark" if current_entry.get("spec_based") is False else "spec"

    current_socket = (features.get("features") or {}).get("socket")
    exclude_ids = {component["hardware_id"]}

    swaps = []
    for hw in _candidate_universe(session, slot):
        if hw.id in exclude_ids:
            continue
        cand_features = features_from_hardware(hw)
        cand_payload = score_scenarios(
            cand_features, anchors=anchors,
            profile={"scenario_weights": profile.scenario_weights},
        )
        cand_scenarios = cand_payload["scenarios"]
        cand_entry = cand_scenarios.get(relevant, {})
        cand_score = cand_entry.get("score")
        if cand_score is None or cand_score <= current_score:
            continue
        cand_effective = _scenario_weighted(profile, cand_scenarios)
        if (cand_effective is None) != (current_effective is None):
            continue
        if cand_effective is not None and cand_effective < current_effective:
            continue
        cand_fv = cand_features.get("features") or {}
        socket_compatible = None
        if current_socket and cand_fv.get("socket"):
            socket_compatible = (cand_fv["socket"] == current_socket)
        tdp = cand_fv.get("tdp_w")
        trade_offs = []
        if slot == "gpu":
            trade_offs.append(
                "candidate scored from listed specs only; no GPU benchmark "
                "data exists in this dataset"
            )
        if power_limit_w and tdp is not None and float(tdp) > float(power_limit_w):
            # power_limit_w is advisory: labeled, and the candidate is
            # withheld from swaps because the listed TDP exceeds it.
            continue
        if power_limit_w and tdp is None:
            trade_offs.append(
                "candidate listed TDP unknown; power limit could not be "
                "checked (advisory, not measured draw)"
            )
        if tdp is not None:
            trade_offs.append(f"candidate listed TDP {tdp:g} W")
        if socket_compatible is False:
            trade_offs.append(
                "candidate socket differs from the selected CPU socket; "
                "replacing both may be required"
            )
        swaps.append({
            "target_slot": slot,
            "remove_hardware_id": component["hardware_id"],
            "remove_hardware_name": component["hardware_name"],
            "candidate_hint": {
                "hardware_id": hw.id,
                "hardware_name": hw.name,
                "socket_compatible": socket_compatible,
            },
            "before_score": current_score,
            "after_score": cand_score,
            "improvement": round(cand_score - current_score, 4),
            "scenario": relevant,
            "evidence_basis": evidence_basis,
            "rationale": (
                f"{relevant} score {cand_score:g} vs current "
                f"{current_score:g} "
                f"(from {'measured benchmark records' if evidence_basis == 'benchmark' else 'listed specs; no GPU benchmark data exists'})"
            ),
            "trade_offs": trade_offs,
        })
    swaps.sort(
        key=lambda s: (-s["improvement"], -s["after_score"],
                       s["candidate_hint"]["hardware_id"])
    )
    return swaps[:_MAX_SWAPS_PER_SLOT]


def optimize_build(component_ids: dict, profile_key: str | None = None,
                   budget_max: float | None = None,
                   power_limit_w: float | None = None,
                   priority: str | None = None,
                   anchors=None, session_factory=None) -> dict:
    """Bounded single-swap optimization suggestions for a build context.

    Read-only; composes the intelligence layer (features, scenarios,
    profiles) and the compatibility engine — no duplicated logic.
    """
    session_factory = session_factory or SessionLocal
    profile = resolve_profile(profile_key)
    prefs = {}
    if priority and priority != "balanced":
        profile = apply_preferences(profile, {"priority": priority})
        prefs["priority"] = priority

    provided = {k: v for k, v in (component_ids or {}).items() if v is not None}
    with session_factory() as session:
        components: dict[str, dict] = {}
        missing = [
            slot for slot, hw_id in provided.items()
            if _load_hardware(session, hw_id) is None
        ]
        if missing:
            raise LookupError(
                f"hardware id not found for slot(s): {', '.join(sorted(missing))}"
            )
        for slot, hw_id in provided.items():
            hw = _load_hardware(session, hw_id)
            components[slot] = {
                "hardware_id": hw.id,
                "hardware_name": hw.name,
                "type": hw.type,
            }
            if hw.type in ("CPU", "GPU"):
                features = features_from_hardware(hw)
                components[slot]["_features"] = features

        swaps: list[dict] = []
        for slot in ("cpu", "gpu"):
            swaps.extend(
                _swap_for_slot(session, slot, components, profile, anchors,
                               power_limit_w)
            )
        swaps.sort(
            key=lambda s: (-s["improvement"], -s["after_score"],
                           s["target_slot"], s["candidate_hint"]["hardware_id"])
        )

    echo = {
        "build": {
            "value": sorted(provided),
            "classification": (
                "unknown" if not provided else "hard"
            ),
            "notes": (
                ["empty build context: no swap can be evaluated"]
                if not provided else []
            ),
        },
        "profile_key": {
            "value": profile.key,
            "classification": "hard",
            "notes": [],
        },
        "budget_max": {
            "value": budget_max,
            "classification": "soft",
            "notes": (
                ["no price data in this dataset; budget never filters "
                 "candidates and no price claim is made"]
                if budget_max is not None else []
            ),
        },
        "power_limit_w": {
            "value": power_limit_w,
            "classification": "soft",
            "notes": (
                ["advisory: candidates with listed TDP above the limit are "
                 "withheld; unknown-TDP candidates are labeled, never "
                 "silently included"]
                if power_limit_w is not None else []
            ),
        },
        "priority": {
            "value": priority,
            "classification": "soft",
            "notes": (
                ["reweights profile scenario weights (documented bounds)"]
                if priority else []
            ),
        },
    }

    return {
        "optimizer_version": OPTIMIZER_VERSION,
        "build_intelligence_version": BUILD_INTELLIGENCE_VERSION,
        "swaps": swaps,
        "constraints_echo": echo,
        "profile": {
            "key": profile.key,
            "label": profile.label,
            "assumptions": list(profile.assumptions),
            "scenario_weights": dict(profile.scenario_weights),
        },
        "deterministic": True,
    }
