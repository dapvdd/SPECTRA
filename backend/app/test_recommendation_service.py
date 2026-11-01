"""Tests for the deterministic recommendation engine (Objective E).

Recommendations rank hardware for a workload, filtered by an evidence
threshold, WITHOUT fabricating suitability scores. These tests pin the
filter/rank semantics on an in-memory database.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    Hardware,
)
from backend.app.services import recommendation_service
from backend.app.services.recommendation_service import recommend


class RecommendationSetup:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        from backend.app.services import recommendation_service

        self._saved = recommendation_service.SessionLocal
        recommendation_service.SessionLocal = self.session_factory

    def teardown(self):
        from backend.app.services import recommendation_service

        recommendation_service.SessionLocal = self._saved
        self.engine.dispose()

    def _add_benchmarked_cpu(self, name, mc_score, sc_score, cores=16):
        with self.session_factory() as session:
            hw = Hardware(
                name=name, manufacturer="AMD", type="CPU", architecture="Zen 4",
            )
            hw.cpu_specification = CPUSpecification(
                cores=cores, threads=cores * 2, base_clock_ghz=4.5,
                boost_clock_ghz=5.7, socket="AM5", tdp_w=170,
            )
            session.add(hw)
            session.commit()
            hw_id = hw.id
            session.add(BenchmarkResult(
                hardware_id=hw_id, benchmark_name="Geekbench 7",
                score=mc_score, unit="points", test_type="multi-core",
            ))
            session.add(BenchmarkResult(
                hardware_id=hw_id, benchmark_name="Geekbench 7",
                score=sc_score, unit="points", test_type="single-core",
            ))
            session.commit()
            return hw_id


def test_recommend_excludes_unrated_for_ai_ml():
    setup = RecommendationSetup()
    try:
        result = recommend("CPU", "ai_ml", limit=10)
        assert result == []
    finally:
        setup.teardown()


def test_recommend_respects_evidence_threshold():
    setup = RecommendationSetup()
    try:
        setup._add_benchmarked_cpu("Ryzen Strong", 16000, 2200)
        result = recommend("CPU", "gaming", limit=5)
        # A strong benchmarked CPU clears the evidence threshold
        assert len(result) >= 1
        for item in result:
            assert item["suitability"]["confidence"] in ("high", "medium")
            assert item["suitability"]["stars"] >= 3
    finally:
        setup.teardown()


def test_recommend_ranks_by_stars_then_evidence():
    setup = RecommendationSetup()
    try:
        setup._add_benchmarked_cpu("Top CPU", 18000, 2300)
        setup._add_benchmarked_cpu("Good CPU", 11000, 1900)
        setup._add_benchmarked_cpu("Entry CPU", 3000, 900)
        result = recommend("CPU", "gaming", limit=10)
        stars = [r["suitability"]["stars"] for r in result]
        assert stars == sorted(stars, reverse=True)
    finally:
        setup.teardown()


def test_recommend_filters_by_hardware_type():
    setup = RecommendationSetup()
    try:
        setup._add_benchmarked_cpu("Any CPU", 15000, 2100)
        result = recommend("CPU", "gaming", limit=10)
        assert len(result) >= 1
        for item in result:
            assert item["hardware"]["type"] == "CPU"
    finally:
        setup.teardown()


def test_recommend_limits_result_count():
    setup = RecommendationSetup()
    try:
        for i in range(12):
            setup._add_benchmarked_cpu(f"CPU {i}", 14000 + i, 2000)
        result = recommend("CPU", "gaming", limit=3)
        assert len(result) == 3
    finally:
        setup.teardown()


def test_recommend_response_payload_round_trips():
    """The service -> wire payload serializes and round-trips cleanly."""
    from backend.app.schemas.recommendation import RecommendationResponse

    setup = RecommendationSetup()
    try:
        setup._add_benchmarked_cpu("Ryzen Strong", 16000, 2200)
        payload = recommendation_service.recommend_response(
            "CPU", "gaming", limit=5
        )
        response = RecommendationResponse.model_validate(payload)
        assert len(response.candidates) == 1
        assert response.candidates[0].suitability.stars >= 3
        assert response.filter_reason is None
        assert RecommendationResponse.model_validate(
            response.model_dump()
        ) == response
    finally:
        setup.teardown()
