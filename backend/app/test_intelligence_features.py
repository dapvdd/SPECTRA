"""M4 Task 1: deterministic feature layer (missing-vs-zero, coverage, provenance).

Covers backend/app/services/intelligence_features.py:
- absent spec fields are None + listed in ``missing`` (never conflated with zero)
- benchmark families observed on the row; best score per family
- efficiency derivation guards (missing tdp / zero tdp)
- min-max normalisation clamps instead of extrapolating
- coverage = share of non-null features over the type-applicable feature set
- provenance summary and data-freshness summary
- determinism: identical input -> identical payload
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.services.intelligence_features import (  # noqa: E402
    CPU_FEATURES,
    FEATURE_VERSION,
    features_from_hardware,
    derive_efficiency,
    normalise,
)


def _cpu(**spec_overrides):
    spec = {
        "cores": 8, "threads": 16, "base_clock_ghz": 3.0,
        "boost_clock_ghz": None, "tdp_w": 65.0, "socket": None,
        "process_node_nm": None,
    }
    spec.update(spec_overrides)
    return SimpleNamespace(
        id=1, name="TestCPU", manufacturer="M", type="CPU",
        architecture="Zen 4", segment=None, release_date=None,
        cpu_specification=SimpleNamespace(**spec),
        gpu_specification=None,
        benchmark_results=[
            SimpleNamespace(test_type="single-core", score=1500.0, recorded_at=None, source_id=None),
            SimpleNamespace(test_type="multi-core", score=9000.0, recorded_at=None, source_id=None),
            SimpleNamespace(test_type="multi-core", score=8000.0, recorded_at=None, source_id=None),
        ],
        field_provenance=[
            SimpleNamespace(table_name="cpu_specifications", field_name="cores", evidence_status="verified"),
            SimpleNamespace(table_name="cpu_specifications", field_name="cores", evidence_status="uncertain"),
        ],
    )


def _gpu(**spec_overrides):
    spec = {
        "memory_gb": 8.0, "memory_type": "GDDR6", "core_clock_mhz": 1500.0,
        "boost_clock_mhz": None, "vram_bandwidth_gbps": None,
        "memory_bus_width_bits": None, "tdp_w": None, "interface": None, "length_mm": None,
    }
    spec.update(spec_overrides)
    return SimpleNamespace(
        id=2, name="TestGPU", manufacturer="M", type="GPU",
        architecture=None, segment=None, release_date=None,
        cpu_specification=None,
        gpu_specification=SimpleNamespace(**spec),
        benchmark_results=[], field_provenance=[],
    )


def test_feature_version_is_pinned():
    assert FEATURE_VERSION == "M4-FEATURES-v1"


def test_missing_boost_is_none_and_listed_not_zero():
    hw = _cpu()
    out = features_from_hardware(hw)
    assert out["features"]["boost_clock_ghz"] is None
    assert "boost_clock_ghz" in out["missing"]


def test_zero_tdp_is_present_and_not_missing():
    hw = _cpu(tdp_w=0.0)
    out = features_from_hardware(hw)
    assert out["features"]["tdp_w"] == 0.0
    assert "tdp_w" not in out["missing"]


def test_benchmark_best_score_per_family_and_families_list():
    out = features_from_hardware(_cpu())
    assert out["features"]["multi_core_score"] == 9000.0
    assert out["features"]["single_core_score"] == 1500.0
    assert sorted(out["benchmark_families"]) == ["multi-core", "single-core"]


def test_cpu_without_benchmarks_has_no_families_and_none_scores():
    out = features_from_hardware(_cpu())
    hw = _cpu()
    hw.benchmark_results = []
    out2 = features_from_hardware(hw)
    assert out2["features"]["multi_core_score"] is None
    assert out2["benchmark_families"] == []


def test_gpu_features_only_apply_to_gpu_type():
    out = features_from_hardware(_gpu())
    assert out["features"]["memory_gb"] == 8.0
    assert out["type"] == "GPU"
    # CPU-only features are absent from a GPU vector, not zero.
    assert "cores" not in out["features"]


def test_cpu_vector_has_no_gpu_features():
    out = features_from_hardware(_cpu())
    assert "memory_gb" not in out["features"]


def test_coverage_is_share_of_present_features():
    out = features_from_hardware(_cpu())
    present = sum(v is not None for v in out["features"].values())
    expected = present / len(out["features"])
    assert out["coverage"] == round(expected, 4)


def test_coverage_zero_when_no_features_present():
    hw = _cpu(cores=None, threads=None, base_clock_ghz=None, tdp_w=None,
              socket=None, process_node_nm=None)
    hw.architecture = None
    hw.benchmark_results = []
    out = features_from_hardware(hw)
    assert out["coverage"] == 0.0


def test_efficiency_derivation_and_guards():
    assert derive_efficiency(9000.0, 65.0) == round(9000.0 / 65.0, 4)
    assert derive_efficiency(None, 65.0) is None
    assert derive_efficiency(9000.0, None) is None
    assert derive_efficiency(9000.0, 0.0) is None
    assert derive_efficiency(9000.0, -5.0) is None


def test_efficiency_feature_none_when_inputs_missing():
    out = features_from_hardware(_cpu(tdp_w=None))
    assert out["features"]["efficiency"] is None
    assert "efficiency" in out["missing"]


def test_normalise_clamps_and_passes_none():
    assert normalise(None, 0.0, 100.0) is None
    assert normalise(-10.0, 0.0, 100.0) == 0.0
    assert normalise(150.0, 0.0, 100.0) == 1.0
    assert round(normalise(50.0, 0.0, 100.0), 6) == 0.5
    assert normalise(5.0, 5.0, 5.0) == 0.0  # degenerate range


def test_provenance_verified_fields_summarised():
    out = features_from_hardware(_cpu())
    assert out["provenance_verified_fields"] == ["cpu_specifications.cores"]


def test_data_freshness_reports_absent_timestamps():
    out = features_from_hardware(_cpu())
    assert out["data_freshness"] == {"recorded_at_present": False, "latest_recorded_at": None}


def test_determinism_same_input_same_payload():
    a = features_from_hardware(_cpu())
    b = features_from_hardware(_cpu())
    assert a == b
