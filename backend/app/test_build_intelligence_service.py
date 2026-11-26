"""M4 Task 5: build intelligence service (M4-BUILD-v1.0).

Covers backend/app/services/build_intelligence_service.py:
- balance classification from benchmark evidence with uncertainty grading
- never emits a bottleneck percentage
- workload suitability per profile from scenario scores
- compatibility passthrough (M32-RULES-v2 verbatim) + summary mapping
- partial builds never COMPATIBLE; missing slots named
- power: M2.5 TDP-reference policy, labeled reference not measured
- upgrade suggestions respect evidence gate + socket compatibility
- determinism
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
from backend.app.services import build_intelligence_service, compatibility_service
from backend.app.services.build_intelligence_service import analyze_build
from backend.app.services.scenario_scoring import derive_anchors


class _Env:
    def __init__(self):
        self._saved_main = main.SessionLocal
        self._saved_compat = compatibility_service.SessionLocal
        self._saved_intel = build_intelligence_service.SessionLocal
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
        self.client = TestClient(main.app)

    def teardown(self):
        main.SessionLocal = _saved_main = self._saved_main
        compatibility_service.SessionLocal = self._saved_compat
        build_intelligence_service.SessionLocal = self._saved_intel


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
            cores=cores, threads=(cores * 2 if cores else None),
            base_clock_ghz=3.0, boost_clock_ghz=4.4, tdp_w=tdp, socket=socket,
        ),
        benchmark_results=benchmarks,
    )


def _gpu(hw_id, name, memory_gb=16.0, tdp=250.0, interface="PCIe 4.0",
         mc_benchmarks: list | None = None):
    """mc_benchmarks: list of (score, test_type) tuples to seed as ORM rows."""
    benchmarks = []
    if mc_benchmarks:
        for score, test_type in mc_benchmarks:
            benchmarks.append(
                BenchmarkResult(benchmark_name="Geekbench 7", score=float(score),
                                unit="points", test_type=test_type)
            )
    return Hardware(
        id=hw_id, name=name, manufacturer="M", type="GPU",
        gpu_specification=GPUSpecification(
            memory_gb=memory_gb, memory_type="GDDR6X", core_clock_mhz=1800.0,
            boost_clock_mhz=2100.0, vram_bandwidth_gbps=760.0,
            memory_bus_width_bits=320, tdp_w=tdp, interface=interface,
        ),
        benchmark_results=benchmarks,
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
        # anchored CPU population
        for i, mc in enumerate((2100, 3030, 5000, 8200, 13100, 16500), start=1):
            s.add(_cpu(100 + i, f"CPU{i:02d}", float(mc), float(mc) / 6))
        # strong vs weak GPU pair (spec-only, no GPU benchmarks exist);
        # GPU Strong additionally carries a measured multi-core record for
        # the balance-ratio path (hypothetical comparable-benchmark case).
        s.add(_gpu(300, "GPU Strong", memory_gb=24.0, tdp=450.0,
                   mc_benchmarks=[(12000.0, "multi-core")]))
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


def _analyze(env, components, anchors=None):
    return analyze_build(components, anchors=anchors or _anchors(env),
                         session_factory=env.session_factory)


# ------------------------------------------------------------------ balance --

def test_version_pinned():
    assert build_intelligence_service.BUILD_INTELLIGENCE_VERSION == "M4-BUILD-v1.0"


def test_balance_classified_from_benchmark_ratio(env):
    _seed(env)
    # GPU Strong (id 300) carries a measured multi-core record; both sides
    # have comparable benchmark evidence -> ratio is computed.
    out = _analyze(env, {"cpu": 105, "gpu": 300})  # CPU mc=16500 vs GPU 12000
    balance = out["balance"]
    assert balance["classification"] in ("cpu_bound", "gpu_bound", "balanced")
    assert balance["basis"] == "multi_core_score_ratio"
    assert balance["uncertainty"] in ("low", "medium", "high")
    assert "ratio" in balance["explanation"].lower()
    assert "bottleneck" not in balance["explanation"].lower()


def test_balance_unknown_for_spec_only_gpu(env):
    """Spec-only GPU (the real dataset condition) -> unknown, never a
    fabricated ratio from VRAM/clock specs."""
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 301})
    balance = out["balance"]
    assert balance["classification"] == "unknown"
    assert balance["basis"] == "insufficient"
    assert balance["uncertainty"] == "high"
    assert "estimat" in balance["explanation"].lower()


def test_balance_unknown_without_evidence(env):
    _seed(env)
    with env.session_factory() as s:
        s.add(Hardware(id=900, name="Bare CPU", manufacturer="M", type="CPU"))
        s.commit()
    out = _analyze(env, {"cpu": 900, "gpu": 300})
    assert out["balance"]["classification"] == "unknown"
    assert out["balance"]["basis"] == "insufficient"
    assert out["balance"]["uncertainty"] == "high"


def test_no_bottleneck_percentage_ever(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300})
    blob = str(out).lower()
    assert "bottleneck_percent" not in blob
    assert "bottleneck percentage" not in blob


def test_workload_suitability_present_with_profiles(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300})
    ws = out["workload_suitability"]
    assert "software_development" in ws and "esports_gaming" in ws
    for profile_key, entry in ws.items():
        assert "score" in entry and "confidence" in entry


def test_compatibility_passthrough_and_summary(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300, "motherboard": 400, "psu": 600})
    compat = out["compatibility"]
    assert compat["rules_version"] == "M32-RULES-v2"
    assert out["compatibility_summary"]["overall"] in (
        "COMPATIBLE", "INCOMPATIBLE", "UNKNOWN", "NOT_EVALUATED")
    assert isinstance(out["compatibility_summary"]["unknown_rules"], list)


def test_partial_build_never_compatible(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300})
    assert out["missing_slots"] == ["motherboard", "ram", "storage", "psu"]
    assert out["compatibility_summary"]["overall"] != "COMPATIBLE"
    assert out["compatibility_summary"]["overall"] in ("UNKNOWN", "NOT_EVALUATED")


def test_power_reference_labeled_not_measured(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300, "psu": 600})
    power = out["power"]
    assert power["mode"] == "reference"
    assert power["basis"].lower().startswith("m2.5")
    assert isinstance(power["reference_w"], int)
    assert any("not measured" in lim.lower() or "listed" in lim.lower()
               for lim in power["limitations"])


def test_power_unknown_when_tdp_missing(env):
    _seed(env)
    with env.session_factory() as s:
        s.add(_cpu(110, "NoTDP CPU", 9000.0, 1500.0, tdp=None))
        s.commit()
    out = _analyze(env, {"cpu": 110, "gpu": 300, "psu": 600})
    assert out["power"]["mode"] == "unknown"
    assert out["power"]["reference_w"] is None


def test_psu_below_reference_is_incompatible(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300, "psu": 601})  # 300W PSU
    summary = out["compatibility_summary"]
    assert summary["overall"] == "INCOMPATIBLE"
    assert "psu-build-wattage" in summary["incompatible_rules"]


def test_upgrade_suggestions_respect_evidence_and_socket(env):
    _seed(env)
    out = _analyze(env, {"cpu": 101, "gpu": 301, "motherboard": 400})  # weakest CPU, weak GPU
    ups = out["upgrades"]
    assert ups, "expected at least one upgrade suggestion"
    cpu_ups = [u for u in ups if u["target_slot"] == "cpu"]
    assert cpu_ups
    for u in cpu_ups:
        assert u["direction"] == "upgrade"
        assert u["evidence"] in ("benchmark", "spec")
        if u["candidate_hint"]:
            hint = u["candidate_hint"]
            assert hint["hardware_id"] not in (101,)
            # candidate must be socket-compatible or carry an unknown-compat caveat
            if hint.get("socket_compatible") is False:
                assert any("unknown" in r.lower() or "not compatible" in r.lower()
                           for r in u["rationale"])
            else:
                assert hint.get("socket_compatible") in (True, None)
        assert u["rationale"]


def test_budget_alternatives_empty_with_reason(env):
    _seed(env)
    out = _analyze(env, {"cpu": 105, "gpu": 300})
    assert out["budget_alternatives"] == []
    assert any("price" in s.lower() for s in out["limitations"])


def test_determinism(env):
    _seed(env)
    a = _analyze(env, {"cpu": 105, "gpu": 300, "motherboard": 400})
    b = _analyze(env, {"cpu": 105, "gpu": 300, "motherboard": 400})
    assert a == b


# ------------------------------------------------------------------- route ---

def test_build_intelligence_route(env):
    _seed(env)
    resp = env.client.post("/build/intelligence", json={"cpu": 105, "gpu": 300})
    assert resp.status_code == 200
    body = resp.json()
    assert body["build_intelligence_version"] == "M4-BUILD-v1.0"
    assert "balance" in body and "compatibility_summary" in body


def test_build_intelligence_route_404_unknown_id(env):
    _seed(env)
    resp = env.client.post("/build/intelligence", json={"cpu": 99999})
    assert resp.status_code == 404
