"""M4 wire models for intelligent recommendations, build intelligence, and
build optimization (additive to all v1 schemas).

Constraint classification vocabulary (closed):
- hard      : filters candidates when violated
- soft      : shapes ranking; never silently filters; documented notes
- unknown   : cannot be evaluated from current data; disclosed, never guessed
- estimated : derived from listed specs under a documented policy (advisory)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RankingVersion = Literal["M4-REC-v2.0"]
BuildIntelVersion = Literal["M4-BUILD-v1.0"]
OptimizerVersion = Literal["M4-OPT-v1.0"]

WorkloadProfileKey = Literal[
    "esports_gaming", "aaa_gaming", "general_productivity",
    "software_development", "video_editing", "rendering_3d",
    "virtualization_homelab", "ai_ml_experimentation",
]

HardwareType = Literal["CPU", "GPU"]
ConstraintClassification = Literal["hard", "soft", "unknown", "estimated"]
Priority = Literal["performance", "balanced", "efficiency"]


class RecommendationConstraints(BaseModel):
    """User constraints for /hardware/recommend/v2."""

    model_config = ConfigDict(extra="forbid")

    hardware_type: HardwareType
    profile_key: WorkloadProfileKey | None = None
    budget_max: int | None = Field(default=None, ge=0)
    resolution: Literal["1080p", "1440p", "4k"] | None = None
    power_limit_w: int | None = Field(default=None, ge=1)
    priority: Priority | None = None
    existing_components: dict[str, int | None] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=50)


class ContributingFactor(BaseModel):
    feature: str
    weight: float
    normalized: float | None = None
    present: bool
    benchmark_value: float | None = None
    price_as_of: str | None = None


class ScenarioScore(BaseModel):
    score: float | None = None
    stars: int = Field(default=0, ge=0, le=5)
    confidence: str
    data_coverage: float = Field(ge=0.0, le=1.0)
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    spec_based: bool = False
    scoring_version: str


class ScenarioSetResponse(BaseModel):
    scoring_version: str
    reference_population: str
    data_coverage: float
    scenarios: dict[str, ScenarioScore]


class ExcludedCandidate(BaseModel):
    hardware_id: int
    hardware_name: str
    reason_code: str
    reason: str


class RecommendationCandidateV2(BaseModel):
    rank: int
    hardware_id: int
    hardware_name: str
    hardware_type: str
    scenario_scores: dict[str, Any]
    stars: int = Field(ge=0, le=5)
    confidence: str
    rank_explanation: list[str] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ConstraintEcho(BaseModel):
    value: Any = None
    classification: ConstraintClassification
    notes: list[str] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    """Wire shape for /hardware/recommend/v2 (GET + POST)."""

    model_config = ConfigDict(from_attributes=True)

    candidates: list[RecommendationCandidateV2]
    alternatives: list[RecommendationCandidateV2]
    excluded: list[ExcludedCandidate]
    constraints_echo: dict[str, ConstraintEcho]
    profile: dict[str, Any]
    ranking_version: RankingVersion
    deterministic: Literal[True]


# --------------------------------------------------------------------------
# M4 Task 5: build intelligence (M4-BUILD-v1.0)
# --------------------------------------------------------------------------

BuildIntelSlot = Literal["cpu", "gpu", "motherboard", "ram", "storage", "psu"]


class BuildIntelligenceRequest(BaseModel):
    """Slot -> hardware id. Every slot optional: partial builds are valid."""

    model_config = ConfigDict(extra="forbid")

    cpu: int | None = None
    gpu: int | None = None
    ram: int | None = None
    storage: int | None = None
    motherboard: int | None = None
    psu: int | None = None


class ComponentRef(BaseModel):
    hardware_id: int
    hardware_name: str
    type: str


class BalanceReport(BaseModel):
    classification: Literal["cpu_bound", "gpu_bound", "balanced", "unknown"]
    basis: str
    uncertainty: Literal["low", "medium", "high"]
    explanation: str


class PowerReport(BaseModel):
    mode: Literal["reference", "unknown"]
    reference_w: int | None = None
    sum_listed_tdp_w: int | None = None
    basis: str
    limitations: list[str] = Field(default_factory=list)


class CompatibilitySummary(BaseModel):
    overall: Literal["COMPATIBLE", "INCOMPATIBLE", "UNKNOWN", "NOT_EVALUATED"]
    engine_state: str | None = None
    explanation: str
    incompatible_rules: list[str] = Field(default_factory=list)
    unknown_rules: list[str] = Field(default_factory=list)
    evaluated_rules: list[str] = Field(default_factory=list)
    unknown_rules_detail: list[dict[str, Any]] = Field(default_factory=list)
    rules_version: str | None = None
    missing_slots: list[str] = Field(default_factory=list)


class UpgradeCandidateHint(BaseModel):
    hardware_id: int
    hardware_name: str
    socket_compatible: bool | None = None


class UpgradeSuggestion(BaseModel):
    target_slot: Literal["cpu", "gpu"]
    direction: Literal["upgrade"]
    evidence: Literal["benchmark", "spec"]
    current_score: float
    suggested_score: float
    candidate_hint: UpgradeCandidateHint
    rationale: str


class WorkloadSuitabilityEntry(BaseModel):
    score: float | None = None
    confidence: str
    profile_label: str
    assumptions: list[str] = Field(default_factory=list)
    per_component: dict[str, Any] = Field(default_factory=dict)


class BuildIntelligenceResponse(BaseModel):
    build_intelligence_version: BuildIntelVersion
    components: dict[str, ComponentRef]
    missing_slots: list[str]
    balance: BalanceReport
    power: PowerReport
    workload_suitability: dict[str, WorkloadSuitabilityEntry]
    compatibility: dict[str, Any] | None = None
    compatibility_summary: CompatibilitySummary
    upgrades: list[UpgradeSuggestion] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    budget_alternatives: list[Any] = Field(default_factory=list)


# --------------------------------------------------------------------------
# M4 Task 6: bounded build optimizer (M4-OPT-v1.0)
# --------------------------------------------------------------------------

class OptimizationRequest(BaseModel):
    """Bounded single-swap optimization request."""

    model_config = ConfigDict(extra="forbid")

    components: BuildIntelligenceRequest
    profile_key: WorkloadProfileKey | None = None
    budget_max: int | None = Field(default=None, ge=0)
    power_limit_w: int | None = Field(default=None, ge=1)
    priority: Priority | None = None


class SwapCandidateHint(BaseModel):
    hardware_id: int
    hardware_name: str
    socket_compatible: bool | None = None


class SwapSuggestion(BaseModel):
    target_slot: Literal["cpu", "gpu"]
    remove_hardware_id: int
    remove_hardware_name: str
    candidate_hint: SwapCandidateHint
    before_score: float
    after_score: float
    improvement: float
    scenario: str
    evidence_basis: Literal["benchmark", "spec"]
    rationale: str
    trade_offs: list[str] = Field(default_factory=list)


class OptimizationResponse(BaseModel):
    optimizer_version: OptimizerVersion
    build_intelligence_version: BuildIntelVersion
    swaps: list[SwapSuggestion]
    constraints_echo: dict[str, ConstraintEcho]
    profile: dict[str, Any]
    deterministic: Literal[True]
