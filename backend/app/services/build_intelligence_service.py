"""M4 Task 5: build intelligence service (M4-BUILD-v1.0).

Composes — never duplicates — the existing M2/M2.5/M3 engines:

- **Compatibility** is delegated verbatim to
  ``compatibility_service.check_build_compatibility`` (M32-RULES-v2). This
  module adds only a summary mapping; the aggregate semantics stay the
  engine's own (any INCOMPATIBLE -> INCOMPATIBLE; else any UNKNOWN ->
  UNKNOWN; else COMPATIBLE; no rules -> UNKNOWN). Partial builds can never
  be COMPATIBLE: with required slots missing the summary downgrades
  COMPATIBLE to UNKNOWN and names the missing slots.

- **Balance** is graded from measured benchmark evidence only. There is no
  bottleneck percentage anywhere in this module: classifications are
  qualitative (cpu_bound/gpu_bound/balanced) with an uncertainty grade, and
  no classification is emitted when either side lacks benchmark evidence
  (basis=insufficient, classification=unknown).

- **Power** follows the M2.5 two-tier policy: the reference is the same
  arithmetic as ``rule_psu_build_wattage`` (sum of listed TDPs plus
  PSU_TDP_REFERENCE_FRACTION headroom), labeled a *reference*, never a
  measurement. Missing listed TDP -> mode=unknown, never an estimate.

- **Workload suitability** reuses scenario scoring (M4-SCORING-v2.0) per
  component with each profile's weights; profiles carry their own documented
  assumptions (workload_profiles), echoed here.

- **Upgrades** are ranked only where evidence exists, and candidate hints
  carry explicit socket-compatibility state (True/False/None) — never a
  silent suggestion of an incompatible part.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware
from backend.app.services import compatibility_service
from backend.app.services.compatibility_rules import PSU_TDP_REFERENCE_FRACTION
from backend.app.services.intelligence_features import features_from_hardware
from backend.app.services.scenario_scoring import SCENARIOS, score_scenarios
from backend.app.services.workload_profiles import PROFILES

BUILD_INTELLIGENCE_VERSION = "M4-BUILD-v1.0"

# Required slots for a complete PC. M1/M2 build slots are cpu/gpu +
# the four M2 categories; a build missing any of these is partial.
_REQUIRED_SLOTS = ("motherboard", "ram", "storage", "psu")
# Slots SPECTRA can actually load specs for (build-chat context is CPU+GPU
# only, M1 contract; the four M2 slots are compatibility context).
_LOADABLE_SLOTS = ("cpu", "gpu", "motherboard", "ram", "storage", "psu")

# Balance ratio bands (multi_core score GPU-proxy absent -> CPU ratio only).
_BALANCED_BAND = (0.75, 1.33)
_MODERATE_BAND = (0.5, 2.0)

_UPGRADE_POOL = 3  # candidate hints per upgrade slot


def _load_hardware(session, hardware_id):
    return session.scalars(
        select(Hardware).where(Hardware.id == hardware_id)
    ).first()


def _load_slot(session, slot: str):
    """Load all hardware of a slot's type with feature-layer relationships."""
    hardware_type = {
        "cpu": "CPU", "gpu": "GPU", "motherboard": "MOTHERBOARD",
        "ram": "RAM", "storage": "STORAGE", "psu": "PSU",
    }[slot]
    if hardware_type not in ("CPU", "GPU"):
        return []
    return list(
        session.scalars(
            select(Hardware).where(Hardware.type == hardware_type)
        ).all()
    )


def _balance(cpu_features, gpu_features) -> dict:
    """Qualitative balance from multi-core score ratio. No percentages.

    Ratio is computed only when BOTH sides carry measured benchmark
    evidence. GPU benchmark scores are absent in this dataset, so the
    common case is unknown/insufficient with the gap named — never an
    estimated ratio.
    """
    cpu_mc = (cpu_features or {}).get("features", {}).get("multi_core_score")
    gpu_mc = (gpu_features or {}).get("features", {}).get("multi_core_score")
    if cpu_mc is None or gpu_mc is None:
        missing = []
        if cpu_mc is None:
            missing.append("CPU multi-core benchmark")
        if gpu_mc is None:
            missing.append("GPU benchmark evidence")
        return {
            "classification": "unknown",
            "basis": "insufficient",
            "uncertainty": "high",
            "explanation": (
                "Balance cannot be graded: "
                + (" and ".join(missing))
                + " missing in this dataset. No ratio is estimated."
            ),
        }
    ratio = round(float(cpu_mc) / float(gpu_mc), 4) if gpu_mc else None
    if ratio is None:
        return {
            "classification": "unknown",
            "basis": "insufficient",
            "uncertainty": "high",
            "explanation": "GPU multi-core score is zero; ratio undefined.",
        }
    if _BALANCED_BAND[0] <= ratio <= _BALANCED_BAND[1]:
        classification, uncertainty = "balanced", "low"
    elif _MODERATE_BAND[0] <= ratio <= _MODERATE_BAND[1]:
        classification = "cpu_bound" if ratio > 1 else "gpu_bound"
        uncertainty = "medium"
    else:
        classification = "cpu_bound" if ratio > 1 else "gpu_bound"
        uncertainty = "high"
    return {
        "classification": classification,
        "basis": "multi_core_score_ratio",
        "uncertainty": uncertainty,
        "ratio": ratio,
        "explanation": (
            f"CPU multi-core {cpu_mc:g} vs GPU multi-core {gpu_mc:g} "
            f"(ratio {ratio:g}); both from measured benchmark records. "
            "Qualitative grading only — no percentage is estimated and "
            "workload-specific balance is not measured."
        ),
    }


def _balance_cpu_only(cpu_features) -> dict:
    """CPU-side balance basis (documented: not a GPU comparison)."""
    return _balance(cpu_features, None)


def _compatibility_summary(component_ids: dict) -> dict:
    """Map the engine's own report to a summary; never re-aggregates."""
    report = compatibility_service.check_build_compatibility(component_ids)
    state = report["state"]
    rule_results = report.get("rule_results", [])

    incompatible_rules = [
        r["rule_id"] for r in rule_results if r.get("state") == "INCOMPATIBLE"
    ]
    unknown_rules = [
        r["rule_id"] for r in rule_results if r.get("state") == "UNKNOWN"
    ]
    evaluated = [r["rule_id"] for r in rule_results]

    provided = {k: v for k, v in component_ids.items() if v is not None}
    missing_slots = [slot for slot in _REQUIRED_SLOTS if slot not in provided]

    overall = state
    if state == "COMPATIBLE" and missing_slots:
        # A partial build proves nothing about the whole build.
        overall = "UNKNOWN"

    return {
        "overall": overall,
        "engine_state": state,
        "explanation": report["explanation"],
        "incompatible_rules": incompatible_rules,
        "unknown_rules": unknown_rules,
        "evaluated_rules": evaluated,
        "unknown_rules_detail": [
            {
                "rule_id": r["rule_id"],
                "reason_code": r.get("reason_code"),
                "missing_information": list(r.get("missing_information", [])),
            }
            for r in rule_results if r.get("state") == "UNKNOWN"
        ],
        "rules_version": report["rules_version"],
        "missing_slots": missing_slots,
    }


def _power(components: dict) -> dict:
    """M2.5 TDP reference policy; labeled reference, never measured."""
    cpu = components.get("cpu") or {}
    gpu = components.get("gpu") or {}
    cpu_tdp = cpu.get("tdp_w")
    gpu_tdp = gpu.get("tdp_w")
    present = [c for c in (cpu, gpu) if c]
    if not present:
        return {
            "mode": "unknown", "reference_w": None, "sum_listed_tdp_w": None,
            "basis": "M2.5 listed-TDP reference policy",
            "limitations": [
                "no CPU or GPU selected; nothing to size against",
                "listed TDP values are not measured power consumption",
            ],
        }
    missing = [name for name, c in (("cpu", cpu), ("gpu", gpu))
               if c and c.get("tdp_w") is None]
    if missing:
        return {
            "mode": "unknown", "reference_w": None,
            "sum_listed_tdp_w": None,
            "basis": "M2.5 listed-TDP reference policy",
            "limitations": [
                f"listed TDP not recorded for: {', '.join(missing)}; "
                "no reference is estimated",
                "listed TDP values are not measured power consumption",
            ],
        }
    total = int((cpu_tdp or 0) + (gpu_tdp or 0))
    reference = int(total * (1 + PSU_TDP_REFERENCE_FRACTION) + 0.5)
    return {
        "mode": "reference",
        "reference_w": reference,
        "sum_listed_tdp_w": total,
        "basis": (
            f"M2.5 listed-TDP reference policy: sum of listed TDPs {total} W "
            f"plus {int(PSU_TDP_REFERENCE_FRACTION * 100)}% reference "
            "headroom"
        ),
        "limitations": [
            "listed TDP values are not measured power consumption and are "
            "not a power supply requirement",
            "PSU connector requirements are not evaluated (no connector "
            "data in this dataset)",
        ],
    }


def _workload_suitability(cpu_features, gpu_features) -> dict:
    """Per-profile suitability from scenario scores (weighted blend)."""
    out = {}
    for key, profile in PROFILES.items():
        per_slot = {}
        weighted = 0.0
        weight_total = 0.0
        confidences = []
        for slot, features in (("cpu", cpu_features), ("gpu", gpu_features)):
            if features is None:
                continue
            payload = score_scenarios(
                features,
                anchors=features.get("_anchors"),
                profile={"scenario_weights": profile.scenario_weights},
            )
            scenarios = payload["scenarios"]
            per_slot[slot] = {
                s: {
                    "score": scenarios[s]["score"],
                    "stars": scenarios[s]["stars"],
                    "confidence": scenarios[s]["confidence"],
                }
                for s in SCENARIOS if s in scenarios
            }
            for scenario, weight in profile.scenario_weights.items():
                entry = scenarios.get(scenario)
                if entry is None or entry["score"] is None or not weight:
                    continue
                weighted += entry["score"] * weight
                weight_total += weight
            confidences.extend(
                scenarios[s]["confidence"] for s in SCENARIOS
                if s in scenarios and scenarios[s]["score"] is not None
            )
        if weight_total:
            score = round(weighted / weight_total, 2)
            confidence = (
                "high" if confidences and all(c == "high" for c in confidences)
                else ("low" if "unknown" in confidences else "medium")
            )
        else:
            score = None
            confidence = "unknown"
        out[key] = {
            "score": score,
            "confidence": confidence,
            "profile_label": profile.label,
            "assumptions": list(profile.assumptions),
            "per_component": per_slot,
        }
    return out


def _upgrade_candidates(session, slot: str, current_score, anchors,
                        current_socket, exclude_ids):
    """Candidate hints for an upgrade slot; evidence-gated, socket-aware."""
    rows = _load_slot(session, slot)
    scored = []
    for hw in rows:
        if hw.id in exclude_ids:
            continue
        features = features_from_hardware(hw)
        payload = score_scenarios(features, anchors=anchors)
        scenarios = payload["scenarios"]
        relevant = ("workstation" if slot == "cpu" else "gaming")
        entry = scenarios.get(relevant, {})
        if entry.get("score") is None:
            continue
        socket = (features.get("features") or {}).get("socket")
        socket_compatible = None
        if current_socket and socket:
            socket_compatible = (socket == current_socket)
        scored.append({
            "hardware_id": hw.id,
            "hardware_name": hw.name,
            "score": entry["score"],
            "socket_compatible": socket_compatible,
        })
    scored.sort(key=lambda item: (-item["score"], item["hardware_id"]))
    return scored[:_UPGRADE_POOL]


def _upgrades(session, components, anchors) -> list[dict]:
    """Evidence-gated upgrade suggestions per slot."""
    upgrades = []
    slot_specs = {
        "cpu": ("workstation", ("multi_core_score",)),
        "gpu": ("gaming", ("memory_gb", "vram_bandwidth_gbps")),
    }
    for slot, (relevant, spec_keys) in slot_specs.items():
        component = components.get(slot) or {}
        features = component.get("_features")
        if features is None:
            continue
        fv = features.get("features") or {}
        if slot == "cpu" and fv.get("multi_core_score") is None:
            continue  # no benchmark evidence -> no upgrade claim
        if slot == "gpu" and all(
            fv.get(k) is None for k in spec_keys
        ):
            continue
        entry = score_scenarios(
            features, anchors=anchors
        )["scenarios"].get(relevant, {})
        current_score = entry.get("score")
        if current_score is None:
            continue
        current_socket = fv.get("socket")
        candidates = _upgrade_candidates(
            session, slot, current_score, anchors, current_socket,
            exclude_ids={component["hardware_id"]},
        )
        if not candidates:
            continue
        better = [c for c in candidates if c["score"] > current_score]
        if not better:
            continue
        for cand in better:
            upgrades.append({
                "target_slot": slot,
                "direction": "upgrade",
                "evidence": "benchmark" if slot == "cpu" else "spec",
                "current_score": current_score,
                "suggested_score": cand["score"],
                "candidate_hint": {
                    "hardware_id": cand["hardware_id"],
                    "hardware_name": cand["hardware_name"],
                    "socket_compatible": cand["socket_compatible"],
                },
                "rationale": (
                    f"{relevant} score {cand['score']:g} vs current "
                    f"{current_score:g} "
                    f"(from {'measured benchmark' if slot == 'cpu' else 'listed specs only; no GPU benchmark data exists'})"
                    + (
                        ""
                        if cand["socket_compatible"] is not False
                        else "; candidate socket differs from the selected "
                             "CPU socket — replacing both may be required"
                    )
                ),
            })
    return upgrades


def analyze_build(component_ids: dict, anchors=None,
                  session_factory=None) -> dict:
    """M4 build intelligence payload for one build context.

    Read-only. ``component_ids`` maps slot -> hardware id (cpu, gpu,
    motherboard, ram, storage, psu). Compatibility is delegated verbatim to
    the M32-RULES-v2 engine; balance/power/workload-suitability follow the
    documented evidence policies above.
    """
    session_factory = session_factory or SessionLocal
    provided = {k: v for k, v in (component_ids or {}).items() if v is not None}
    unknown_ids = [k for k in provided if k not in _LOADABLE_SLOTS]
    if unknown_ids:
        raise ValueError(
            f"unknown build slot(s): {', '.join(sorted(unknown_ids))}"
        )

    with session_factory() as session:
        components: dict[str, dict] = {}
        missing_hardware = [
            slot for slot, hw_id in provided.items()
            if _load_hardware(session, hw_id) is None
        ]
        if missing_hardware:
            raise LookupError(
                f"hardware id not found for slot(s): {', '.join(missing_hardware)}"
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
                features["_anchors"] = anchors
                components[slot]["_features"] = features
                components[slot]["tdp_w"] = (
                    features["features"].get("tdp_w")
                )

        cpu_features = components.get("cpu", {}).get("_features")
        gpu_features = components.get("gpu", {}).get("_features")

        payload = {
            "build_intelligence_version": BUILD_INTELLIGENCE_VERSION,
            "components": {
                slot: {k: v for k, v in c.items() if not k.startswith("_")}
                for slot, c in components.items()
            },
            "missing_slots": [
                slot for slot in _REQUIRED_SLOTS if slot not in provided
            ],
            "balance": _balance(cpu_features, gpu_features),
            "power": _power(components),
            "workload_suitability": _workload_suitability(
                cpu_features, gpu_features
            ),
            "limitations": [
                "no price data in this dataset; budget alternatives cannot "
                "be suggested",
                "no thermal measurements; thermal balance is not assessed",
                "no game FPS or application-specific benchmark data exists",
            ],
            "budget_alternatives": [],
        }

    # Compatibility engine (delegates its own session, read-only).
    if provided:
        payload["compatibility"] = compatibility_service.check_build_compatibility(
            provided
        )
        payload["compatibility_summary"] = _compatibility_summary(provided)
    else:
        payload["compatibility"] = None
        payload["compatibility_summary"] = {
            "overall": "NOT_EVALUATED",
            "engine_state": None,
            "explanation": "no components provided",
            "incompatible_rules": [], "unknown_rules": [],
            "evaluated_rules": [], "unknown_rules_detail": [],
            "rules_version": None,
            "missing_slots": list(_REQUIRED_SLOTS),
        }

    with session_factory() as session:
        payload["upgrades"] = _upgrades(session, components, anchors)

    return payload
