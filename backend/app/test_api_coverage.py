"""Coverage tests for user-facing API branches not exercised elsewhere.

Targets (from a `pytest-cov` run over `backend.app.main` + `backend.app.services`):

1. `recommendation_service.recommend_response` generic "no candidates"
   ``filter_reason`` branch — the non-ai_ml empty-candidates message
   (``recommendation_service.py:132-135``). The ai_ml-specific branch is
   already covered by `test_recommend_returns_empty_for_gpu_ai_ml`.
2. The single-category suitability route 404
   (``main.py:665``, `GET /hardware/{id}/suitability/{category}` when the
   hardware does not exist). The multi-category route's 404 is already tested
   in `test_suitability_missing_hardware_returns_404`.

The in-memory SQLite + session redirection pattern matches
`backend/app/test_suitability_api.py` exactly (both ``main.SessionLocal`` and
``recommendation_service.SessionLocal`` are redirected so sub-services share
the same connection).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import (
    CPUSpecification,
    Hardware,
)
from backend.app.services import recommendation_service  # noqa: E402


class CoverageAPISetup:
    """Seed an in-memory DB identical to SuitabilityAPISetup's fixtures."""

    def __init__(self):
        self._saved_main = main.SessionLocal
        self._saved_rec = recommendation_service.SessionLocal
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main.SessionLocal = self.session_factory
        recommendation_service.SessionLocal = self.session_factory
        self.client = TestClient(main.app)
        self.cpu_id, self.gpu_id, self.bench_cpu_id = self._seed()

    def _seed(self):
        with self.session_factory() as session:
            # Seed only a CPU: the recommendation-recommend test requests
            # `type=GPU` to exercise the empty-candidates branch, so no GPU
            # rows may exist. The 404 test is type-agnostic (unknown id).
            cpu = Hardware(
                name="AMD Ryzen 5 5600",
                manufacturer="AMD",
                type="CPU",
                architecture="Zen 3",
            )
            cpu.cpu_specification = CPUSpecification(
                cores=6, threads=12, base_clock_ghz=3.5,
                boost_clock_ghz=4.4, socket="AM4", tdp_w=65,
            )
            session.add(cpu)
            session.commit()
            return cpu.id, None, None

    def teardown(self):
        main.SessionLocal = self._saved_main
        recommendation_service.SessionLocal = self._saved_rec
        self.engine.dispose()


def test_recommend_returns_empty_generic_filter_reason_for_unbenchmarked_type():
    """The generic (non-ai_ml) empty-candidates filter_reason branch.

    The seed contains only a CPU. Requesting `type=GPU` means there are no
    GPU rows at all, so no candidate passes the evidence threshold and the
    route must report the generic message — not the ai_ml-specific one.
    """
    setup = CoverageAPISetup()
    try:
        resp = setup.client.get(
            "/hardware/recommend",
            params={"type": "GPU", "workload": "gaming"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["candidates"] == []
        assert body["filter_reason"] is not None
        assert (
            body["filter_reason"]
            == "no candidates passed evidence threshold"
        )
        # Explicitly NOT the ai_ml-specific message.
        assert "GPU/VRAM" not in body["filter_reason"]
    finally:
        setup.teardown()


def test_suitability_single_category_missing_hardware_returns_404():
    """Single-category suitability route 404 for an unknown hardware id."""
    setup = CoverageAPISetup()
    try:
        resp = setup.client.get("/hardware/999999/suitability/gaming")
        assert resp.status_code == 404
        assert "Hardware not found" in resp.json()["detail"]
    finally:
        setup.teardown()
