"""M4 Task 3: configurable workload profiles (WORKLOAD_PROFILE_VERSION M4-PROFILES-v1.0).

Eight profiles from the mission brief. A profile is an immutable recipe that
maps scenarios (from scenario_scoring) to weights, documents the evidence it
relies on and does NOT claim (assumptions), and declares which user
preferences it supports.

Evidence policy (mission T3):
- Profiles never invent application-specific benchmark measurements. Each
  profile's assumptions name the proxy evidence used (e.g. Geekbench 7
  multi-core for rendering workloads) and the claims it does not make
  (e.g. no game FPS, no GPU-compute measurements in this dataset).
- Preferences are validated: unsupported preference -> ValueError; unknown
  preference -> ValueError. Priority reweights scenario weights within
  documented, deterministic bounds; weights always stay normalised to 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

WORKLOAD_PROFILE_VERSION = "M4-PROFILES-v1.0"

_RESOLUTIONS = ("1080p", "1440p", "4k")
_PRIORITIES = ("performance", "balanced", "efficiency")

# Priority reweighting: multiply positive scenario weights, then renormalise.
_PRIORITY_MULTIPLIERS = {
    "performance": {"gaming": 1.15, "workstation": 1.15, "daily": 0.85},
    "efficiency": {"gaming": 0.85, "workstation": 0.85, "daily": 1.15},
    "balanced": {},
}


@dataclass(frozen=True)
class WorkloadProfile:
    key: str
    label: str
    description: str
    scenario_weights: dict        # scenario -> weight (sums to 1.0)
    evidence_requirements: tuple  # evidence families the profile relies on
    assumptions: tuple            # explicit evidence claims and non-claims
    supported_preferences: tuple
    preferences: dict = None      # filled by apply_preferences (never on base)

    def __post_init__(self):
        # normalize None preferences to {} without breaking frozen-ness
        if self.preferences is None:
            object.__setattr__(self, "preferences", {})


def _p(key, label, description, weights, requirements, assumptions, prefs):
    return WorkloadProfile(
        key=key, label=label, description=description,
        scenario_weights=dict(weights),
        evidence_requirements=tuple(requirements),
        assumptions=tuple(assumptions),
        supported_preferences=tuple(prefs),
    )


PROFILES: dict[str, WorkloadProfile] = {
    p.key: p for p in [
        _p(
            "esports_gaming", "Esports gaming",
            "High-frame-rate competitive titles at 1080p/1440p.",
            {"gaming": 0.7, "daily": 0.15, "value": 0.15},
            ("multi-core", "single-core"),
            (
                "Uses CPU Geekbench 7 multi-core as the gaming proxy; no "
                "game-specific FPS measurements exist in this dataset.",
                "Does not claim measured FPS at any resolution; resolution "
                "preference is advisory context only.",
                "No GPU gaming benchmarks exist in this dataset, so GPU "
                "gaming suitability is spec-based and capped.",
            ),
            ("resolution", "budget_max", "priority", "existing_components"),
        ),
        _p(
            "aaa_gaming", "AAA gaming",
            "GPU-heavy modern titles at 1440p/4k.",
            {"gaming": 0.55, "workstation": 0.1, "daily": 0.15, "value": 0.2},
            ("multi-core",),
            (
                "CPU side uses Geekbench 7 multi-core; GPU side is "
                "spec-based (VRAM/bandwidth) and capped at 3 stars because "
                "no GPU gaming benchmark data exists.",
                "Never reports expected FPS at a resolution.",
                "Assumes higher VRAM/bandwidth helps at higher resolution — "
                "a qualitative spec argument, not a measured one.",
            ),
            ("resolution", "budget_max", "priority", "existing_components"),
        ),
        _p(
            "general_productivity", "General productivity",
            "Office, browsing, media, everyday multitasking.",
            {"daily": 0.7, "workstation": 0.1, "gaming": 0.05, "value": 0.15},
            ("single-core",),
            (
                "Daily-use scenario weights single-core responsiveness "
                "(Geekbench 7 single-core) and efficiency (score-per-watt).",
                "Does not measure application launch times or battery life.",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
        _p(
            "software_development", "Software development",
            "Coding, compiling, containers, local VMs.",
            {"workstation": 0.55, "daily": 0.2, "gaming": 0.0, "value": 0.25},
            ("multi-core", "single-core"),
            (
                "Compilation/build throughput is proxied by Geekbench 7 "
                "multi-core; IDE responsiveness by single-core.",
                "Does not measure project-specific compile times.",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
        _p(
            "video_editing", "Video editing",
            "Timeline editing, exports, effects.",
            {"workstation": 0.6, "gaming": 0.1, "daily": 0.1, "value": 0.2},
            ("multi-core", "single-core"),
            (
                "Proxy: Geekbench 7 multi-core for export/encode; no "
                "application-specific video benchmark data exists.",
                "Does not claim codec-specific performance (no such data).",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
        _p(
            "rendering_3d", "3D rendering",
            "CPU/GPU render workloads.",
            {"workstation": 0.75, "daily": 0.05, "gaming": 0.0, "value": 0.2},
            ("multi-core",),
            (
                "CPU render proxy: Geekbench 7 multi-core.",
                "GPU render/compute claims are NOT made: no GPU compute "
                "benchmarks exist in this dataset; GPU suitability is "
                "spec-based only.",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
        _p(
            "virtualization_homelab", "Virtualization & homelab",
            "Multi-VM hosts, containers, NAS/services.",
            {"workstation": 0.6, "daily": 0.25, "gaming": 0.0, "value": 0.15},
            ("multi-core",),
            (
                "Proxy: multi-core throughput plus core count; RAM capacity "
                "requirements are NOT modeled (no VM memory sizing data).",
                "Does not estimate VM density.",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
        _p(
            "ai_ml_experimentation", "AI/ML experimentation",
            "Local model inference/experimentation, dataset work.",
            {"workstation": 0.7, "daily": 0.15, "gaming": 0.0, "value": 0.15},
            ("multi-core",),
            (
                "No GPU/VRAM compute benchmarks exist in this dataset: "
                "AI/ML GPU suitability is NOT scored (mirrors v1 ai_ml "
                "insufficient_data:no_gpu_benchmarks).",
                "CPU-side proxy: Geekbench 7 multi-core for data "
                "preprocessing; no training-throughput claims.",
            ),
            ("budget_max", "priority", "power_limit_w", "existing_components"),
        ),
    ]
}

PROFILE_KEYS: tuple[str, ...] = tuple(PROFILES)

_DEFAULT_PROFILE = "general_productivity"

# Preferences only meaningful for gaming-context profiles.
_GAMING_PREFS = {"resolution"}
_GAMING_KEYS = {"esports_gaming", "aaa_gaming"}

_SUPPORTED_PREFS = {
    "resolution", "budget_max", "power_limit_w", "priority",
    "existing_components",
}


def resolve_profile(key: str | None) -> WorkloadProfile:
    """Resolve a profile key; None -> the default profile."""
    if key is None:
        return PROFILES[_DEFAULT_PROFILE]
    if key not in PROFILES:
        raise KeyError(
            f"unknown workload profile '{key}'; supported: {', '.join(PROFILE_KEYS)}"
        )
    return PROFILES[key]


def apply_preferences(profile: WorkloadProfile, prefs: dict) -> WorkloadProfile:
    """Validate and apply preferences; returns a NEW frozen profile."""
    if not prefs:
        return profile
    unknown = set(prefs) - _SUPPORTED_PREFS
    if unknown:
        raise ValueError(f"unsupported preference(s): {', '.join(sorted(unknown))}")
    unsupported_for_profile = set(prefs) - set(profile.supported_preferences)
    if unsupported_for_profile:
        raise ValueError(
            f"preference(s) {', '.join(sorted(unsupported_for_profile))} not "
            f"supported by profile '{profile.key}'"
        )

    if "resolution" in prefs:
        if profile.key not in _GAMING_KEYS:
            raise ValueError(
                f"resolution preference is only supported for gaming profiles"
            )
        if prefs["resolution"] not in _RESOLUTIONS:
            raise ValueError(f"invalid resolution '{prefs['resolution']}'")

    if "priority" in prefs and prefs["priority"] not in _PRIORITIES:
        raise ValueError(f"invalid priority '{prefs['priority']}'")

    if "budget_max" in prefs:
        value = prefs["budget_max"]
        if value is not None and (not isinstance(value, (int, float)) or value < 0):
            raise ValueError("budget_max must be a non-negative number")

    if "power_limit_w" in prefs:
        value = prefs["power_limit_w"]
        if value is not None and (not isinstance(value, (int, float)) or value <= 0):
            raise ValueError("power_limit_w must be a positive number")

    weights = dict(profile.scenario_weights)
    priority = prefs.get("priority")
    if priority and priority in _PRIORITY_MULTIPLIERS:
        multipliers = _PRIORITY_MULTIPLIERS[priority]
        adjusted = {
            s: w * multipliers.get(s, 1.0)
            for s, w in weights.items()
            if w > 0
        }
        total = sum(adjusted.values())
        weights = {s: round(w / total, 6) for s, w in adjusted.items()}
        # Renormalise rounding drift onto the largest weight.
        drift = round(1.0 - sum(weights.values()), 9)
        if drift != 0.0 and weights:
            top = max(weights, key=weights.get)
            weights[top] = round(weights[top] + drift, 6)

    return replace(profile, preferences=dict(prefs), scenario_weights=weights)
