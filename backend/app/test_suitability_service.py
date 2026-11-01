"""Tests for the SPECTRA evidence-quality scoring (Objective C).

Evidence quality is a SEPARATE dimension from suitability: it measures how
trustworthy our data is for a hardware+workload pair (0..1 float + confidence),
independent of how good the hardware is. These tests pin the weighted-signal
formula deterministically.
"""

from __future__ import annotations

from backend.app.services.suitability_service import score_evidence_quality


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


def _hardware(
    *,
    hw_type="CPU",
    cpu_spec=None,
    gpu_spec=None,
    benchmarks=(),
    provenance=(),
):
    class Hardware:
        pass

    hw = Hardware()
    hw.type = hw_type
    hw.cpu_specification = cpu_spec
    hw.gpu_specification = gpu_spec
    hw.benchmark_results = list(benchmarks)
    hw.field_provenance = list(provenance)
    return hw


def _benchmark(test_type="multi-core"):
    class Benchmark:
        pass

    b = Benchmark()
    b.test_type = test_type
    return b


def _full_cpu_spec():
    return _Spec(
        cores=8, threads=16, base_clock_ghz=3.4,
        boost_clock_ghz=4.8, socket="AM5", tdp_w=105,
    )


def test_evidence_quality_high_for_benchmarked_complete_hardware():
    hw = _hardware(
        cpu_spec=_full_cpu_spec(),
        benchmarks=[_benchmark("multi-core")],
        provenance=[_Prov("verified")],
    )
    result = score_evidence_quality(hw, "gaming")
    assert result["score"] == 1.0
    assert result["confidence"] == "high"


def test_evidence_quality_low_when_no_benchmarks_and_no_specs():
    hw = _hardware()
    result = score_evidence_quality(hw, "gaming")
    assert result["score"] == 0.0
    assert result["confidence"] == "low"


def test_evidence_quality_medium_with_benchmark_but_no_spec_or_provenance():
    # A relevant benchmark fires attribution (0.35) AND workload_match (0.20),
    # but with no spec (0.25) and no provenance (0.20): 0.35 + 0.20 = 0.55.
    hw = _hardware(benchmarks=[_benchmark("multi-core")])
    result = score_evidence_quality(hw, "workstation")
    assert result["score"] == 0.55
    assert result["confidence"] == "medium"


def test_evidence_quality_requires_workload_benchmark_family_match():
    # single-core benchmark does NOT satisfy workstation (needs multi-core)
    hw = _hardware(
        cpu_spec=_full_cpu_spec(),
        benchmarks=[_benchmark("single-core")],
        provenance=[_Prov("verified")],
    )
    result = score_evidence_quality(hw, "workstation")
    # attribution off (no relevant benchmark) -> 0.25 + 0.20 = 0.45
    assert result["score"] == 0.45
    assert result["confidence"] == "medium"


def test_evidence_quality_ai_ml_has_no_benchmark_family():
    # AI/ML has no supported benchmark family in this dataset (no GPU benches).
    hw = _hardware(
        gpu_spec=_Spec(memory_gb=12, memory_type="GDDR6"),
    )
    result = score_evidence_quality(hw, "ai_ml")
    assert result["score"] == 0.0
    assert result["confidence"] == "low"
