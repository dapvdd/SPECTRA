"""M4 Task 6: bounded build optimizer (M4-OPT-v1.0).

Covers backend/app/services/build_optimizer.py:
- bounded swaps: single-component substitutions with explicit trade-offs
- every swap carries before/after evidence (scores from measured benchmarks;
  spec-based entries labeled)
- constraints classification (budget soft/never filters without price data;
  power_limit_w advisory with TDP evidence)
- never invents prices, FPS, or availability
- socket compatibility passthrough on swap candidates
- deterministic ordering with id tie-break
- route contract (additive /build/optimize)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import main
from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult, CPUSpecification, GPUSpecification, Hardware,
    MotherboardSpecification, PSUSpecification,
)
from backend.app.schemas.intelligence import (
    BuildIntelligenceRequest, OptimizationRequest,
)
from backend.app.services import build_intelligence_service, build_optimizer
from backend.app.services import compatibility_service
from backend.app.services.build_optimizer import optimize_build
from backend.app.services.scenario_scoring import derive_anchors


class _Env:
    def __init__(self):
        self._saved_main = main.SessionLocal
        self._saved_compat = compatibility_service.SessionLocal
        self._saved_intel = build_intelligence_service.SessionLocal
        self._saved_opt = build_optimizer.SessionLocal
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main.SessionLocal = self.session_factory
        compatibility_service.SessionLocal = self.session_factory
        build_intelligence_service.SessionLocal = self.session_factory
        build_optimizer.SessionLocal = self.session_factory
        self.client = TestClient(main.app)

    def teardown(self):
        main.SessionLocal = self._saved_main
        compatibility_service.SessionLocal = self._saved_compat
        build_intelligence_service.SessionLocal = self._saved_intel
        build_optimizer.SessionLocal = self._saved_opt


@pytest.fixture()
def env():
    e = _Env()
    yield e
    e.teardown()


def _cpu(hw_id, name, mc, sc, socket="AM5", cores=8, tdp=65.0):
    benchmarks = []
    if mc is not None:
        benchmarks = [
            BenchmarkResult(benchmark_name="Geekbench 7", score=float(mc),
                            unit="points", test_type="multi-core"),
            BenchmarkResult(benchmark_name="Geekbench 7", score=float(sc),
                            unit="points", test_type="single-core"),
        ]
    return Hardware(
        id=hw_id, name=name, manufacturer="M", type="CPU",
        cpu_specification=CPUSpecification(
            cores=cores, threads=cores * 2, base_clock_ghz=3.0,
            boost_clock_ghz=4.4, tdp_w=tdp, socket=socket,
        ),
        benchmark_results=benchmarks,
    )


def _gpu(hw_id, name, memory_gb=16.0, tdp=250.0):
    return Hardware(
        id=hw_id, name=name, manufacturer="M", type="GPU",
        gpu_specification=GPUSpecification(
            memory_gb=memory_gb, memory_type="GDDR6X", core_clock_mhz=1800.0,
            boost_clock_mhz=2100.0, vram_bandwidth_gbps=760.0,
            memory_bus_width_bits=320, tdp_w=tdp, interface="PCIe 4.0",
        ),
    )


def _board(hw_id, name, socket="AM5"):
    return Hardware(
        id=hw_id, name=name, manufacturer="M", type="MOTHERBOARD",
        motherboard_specification=MotherboardSpecification(
            socket=socket, ram_type="DDR5", max_ram_gb=128, ram_slots=4,
            m2_slots=2, sata_ports=4, pcie_slots=3,
        ),
    )


def _psu(hw_id, name, wattage=750):
    return Hardware(
        id=hw_id, name=name, manufacturer="M", type="PSU",
        psu_specification=PSUSpecification(wattage=wattage),
    )


def _seed(env):
    with env.session_factory() as s:
        for i, mc in enumerate((2100, 3030, 5000, 8200, 13100, 16500), start=1):
            s.add(_cpu(100 + i, f"CPU{i:02d}", float(mc), float(mc) / 6))
        s.add(_gpu(300, "GPU Strong", memory_gb=24.0, tdp=450.0))
        s.add(_gpu(301, "GPU Weak", memory_gb=6.0, tdp=75.0))
        s.add(_board(400, "Board AM5"))
        s.add(_board(401, "Board LGA1700", socket="LGA1700"))
        s.add(_psu(600, "PSU 750W", wattage=750))
        s.add(_psu(601, "PSU 300W", wattage=300))
        s.commit()


def _anchors(env):
    with env.session_factory() as s:
        rows = s.query(Hardware).filter(Hardware.type == "CPU").all()
        mc = sorted(b.score for r in rows for b in r.benchmark_results
                    if b.test_type == "multi-core")
        sc = sorted(b.score for r in rows for b in r.benchmark_results
                    if b.test_type == "single-core")
    return {"multi-core": derive_anchors(mc), "single-core": derive_anchors(sc)}


def _optimize(env, components, **kw):
    return optimize_build(
        components, anchors=_anchors(env), session_factory=env.session_factory,
        **kw
    )


# ------------------------------------------------------------------ swaps ----

def test_optimizer_version_pinned():
    assert build_intelligence_service.BUILD_INTELLIGENCE_VERSION == "M4-BUILD-v1.0"
    from backend.app.services.build_optimizer import OPTIMIZER_VERSION
    assert OPTIMIZER_VERSION == "M4-OPT-v1.0"


def test_swap_improves_targeted_scenario(env):
    _seed(env)
    out = _optimize(env, {"cpu": 101, "gpu": 300},
                    profile_key="software_development")
    assert out["optimizer_version"] == "M4-OPT-v1.0"
    swaps = out["swaps"]
    assert isinstance(swaps, list)
    for swap in swaps:
        assert swap["target_slot"] in ("cpu", "gpu")
        assert swap["before_score"] is not None
        assert swap["after_score"] >= swap["before_score"]


def test_swap_payload_carries_evidence_labels(env):
    _seed(env)
    out = _optimize(env, {"cpu": 101, "gpu": 301},
                    profile_key="aaa_gaming")
    for swap in out["swaps"]:
        assert swap["evidence_basis"] in ("benchmark", "spec")
        if swap["evidence_basis"] == "spec":
            assert any("no gpu benchmark" in s.lower()
                       or "spec" in s.lower()
                       for s in swap["trade_offs"] + [swap["rationale"]])


def test_budget_never_filters(env):
    _seed(env)
    out = _optimize(env, {"cpu": 101}, profile_key="general_productivity",
                    budget_max=100)
    assert out["constraints_echo"]["budget_max"]["classification"] == "soft"
    assert any("price" in n.lower()
               for n in out["constraints_echo"]["budget_max"]["notes"])


def test_power_limit_advisory(env):
    _seed(env)
    # CPU105 tdp=65, swap candidates include tdp=200 (CPU950-like); with a
    # 100 W limit the 200 W candidate must be labeled, not silently offered.
    with env.session_factory() as s:
        s.add(_cpu(950, "Hot CPU", 9000.0, 1500.0, tdp=200.0))
        s.commit()
    out = _optimize(env, {"cpu": 101}, profile_key="software_development",
                    power_limit_w=100)
    offered_ids = {
        swap["candidate_hint"]["hardware_id"]
        for swap in out["swaps"] if swap["target_slot"] == "cpu"
    }
    assert 950 not in offered_ids
    assert any("power" in w.lower() or "tdp" in w.lower()
               for swap in out["swaps"] for w in swap["trade_offs"]) or (
        out["constraints_echo"]["power_limit_w"]["classification"] == "soft"
    )


def test_socket_mismatch_candidate_labeled(env):
    _seed(env)
    # Board AM5 present; candidate CPUs are all AM5 -> fine. Add an LGA CPU.
    with env.session_factory() as s:
        s.add(_cpu(960, "LGA CPU", 17000.0, 2400.0, socket="LGA1700"))
        s.commit()
    out = _optimize(env, {"cpu": 101, "motherboard": 400},
                    profile_key="software_development")
    for swap in out["swaps"]:
        if swap["candidate_hint"]["hardware_id"] == 960:
            assert swap["candidate_hint"]["socket_compatible"] is False
            assert any("socket" in r.lower()
                       for r in swap["trade_offs"] + [swap["rationale"]])


def test_no_price_fps_or_availability_claims(env):
    _seed(env)
    out = _optimize(env, {"cpu": 101, "gpu": 300},
                    profile_key="general_productivity")
    blob = str(out).lower()
    assert "price_usd" not in blob
    assert " fps" not in blob
    assert "in stock" not in blob
    assert "availability" not in blob


def test_deterministic_swap_order(env):
    _seed(env)
    a = _optimize(env, {"cpu": 101, "gpu": 301},
                  profile_key="general_productivity")
    b = _optimize(env, {"cpu": 101, "gpu": 301},
                  profile_key="general_productivity")
    assert a == b


def test_empty_build_returns_no_swaps(env):
    _seed(env)
    out = _optimize(env, {}, profile_key="general_productivity")
    assert out["swaps"] == []
    assert out["constraints_echo"]["build"]["classification"] == "unknown"


# ------------------------------------------------------------------ route ----

def test_optimize_route_shape(env):
    _seed(env)
    resp = env.client.post(
        "/build/optimize",
        json={"components": {"cpu": 101, "gpu": 300},
              "profile_key": "software_development"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["optimizer_version"] == "M4-OPT-v1.0"
    assert "swaps" in body and "constraints_echo" in body


def test_optimize_route_404_unknown_id(env):
    _seed(env)
    resp = env.client.post(
        "/build/optimize",
        json={"components": {"cpu": 99999}},
    )
    assert resp.status_code == 404


def test_optimize_route_invalid_profile_422(env):
    _seed(env)
    resp = env.client.post(
        "/build/optimize",
        json={"components": {"cpu": 101}, "profile_key": "nope"},
    )
    assert resp.status_code == 422
