"""Tests for the suitability API wire models (schemas/suitability.py).

Verifies the Pydantic models round-trip cleanly and that the service-to-wire
conversion helpers (`rating_to_response`, `evidence_quality_to_response`) are
lossless for every field the service produces.
"""

from __future__ import annotations

from backend.app.schemas.suitability import (
    EvidenceQualityResponse,
    SuitabilityRatingResponse,
    evidence_quality_to_response,
    rating_to_response,
)


def _rating_dict():
    return {
        "stars": 3,
        "raw_score": 3.2,
        "confidence": "medium",
        "spec_based": True,
        "category": "gaming",
        "rationale": ["No driver/benchmark evidence; rating based on specs only"],
        "caveats": ["Spec-based rating capped at 3 stars"],
        "unrated_reason": None,
        "evidence_quality": {
            "score": 0.55,
            "confidence": "medium",
            "signals": {
                "attribution": True,
                "spec": True,
                "provenance": False,
                "workload_match": True,
                "any_benchmark": True,
            },
            "reason": None,
        },
    }


def test_rating_response_round_trips_through_model_dump():
    rating = rating_to_response(_rating_dict())
    as_dict = rating.model_dump()
    rebuilt = SuitabilityRatingResponse.model_validate(as_dict)
    assert rebuilt == rating


def test_evidence_quality_response_round_trips():
    evidence = {
        "score": 0.55,
        "confidence": "medium",
        "signals": {
            "attribution": True,
            "spec": True,
            "provenance": False,
            "workload_match": True,
            "any_benchmark": True,
        },
        "reason": None,
    }
    resp = evidence_quality_to_response(evidence)
    assert resp.benchmark_present is True
    assert resp.spec_complete is True
    as_dict = resp.model_dump()
    assert EvidenceQualityResponse.model_validate(as_dict) == resp


def test_rating_to_response_preserves_every_field():
    rating = rating_to_response(_rating_dict())
    assert rating.stars == 3
    assert rating.raw_score == 3.2
    assert rating.confidence == "medium"
    assert rating.spec_based is True
    assert rating.category == "gaming"
    assert rating.unrated_reason is None
    assert rating.evidence_quality is not None
    assert rating.evidence_quality.score == 0.55


def test_unrated_rating_is_serializable():
    rating_dict = _rating_dict()
    rating_dict.update(
        stars=0,
        raw_score=0.0,
        confidence="unrated",
        spec_based=False,
        unrated_reason="insufficient_data:no_gpu_benchmarks",
        evidence_quality={
            "score": 0.0,
            "confidence": "low",
            "signals": {
                "attribution": False,
                "spec": False,
                "provenance": False,
                "workload_match": False,
                "any_benchmark": False,
            },
            "reason": None,
        },
    )
    rating = rating_to_response(rating_dict)
    as_dict = rating.model_dump()
    assert SuitabilityRatingResponse.model_validate(as_dict) == rating
    assert rating.unrated_reason.startswith("insufficient_data")
