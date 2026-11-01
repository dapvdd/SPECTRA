"""Pydantic wire models for the hardware recommendation API (Objective E).

Mirrors the `recommend` service output so the API layer can construct the
response without reshaping.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.suitability import (
    SuitabilityRatingResponse,
)


class RecommendationCandidate(BaseModel):
    """One ranked recommendation: a hardware summary + its suitability."""

    model_config = ConfigDict(from_attributes=True)

    hardware_id: int
    hardware_name: str
    hardware_type: str
    suitability: SuitabilityRatingResponse
    explanation: list[str]


class RecommendationResponse(BaseModel):
    """Ranked recommendations for a workload."""

    model_config = ConfigDict(from_attributes=True)

    candidates: list[RecommendationCandidate]
    filter_reason: str | None = None
    budget_max: int | None = Field(default=None, ge=0)
