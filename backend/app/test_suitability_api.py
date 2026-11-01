"""Tests for the suitability API endpoints (Objective B/D).

Covers `GET /hardware/{id}/suitability` (all categories) and
`GET /hardware/{id}/suitability/{category}`. An in-memory SQLite database is
used and the app session factory is redirected at it, matching the existing
API tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    GPUSpecification,
    Hardware,
)


class SuitabilityAPISetup:
    def __init__(self):
        self._saved = main.SessionLocal
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main.SessionLocal = self.session_factory
        self.client = TestClient(main.app)
        self.cpu_id, self.gpu_id, self.bench_cpu_id = self._seed()

    def _seed(self):
        with self.session_factory() as session:
            cpu = Hardware(name="AMD Ryzen 5 5600", manufacturer="AMD",
                           type="CPU", architecture="Zen 3")
            cpu.cpu_specification = CPUSpecification(
                cores=6, threads=12, base_clock_ghz=3.5,
                boost_clock_ghz=4.4, socket="AM4", tdp_w=65,
            )
            gpu = Hardware(name="NVIDIA RTX 5070 Ti", manufacturer="NVIDIA",
                           type="GPU", architecture="Blackwell")
            gpu.gpu_specification = GPUSpecification(
                memory_gb=16, memory_type="GDDR7", core_clock_mhz=2400,
                memory_bus_width_bits=256, tdp_w=350,
            )
            # A fully benchmarked CPU (with multi and single-core scores)
            bench_cpu = Hardware(name="AMD Ryzen 9 7950X", manufacturer="AMD",
                                 type="CPU", architecture="Zen 4")
            bench_cpu.cpu_specification = CPUSpecification(
                cores=16, threads=32, base_clock_ghz=4.5,
                boost_clock_ghz=5.7, socket="AM5", tdp_w=170,
            )
            session.add_all([cpu, gpu, bench_cpu])
            session.commit()
            bench_cpu_id = bench_cpu.id
            session.add(BenchmarkResult(
                hardware_id=bench_cpu_id, benchmark_name="Geekbench 7",
                score=16000, unit="points", test_type="multi-core",
            ))
            session.add(BenchmarkResult(
                hardware_id=bench_cpu_id, benchmark_name="Geekbench 7",
                score=2200, unit="points", test_type="single-core",
            ))
            session.commit()
            return cpu.id, gpu.id, bench_cpu_id

    def teardown(self):
        main.SessionLocal = self._saved
        self.engine.dispose()


def test_suitability_returns_unrated_for_gpu_ai_ml():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get(f"/hardware/{setup.gpu_id}/suitability")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hardware_type"] == "GPU"
        ai = [r for r in body["ratings"] if r["category"] == "ai_ml"][0]
        assert ai["confidence"] == "unrated"
        assert ai["stars"] == 0
    finally:
        setup.teardown()


def test_suitability_is_spec_based_when_no_benchmark():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get(f"/hardware/{setup.cpu_id}/suitability")
        assert resp.status_code == 200
        body = resp.json()
        ratings = body["ratings"]
        assert len(ratings) == 5
        # The non-benchmarked CPU is spec-based for multi-core workloads
        gaming = [r for r in ratings if r["category"] == "gaming"][0]
        assert gaming["spec_based"] is True
        assert gaming["evidence_quality"] is not None
    finally:
        setup.teardown()


def test_suitability_benchmarked_cpu_not_spec_based():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get(f"/hardware/{setup.bench_cpu_id}/suitability")
        body = resp.json()
        gaming = [r for r in body["ratings"] if r["category"] == "gaming"][0]
        assert gaming["spec_based"] is False
        # A strong multi-core benchmark maps to 4-5 stars
        assert gaming["stars"] >= 4
    finally:
        setup.teardown()


def test_suitability_detail_single_category():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get(
            f"/hardware/{setup.cpu_id}/suitability/workstation"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["category"] == "workstation"
        assert "rationale" in body
        assert "caveats" in body
    finally:
        setup.teardown()


def test_suitability_invalid_category_returns_422():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get(f"/hardware/{setup.cpu_id}/suitability/nope")
        assert resp.status_code == 422
    finally:
        setup.teardown()


def test_suitability_missing_hardware_returns_404():
    setup = SuitabilityAPISetup()
    try:
        resp = setup.client.get("/hardware/999999/suitability")
        assert resp.status_code == 404
    finally:
        setup.teardown()
