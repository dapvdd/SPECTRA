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
