"""Tests for the Stage 5 workload-evidence analyzer.

Encodes the contract:
- ``analyze_hardware_evidence`` takes (hardware_type, workload, benchmark_families,
  spec_ok, provenance_ok) and returns the same evidence signals the suitability
  service uses (attribution/spec/provenance/workload_match) as booleans, plus a
  verdict: ``rated`` or ``unrated`` with the same semantics.
- ``aggregate_by_workload`` counts catalog-scale coverage per (type, workload):
  how many hardware rows have relevant benchmark evidence vs spec vs provenance.
- ``report`` is a deterministic dict (sorted keys) derived from SQL over a dev DB.
- The honest boundary: ai_ml has no supported benchmark family -> attribution and
  workload_match are always False and its verdict can never be benchmark-driven.
- No fabrication: all values come from real rows or the caller's facts.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    FieldProvenance,
    GPUSpecification,
    Hardware,
    Source,
)
from backend.app.scripts import workload_evidence as we


# ---------------------------------------------------------------------------
# Unit: per-hardware evidence reproduction (no DB)
# ---------------------------------------------------------------------------


class TestHardwareEvidence:
    def test_multicore_attribution_true_when_multicore_benchmark(self):
        result = we.analyze_hardware_evidence(
            hardware_type="CPU", workload="gaming",
            benchmark_families={"multi-core"},
            spec_ok=True, provenance_ok=True,
        )
        assert result["signals"]["attribution"] is True
        assert result["signals"]["workload_match"] is True
        assert result["verdict"] == "rated"

    def test_singlecore_benchmark_does_not_credit_multicore_workload(self):
        result = we.analyze_hardware_evidence(
            hardware_type="CPU", workload="gaming",
            benchmark_families={"single-core"},
            spec_ok=True, provenance_ok=True,
        )
        assert result["signals"]["attribution"] is False
        assert result["signals"]["workload_match"] is False

    def test_ai_ml_never_has_benchmark_attribution(self):
        result = we.analyze_hardware_evidence(
            hardware_type="GPU", workload="ai_ml",
            benchmark_families={"multi-core", "single-core"},
            spec_ok=True, provenance_ok=True,
        )
        assert result["signals"]["attribution"] is False
        assert result["signals"]["workload_match"] is False
        # The verdict stays unrated even with spec+provenance, matching the
        # suitability service's hard boundary for ai_ml.
        assert result["verdict"] == "unrated"

    def test_no_evidence_is_unrated(self):
        result = we.analyze_hardware_evidence(
            hardware_type="CPU", workload="gaming",
            benchmark_families=set(), spec_ok=False, provenance_ok=False,
        )
        assert result["signals"]["attribution"] is False
        assert result["signals"]["spec"] is False
        assert result["signals"]["provenance"] is False
        assert result["verdict"] == "unrated"

    def test_gaming_requires_multicore_family(self):
        # gaming maps to multi-core (same as suitability service).
        assert we.workload_family("gaming") == "multi-core"
        assert we.workload_family("productivity") == "single-core"
        assert we.workload_family("ai_ml") is None


# ---------------------------------------------------------------------------
# Aggregation over an in-memory engine
# ---------------------------------------------------------------------------


class EngineBase:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def teardown_method(self):
        self.engine.dispose()

    def _seed(self, spec_type="CPU", with_bench=False, verified=False,
              spec_ok=True):
        with self.session_factory() as session:
            hw = Hardware(name="Chip", manufacturer="MFR", type=spec_type)
            session.add(hw)
            session.flush()
            if spec_type == "CPU":
                session.add(CPUSpecification(
                    hardware_id=hw.id,
                    cores=8 if spec_ok else None,
                    threads=16 if spec_ok else None,
                    base_clock_ghz=3.0 if spec_ok else None,
                ))
            else:
                session.add(GPUSpecification(
                    hardware_id=hw.id,
                    memory_gb=8 if spec_ok else None,
                    memory_type="GDDR6" if spec_ok else None,
                    core_clock_mhz=1500 if spec_ok else None,
                ))
            if with_bench:
                session.add(BenchmarkResult(
                    hardware_id=hw.id,
                    benchmark_name="Geekbench 7",
                    score=12000, unit="points",
                    test_type="multi-core",
                ))
            if verified:
                source = session.scalar(select(Source).where(Source.name == "S"))
                if source is None:
                    source = Source(name="S", url="https://s.example")
                    session.add(source)
                    session.flush()
                session.add(FieldProvenance(
                    hardware_id=hw.id, source_id=source.id,
                    table_name=spec_type.lower() + "_specifications",
                    field_name="cores", evidenced_value="8",
                    source_url="https://s.example", evidence_status="verified",
                    batch_no=1,
                ))
            session.commit()


class TestCatalogAggregation(EngineBase):
    def test_counts_benchmark_evidence_per_workload(self):
        self._seed(spec_type="CPU", with_bench=True, verified=True)
        self._seed(spec_type="CPU", with_bench=False, verified=True)
        agg = we.aggregate_by_workload(self.session_factory)
        cpu_gaming = next(a for a in agg["cpu"] if a["workload"] == "gaming")
        assert cpu_gaming["total"] == 2
        assert cpu_gaming["with_benchmark_evidence"] == 1
        assert cpu_gaming["with_spec_evidence"] == 2
        assert cpu_gaming["with_provenance"] == 2

    def test_ai_ml_counts_never_include_benchmark_evidence(self):
        self._seed(spec_type="GPU", with_bench=True, verified=True)
        agg = we.aggregate_by_workload(self.session_factory)
        gpu_aiml = next(a for a in agg["gpu"] if a["workload"] == "ai_ml")
        assert gpu_aiml["total"] == 1
        assert gpu_aiml["with_benchmark_evidence"] == 0  # ai_ml has no family


# ---------------------------------------------------------------------------
# Deterministic report + serialization
# ---------------------------------------------------------------------------


class TestReportShape:
    def test_report_has_all_workloads_for_both_types(self, tmp_path):
        report = we.make_catalog_report()
        assert set(report["by_type"]) == {"cpu", "gpu"}
        for t in ("cpu", "gpu"):
            workloads = {a["workload"] for a in report["by_type"][t]}
            assert {"gaming", "workstation", "productivity",
                    "content_creation", "ai_ml"} <= workloads

    def test_report_matches_known_gpu_benchmark_zero(self, tmp_path):
        # The catalog has 0 GPU benchmark rows: ai_ml is unrated everywhere.
        report = we.make_catalog_report()
        gpu_aiml = next(a for a in report["by_type"]["gpu"]
                        if a["workload"] == "ai_ml")
        assert gpu_aiml["with_benchmark_evidence"] == 0
        assert gpu_aiml["unrated_boundary"] is True

    def test_report_json_roundtrip(self, tmp_path):
        report = we.make_catalog_report()
        text = json.dumps(report, sort_keys=True)
        assert '"by_type"' in text
        (tmp_path / "we.json").write_text(text, encoding="utf-8")
        assert (tmp_path / "we.json").stat().st_size > 0
