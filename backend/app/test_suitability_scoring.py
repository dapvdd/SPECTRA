"""Sensitivity and regression tests for suitability + evidence scoring.

These tests guard the two most critical correctness properties of the
Objective B/C engine: determinism (same input -> same output, always) and
bound invariants (evidence score in 0..1, stars in 0..5, valid confidence)
across every supported workload. They are cheap to run so they can be trusted
as a regression gate on the whole scoring pipeline.
"""

from __future__ import annotations

from backend.app.services.suitability_service import (
    WORKLOADS,
    rate_suitability,
    score_evidence_quality,
)


class _Spec:
    def __init__(self, **kw):
        self.cores = kw.get("cores")
        self.threads = kw.get("threads")
        self.base_clock_ghz = kw.get("base_clock_ghz")
        self.boost_clock_ghz = kw.get("boost_clock_ghz")
        self.socket = kw.get("socket")
        self.tdp_w = kw.get("tdp_w")
        self.memory_gb = kw.get("memory_gb")
        self.memory_type = kw.get("memory_type")
        self.core_clock_mhz = kw.get("core_clock_mhz")
        self.memory_bus_width_bits = kw.get("memory_bus_width_bits")


class _Prov:
    def __init__(self, status):
        self.evidence_status = status


class _Benchmark:
    def __init__(self, test_type, score):
        self.test_type = test_type
        self.score = score


class _Hardware:
    type = "CPU"

    def __init__(self, spec, benchmarks, provenance):
        self.cpu_specification = spec
        self.gpu_specification = None
        self.benchmark_results = benchmarks
        self.field_provenance = provenance


def _full_cpu():
    return _Hardware(
        spec=_Spec(
            cores=16, threads=32, base_clock_ghz=4.5,
            boost_clock_ghz=5.7, socket="AM5", tdp_w=170,
        ),
        benchmarks=[
            _Benchmark("multi-core", 16000),
            _Benchmark("single-core", 2200),
        ],
        provenance=[_Prov("verified")],
    )


def _bare_cpu():
    return _Hardware(spec=None, benchmarks=[], provenance=[])


def test_suitability_same_input_always_same_output():
    hw = _full_cpu()
    for _ in range(100):
        assert rate_suitability(hw, "gaming") == rate_suitability(hw, "gaming")


def test_all_categories_return_valid_stars():
    hw = _full_cpu()
    for workload in WORKLOADS:
        rating = rate_suitability(hw, workload)
        assert 0 <= rating["stars"] <= 5
        assert rating["confidence"] in (
            "high", "medium", "low", "unrated",
        )
        assert 0.0 <= rating["raw_score"] <= 5.0


def test_evidence_quality_score_in_0_to_1():
    for hardware, workload in (
        (_full_cpu(), "gaming"),
        (_full_cpu(), "ai_ml"),
        (_bare_cpu(), "workstation"),
        (_bare_cpu(), "productivity"),
    ):
        evidence = score_evidence_quality(hardware, workload)
        assert 0.0 <= evidence["score"] <= 1.0
        assert evidence["confidence"] in ("high", "medium", "low")


def test_rating_stars_monotonic_in_raw_score():
    """A higher raw score never produces a lower star count."""
    hw_low = _Hardware(
        spec=_full_cpu().cpu_specification,
        benchmarks=[_Benchmark("multi-core", 1500)],
        provenance=[_Prov("verified")],
    )
    hw_high = _Hardware(
        spec=_full_cpu().cpu_specification,
        benchmarks=[_Benchmark("multi-core", 18000)],
        provenance=[_Prov("verified")],
    )
    rating_low = rate_suitability(hw_low, "workstation")
    rating_high = rate_suitability(hw_high, "workstation")
    assert rating_low["raw_score"] <= rating_high["raw_score"]
    assert rating_low["stars"] <= rating_high["stars"]


def test_evidence_score_stable_across_workloads_for_same_signals():
    """A fully-evidenced CPU scores high for every CPU-rated workload."""
    hw = _full_cpu()
    for workload in ("gaming", "workstation", "productivity", "content_creation"):
        evidence = score_evidence_quality(hw, workload)
        assert evidence["score"] >= 0.8
