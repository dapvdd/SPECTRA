"""Pydantic wire models for the hardware suitability API (Objective B/D).

These models mirror what ``rate_suitability`` and ``score_evidence_quality``
return so the API layer can construct them without reshaping. Both dimensions
are deliberately separate so a suitability rating is never confused with the
trustworthiness of its underlying evidence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Closed vocabulary shared with the suitability service.
WorkloadCategory = Literal[
    "gaming", "workstation", "productivity", "content_creation", "ai_ml"
]
EvidenceConfidence = Literal["high", "medium", "low"]
RatingConfidence = Literal["high", "medium", "low", "unrated"]


class EvidenceQualityResponse(BaseModel):
    """How trustworthy our data is for a hardware+workload pair (0..1)."""

    model_config = ConfigDict(from_attributes=True)

    score: float = Field(ge=0.0, le=1.0)
    confidence: EvidenceConfidence
    signals: dict[str, bool]
    benchmark_present: bool
    spec_complete: bool
    reason: str | None = None


class SuitabilityRatingResponse(BaseModel):
    """Workload-aware suitability for one category (0..5 stars)."""

    model_config = ConfigDict(from_attributes=True)

    category: WorkloadCategory
    stars: int = Field(ge=0, le=5)
    raw_score: float = Field(ge=0.0, le=5.0)
    confidence: RatingConfidence
    spec_based: bool
    rationale: list[str]
    caveats: list[str]
    evidence_quality: EvidenceQualityResponse | None = None
    unrated_reason: str | None = None


class HardwareSuitabilityResponse(BaseModel):
    """All suitability categories for one hardware record."""

    model_config = ConfigDict(from_attributes=True)

    hardware_id: int
    hardware_name: str
    hardware_type: str
    ratings: list[SuitabilityRatingResponse]


class WorkloadRequest(BaseModel):
    """Optional workload context for a suitability query.

    ``resolution`` and ``target_fps`` are accepted for gaming workloads where
    supporting evidence exists; they refine the request but the rating logic
    never fabricates an FPS figure when none is available.
    """

    model_config = ConfigDict(extra="forbid")

    category: WorkloadCategory
    resolution: Literal["1080p", "1440p", "4k"] | None = None
    target_fps: int | None = Field(default=None, ge=30, le=240)


def evidence_quality_to_response(evidence: dict) -> EvidenceQualityResponse:
    """Build the wire model from a `score_evidence_quality` payload."""
    signals = evidence["signals"]
    return EvidenceQualityResponse(
        score=evidence["score"],
        confidence=evidence["confidence"],
        signals=signals,
        benchmark_present=signals.get("any_benchmark", False),
        spec_complete=signals.get("spec", False),
        reason=evidence.get("reason"),
    )


def rating_to_response(rating: dict) -> SuitabilityRatingResponse:
    """Build the wire model from a `rate_suitability` payload."""
    return SuitabilityRatingResponse(
        category=rating["category"],
        stars=rating["stars"],
        raw_score=rating["raw_score"],
        confidence=rating["confidence"],
        spec_based=rating["spec_based"],
        rationale=rating["rationale"],
        caveats=rating["caveats"],
        evidence_quality=evidence_quality_to_response(
            rating["evidence_quality"]
        ),
        unrated_reason=rating.get("unrated_reason"),
    )
