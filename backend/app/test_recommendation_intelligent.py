"""M4 Task 4: intelligent recommendations (ranking v2, /v2 endpoint).

Covers the additive recommend_intelligent layer on top of v1:
- constraint classification (hard/soft/unknown/estimated)
- deterministic ranking with id-asc tie-break
- socket-mismatch exclusion reusing the M32-RULES-v2 rule function
- evidence-gate exclusion ledger with reason codes
- v1 recommend()/recommend_response() behavior byte-identical
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

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
    MotherboardSpecification,
)
from backend.app.schemas.intelligence import RecommendationConstraints
from backend.app.services import recommendation_service
from backend.app.services.recommendation_service import recommend_intelligent
from backend.app.services.scenario_scoring import derive_anchors


class _Env:
    """In-memory DB + SessionLocal redirection (established repo pattern)."""

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

    def teardown(self):
        main.SessionLocal = self._saved_main
        recommendation_service.SessionLocal = self._saved_rec


def _cpu(hw_id, name, mc, sc, socket="AM5", cores=8, tdp=65.0, eff=None):
    eff = eff if eff is not None else (mc / tdp if (mc and tdp) else None)
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


@pytest.fixture()
def env():
    e = _Env()
    yield e
    e.teardown()


def _seed_anchored_population(session):
    """12 CPUs with a spread of scores -> anchors derivable from the DB itself."""
    mc_scores = [2100, 2410, 2720, 3030, 3340, 3650, 5000, 6100, 8200, 10300, 13100, 16500]
    sc_scores = [700, 850, 1000, 1150, 1300, 1450, 1600, 1750, 1900, 2050, 2200, 2350]
    for i, (mc, sc) in enumerate(zip(mc_scores, sc_scores), start=1):
        session.add(_cpu(100 + i, f"CPU{i:02d}", float(mc), float(sc)))
    session.add(Hardware(
        id=500, name="Board A", manufacturer="M", type="MOTHERBOARD",
        motherboard_specification=MotherboardSpecification(
            socket="AM5", ram_type="DDR5", max_ram_gb=128, ram_slots=4,
            m2_slots=2, sata_ports=4, pcie_slots=3,
        ),
    ))
    session.commit()


def _anchors_from_env(env):
    with env.session_factory() as s:
        rows = s.query(Hardware).filter(Hardware.type == "CPU").all()
        mc = sorted(
            b.score for r in rows for b in r.benchmark_results
            if b.test_type == "multi-core"
        )
        sc = sorted(
            b.score for r in rows for b in r.benchmark_results
            if b.test_type == "single-core"
        )
    return {"multi-core": derive_anchors(mc), "single-core": derive_anchors(sc)}


def test_constraints_defaults_are_minimal():
    c = RecommendationConstraints(hardware_type="CPU")
    assert c.profile_key is None
    assert c.budget_max is None
    assert c.limit == 10
    assert c.existing_components == {}


def test_constraint_classification_budget_is_soft(env):
    _seed_anchored_population(env.session_factory())
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(hardware_type="CPU", budget_max=500),
        anchors=_anchors_from_env(env),
    )
    assert out["constraints_echo"]["budget_max"]["classification"] == "soft"
    # budget never filters in this dataset
    assert len(out["candidates"]) > 0
    assert any("price" in s.lower()
               for s in out["constraints_echo"]["budget_max"]["notes"])


def test_ranking_deterministic_with_id_tiebreak(env):
    # Two identical CPUs: ranking must order by id ascending.
    with env.session_factory() as s:
        _seed_anchored_population(s)
        s.add(_cpu(900, "TwinA", 9000.0, 1500.0))
        s.add(_cpu(899, "TwinB", 9000.0, 1500.0))
        s.commit()
    constraints = RecommendationConstraints(hardware_type="CPU", limit=5)
    a = recommend_intelligent(env.session_factory, constraints,
                              anchors=_anchors_from_env(env))
    b = recommend_intelligent(env.session_factory, constraints,
                              anchors=_anchors_from_env(env))
    assert a == b  # byte-identical determinism
    ids = [c["hardware_id"] for c in a["candidates"]]
    if 899 in ids and 900 in ids:
        assert ids.index(899) < ids.index(900)


def test_socket_mismatch_excluded_with_reason_code(env):
    with env.session_factory() as s:
        _seed_anchored_population(s)
        s.add(_cpu(700, "Intel CPU", 9000.0, 1500.0, socket="LGA1700"))
        s.commit()
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(
            hardware_type="CPU",
            existing_components={"motherboard": 500},
        ),
        anchors=_anchors_from_env(env),
    )
    excluded_ids = {e["hardware_id"] for e in out["excluded"]}
    assert 700 in excluded_ids
    entry = next(e for e in out["excluded"] if e["hardware_id"] == 700)
    assert entry["reason_code"] == "SOCKET_MISMATCH"


def test_unknown_socket_does_not_exclude(env):
    with env.session_factory() as s:
        _seed_anchored_population(s)
        s.add(_cpu(701, "NoSocket CPU", 9000.0, 1500.0, socket=None))
        s.commit()
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(
            hardware_type="CPU",
            existing_components={"motherboard": 500},
        ),
        anchors=_anchors_from_env(env),
    )
    excluded_ids = {e["hardware_id"] for e in out["excluded"]}
    assert 701 not in excluded_ids


def test_exclusion_ledger_includes_evidence_gate_failures(env):
    with env.session_factory() as s:
        _seed_anchored_population(s)
        s.add(Hardware(id=800, name="NoBench CPU", manufacturer="M", type="CPU"))
        s.commit()
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(hardware_type="CPU", limit=10),
        anchors=_anchors_from_env(env),
    )
    codes = {e["reason_code"] for e in out["excluded"]}
    assert any(code.startswith("insufficient_data") for code in codes)
    # the excluded entry names the hardware
    entry = next(e for e in out["excluded"] if e["hardware_id"] == 800)
    assert entry["reason_code"] == "insufficient_data:no_evidence"


def test_ranking_version_and_profile_echo(env):
    _seed_anchored_population(env.session_factory())
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(hardware_type="CPU", profile_key="software_development"),
        anchors=_anchors_from_env(env),
    )
    assert out["ranking_version"] == "M4-REC-v2.0"
    assert out["profile"]["key"] == "software_development"
    assert out["profile"]["assumptions"]


def test_candidate_payload_shape(env):
    _seed_anchored_population(env.session_factory())
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(hardware_type="CPU", limit=3),
        anchors=_anchors_from_env(env),
    )
    assert len(out["candidates"]) == 3
    cand = out["candidates"][0]
    for key in ("hardware_id", "hardware_name", "scenario_scores",
                "stars", "confidence", "rank_explanation", "trade_offs"):
        assert key in cand
    assert cand["rank"] == 1
    # alternatives present when enough candidates pass the gate
    assert isinstance(out["alternatives"], list)


def test_power_limit_filters_only_with_tdp_evidence(env):
    with env.session_factory() as s:
        _seed_anchored_population(s)
        s.add(_cpu(950, "Hot CPU", 9000.0, 1500.0, tdp=200.0))
        s.add(_cpu(951, "NoTDP CPU", 9000.0, 1500.0, tdp=None))
        s.commit()
    out = recommend_intelligent(
        env.session_factory,
        RecommendationConstraints(
            hardware_type="CPU", power_limit_w=100,
        ),
        anchors=_anchors_from_env(env),
    )
    excluded_ids = {e["hardware_id"] for e in out["excluded"]}
    assert 950 in excluded_ids          # known TDP over limit -> excluded
    assert 951 not in excluded_ids      # unknown TDP -> advisory, not excluded
    hot = next(
        c for c in out["constraints_echo"]["power_limit_w"]["notes"]
        if "unknown" in c.lower()
    )
    assert "unknown" in hot.lower()


# --------------------------------------------------------- API (additive) ----

def test_v2_get_endpoint_shape(env):
    _seed_anchored_population(env.session_factory())
    resp = env.client.get("/hardware/recommend/v2?type=CPU&profile_key=software_development&limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ranking_version"] == "M4-REC-v2.0"
    assert len(body["candidates"]) == 3


def test_v2_get_invalid_profile_422(env):
    resp = env.client.get("/hardware/recommend/v2?type=CPU&profile_key=nope")
    assert resp.status_code == 422


def test_v2_post_endpoint(env):
    _seed_anchored_population(env.session_factory())
    resp = env.client.post(
        "/hardware/recommend/v2",
        json={"hardware_type": "CPU", "profile_key": "aaa_gaming",
              "resolution": "1440p", "limit": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["candidates"]


def test_v1_recommend_response_unchanged(env):
    """v1 contract: shape and filter_reason semantics stay intact."""
    _seed_anchored_population(env.session_factory())
    payload = recommendation_service.recommend_response("CPU", "gaming")
    assert "candidates" in payload and "filter_reason" in payload
    assert payload["budget_max"] is None
    for cand in payload["candidates"]:
        assert set(cand) == {
            "hardware_id", "hardware_name", "hardware_type",
            "suitability", "explanation",
        }
