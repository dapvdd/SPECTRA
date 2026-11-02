"""Tests for Stage 6 calibration verification of the suitability star anchors.

Verifies that the star anchors hard-coded in
``backend.app.services.suitability_service`` are consistent with the actual
score distribution in the benchmarked population (without changing the scoring
methodology). Any drift is *reported*, not silently rewritten.

Contract:
- ``anchor_percentiles(conn, test_type)`` returns the observed p10..p90 score
  values for the given benchmark family from the dev DB.
- ``calibration_report()`` compares documented anchors vs observed percentiles
  and returns a deterministic dict with per-family ``documented``,
  ``observed``, ``max_pct_err``, ``status`` (``ok`` | ``drift``).
- The single-core / multi-core families must both be analyzable.
- Debugging/verification only: no scoring file is mutated by this module.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import BenchmarkResult, Hardware
from backend.app.scripts import calibration_verify as cv


def _engine_with_scores(scores, test_type="multi-core"):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    sf = sessionmaker(bind=engine)
    with sf() as session:
        for i, score in enumerate(scores):
            hw = Hardware(name=f"Chip{i}", manufacturer="MFR", type="CPU")
            session.add(hw)
            session.flush()
            session.add(BenchmarkResult(
                hardware_id=hw.id, benchmark_name="Geekbench 7",
                score=score, unit="points", test_type=test_type,
            ))
        session.commit()
    return engine


class TestAnchorPercentiles:
    def test_known_distribution_yields_known_percentiles(self):
        scores = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
        engine = _engine_with_scores(scores)
        sf = sessionmaker(bind=engine)
        pcts = cv.anchor_percentiles(sf, "multi-core")
        # p10 of 1..10 (n=10, nearest-rank p10 = 2nd) -> 2000 ... p90 -> 9000
        assert abs(pcts["p10"] - 2000) <= 1
        assert abs(pcts["p50"] - 5500) <= 500
        assert abs(pcts["p90"] - 9000) <= 1
        engine.dispose()

    def test_empty_population_returns_none(self):
        engine = _engine_with_scores([])
        sf = sessionmaker(bind=engine)
        pcts = cv.anchor_percentiles(sf, "multi-core")
        assert pcts is None or pcts.get("count", 0) == 0
        engine.dispose()


class TestCalibrationReport:
    def test_real_db_report_shape_and_families(self):
        report = cv.calibration_report()
        assert set(report["families"]) == {"single-core", "multi-core"}
        for fam in ("single-core", "multi-core"):
            entry = report["families"][fam]
            assert set(entry) == {"documented", "observed", "max_pct_err", "status"}
            assert len(entry["documented"]) == 5
            assert len(entry["observed"]) == 5

    def test_report_serializable_and_deterministic(self, tmp_path):
        report = cv.calibration_report()
        a = json.dumps(report, sort_keys=True)
        b = json.dumps(cv.calibration_report(), sort_keys=True)
        assert a == b
        (tmp_path / "cal.json").write_text(a, encoding="utf-8")
        assert (tmp_path / "cal.json").stat().st_size > 0
