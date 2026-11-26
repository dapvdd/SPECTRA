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
