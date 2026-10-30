import pytest

from backend.app.models.cpu import CPUSpecification
from backend.app.models.gpu import GPUSpecification
from backend.app.models.hardware import Hardware
from backend.app.services.comparison_service import compare_cpus, compare_gpus


def _cpu(name: str, **specification) -> Hardware:
    return Hardware(
        name=name,
        manufacturer="Vendor",
        type="CPU",
        cpu_specification=CPUSpecification(**specification),
    )


def _metric(result, name):
    return next(metric for metric in result.metrics if metric.name == name)


def test_reports_side_a_as_winner_when_its_value_is_higher():
    result = compare_cpus(
        _cpu("CPU A", cores=8, threads=16, base_clock_ghz=3.5, boost_clock_ghz=5.0, tdp_w=65),
        _cpu("CPU B", cores=6, threads=12, base_clock_ghz=3.0, boost_clock_ghz=4.5, tdp_w=125),
    )

    assert result.hardware_a == "CPU A"
    assert result.hardware_b == "CPU B"
    assert [metric.winner for metric in result.metrics] == ["a", "a", "a", "a", "a"]


def test_reports_side_b_as_winner_when_its_value_is_higher():
    result = compare_cpus(
        _cpu("CPU A", cores=6, threads=12, base_clock_ghz=3.0, boost_clock_ghz=4.5, tdp_w=125),
        _cpu("CPU B", cores=8, threads=16, base_clock_ghz=3.5, boost_clock_ghz=5.0, tdp_w=65),
    )

    assert [metric.winner for metric in result.metrics] == ["b", "b", "b", "b", "b"]


def test_exact_ties_are_reported_as_ties_not_winners():
    result = compare_cpus(
        _cpu("CPU A", cores=8, threads=16, base_clock_ghz=3.5, boost_clock_ghz=5.0, tdp_w=65),
        _cpu("CPU B", cores=8, threads=16, base_clock_ghz=3.5, boost_clock_ghz=5.0, tdp_w=65),
    )

    assert [metric.winner for metric in result.metrics] == ["tie", "tie", "tie", "tie", "tie"]
    assert [metric.difference for metric in result.metrics] == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_difference_is_signed_value_a_minus_value_b():
    result = compare_cpus(
        _cpu("CPU A", cores=12, threads=8),
        _cpu("CPU B", cores=8, threads=12),
    )

    assert _metric(result, "cores").difference == 4.0
    assert _metric(result, "threads").difference == -4.0


def test_difference_is_rounded_to_three_decimals():
    result = compare_cpus(
        _cpu("CPU A", boost_clock_ghz=5.2),
        _cpu("CPU B", boost_clock_ghz=4.8),
    )

    # 5.2 - 4.8 is 0.3999999999999995 in binary floating point.
    assert _metric(result, "boost_clock").difference == 0.4


@pytest.mark.parametrize(
    "field",
    ["cores", "threads", "base_clock_ghz", "boost_clock_ghz"],
)
def test_nullable_field_missing_on_side_a_is_unavailable(field):
    spec_a = {"cores": 8, "threads": 16, "base_clock_ghz": 3.5, "boost_clock_ghz": 5.0}
    spec_b = {"cores": 6, "threads": 12, "base_clock_ghz": 3.0, "boost_clock_ghz": 4.5}
    spec_a[field] = None

    result = compare_cpus(_cpu("CPU A", **spec_a), _cpu("CPU B", **spec_b))

    metric = _metric(
        result,
        {
            "cores": "cores",
            "threads": "threads",
            "base_clock_ghz": "base_clock",
            "boost_clock_ghz": "boost_clock",
        }[field],
    )

    assert metric.winner == "unavailable"
    assert metric.difference is None
    assert metric.value_a is None
    assert metric.value_b == spec_b[field]


@pytest.mark.parametrize(
    "field",
    ["cores", "threads", "base_clock_ghz", "boost_clock_ghz"],
)
def test_nullable_field_missing_on_side_b_is_unavailable(field):
    spec_a = {"cores": 8, "threads": 16, "base_clock_ghz": 3.5, "boost_clock_ghz": 5.0}
    spec_b = {"cores": 6, "threads": 12, "base_clock_ghz": 3.0, "boost_clock_ghz": 4.5}
    spec_b[field] = None

    result = compare_cpus(_cpu("CPU A", **spec_a), _cpu("CPU B", **spec_b))

    metric = _metric(
        result,
        {
            "cores": "cores",
            "threads": "threads",
            "base_clock_ghz": "base_clock",
            "boost_clock_ghz": "boost_clock",
        }[field],
    )

    assert metric.winner == "unavailable"
    assert metric.difference is None
    assert metric.value_a == spec_a[field]
    assert metric.value_b is None


def test_missing_values_never_become_a_tie_or_a_zero_difference():
    result = compare_cpus(
        _cpu("CPU A", cores=8),
        _cpu("CPU B", cores=None),
    )

    metric = _metric(result, "cores")

    assert metric.winner != "tie"
    assert metric.winner != "a"
    assert metric.winner != "b"
    assert metric.difference is None


def test_missing_value_on_both_sides_is_unavailable():
    result = compare_cpus(
        _cpu("CPU A", cores=None),
        _cpu("CPU B", cores=None),
    )

    metric = _metric(result, "cores")

    assert metric.winner == "unavailable"
    assert metric.value_a is None
    assert metric.value_b is None
    assert metric.difference is None


def test_every_supported_metric_is_reported_even_when_unavailable():
    result = compare_cpus(
        _cpu("CPU A", cores=8),
        _cpu("CPU B", cores=6),
    )

    assert [metric.name for metric in result.metrics] == [
        "cores",
        "threads",
        "base_clock",
        "boost_clock",
        "power_efficiency",
    ]
    assert [metric.unit for metric in result.metrics] == [
        "cores",
        "threads",
        "GHz",
        "GHz",
        "cores/W",
    ]


def test_power_efficiency_is_cores_per_watt_and_higher_is_winner():
    result = compare_cpus(
        _cpu("CPU A", cores=8, tdp_w=65),
        _cpu("CPU B", cores=8, tdp_w=95),
    )

    metric = _metric(result, "power_efficiency")

    assert metric.unit == "cores/W"
    # 8/65 = 0.1230769... ; 8/95 = 0.0842105...
    assert round(metric.value_a, 4) == 0.1231
    assert round(metric.value_b, 4) == 0.0842
    assert metric.winner == "a"


def test_power_efficiency_missing_tdp_is_unavailable_on_that_side():
    result = compare_cpus(
        _cpu("CPU A", cores=8, tdp_w=65),
        _cpu("CPU B", cores=8),
    )

    metric = _metric(result, "power_efficiency")

    assert metric.winner == "unavailable"
    assert metric.difference is None
    assert metric.value_b is None


def test_power_efficiency_missing_cores_is_unavailable():
    result = compare_cpus(
        _cpu("CPU A", cores=None, tdp_w=65),
        _cpu("CPU B", cores=8, tdp_w=65),
    )

    metric = _metric(result, "power_efficiency")

    assert metric.winner == "unavailable"
    assert metric.difference is None


def test_power_efficiency_never_uses_negative_or_zero_tdp():
    result = compare_cpus(
        _cpu("CPU A", cores=8, tdp_w=0),
        _cpu("CPU B", cores=8, tdp_w=-5),
    )

    metric = _metric(result, "power_efficiency")

    assert metric.winner == "unavailable"
    assert metric.value_a is None
    assert metric.value_b is None


def test_zero_is_compared_as_a_real_numeric_value():
    result = compare_cpus(
        _cpu("CPU A", cores=0, threads=4),
        _cpu("CPU B", cores=4, threads=0),
    )

    assert _metric(result, "cores").winner == "b"
    assert _metric(result, "threads").winner == "a"


def test_requires_cpu_specifications_on_both_sides():
    with pytest.raises(ValueError, match="CPU specifications"):
        compare_cpus(
            Hardware(name="CPU A", manufacturer="Vendor", type="CPU"),
            _cpu("CPU B", cores=6),
        )

    with pytest.raises(ValueError, match="CPU specifications"):
        compare_cpus(
            _cpu("CPU A", cores=6),
            Hardware(name="CPU B", manufacturer="Vendor", type="CPU"),
        )


# ---------------------------------------------------------------------------
# GPU comparison parity tests
# ---------------------------------------------------------------------------

def _gpu(name: str, **specification) -> Hardware:
    return Hardware(
        name=name,
        manufacturer="Vendor",
        type="GPU",
        gpu_specification=GPUSpecification(**specification),
    )


def test_gpu_side_a_wins_each_higher_is_better_metric():
    result = compare_gpus(
        _gpu(
            "GPU A",
            memory_gb=24.0,
            vram_bandwidth_gbps=960.0,
            core_clock_mhz=1400.0,
            boost_clock_mhz=2700.0,
            tdp_w=200.0,
            length_mm=280.0,
            memory_bus_width_bits=384,
        ),
        _gpu(
            "GPU B",
            memory_gb=16.0,
            vram_bandwidth_gbps=640.0,
            core_clock_mhz=1300.0,
            boost_clock_mhz=2600.0,
            tdp_w=300.0,
            length_mm=320.0,
            memory_bus_width_bits=256,
        ),
    )

    assert result.hardware_a == "GPU A"
    assert result.hardware_b == "GPU B"
    # All higher-is-better metrics -> a; lower-is-better (tdp_w, length_mm) -> a.
    assert [metric.winner for metric in result.metrics] == [
        "a", "a", "a", "a", "a", "a", "a",
    ]


def test_gpu_lower_is_better_metrics_are_reported_correctly():
    # Side B is lower on TDP and length (lower is better) and wins those.
    result = compare_gpus(
        _gpu(
            "GPU A",
            tdp_w=300.0,
            length_mm=320.0,
        ),
        _gpu(
            "GPU B",
            tdp_w=200.0,
            length_mm=280.0,
        ),
    )

    winners = {metric.name: metric.winner for metric in result.metrics}

    assert winners["tdp_w"] == "b"
    assert winners["length_mm"] == "b"


def test_gpu_exact_ties_are_ties():
    result = compare_gpus(
        _gpu(
            "GPU A",
            memory_gb=16.0,
            core_clock_mhz=1400.0,
        ),
        _gpu(
            "GPU B",
            memory_gb=16.0,
            core_clock_mhz=1400.0,
        ),
    )

    assert _metric_gpu(result, "memory_gb").winner == "tie"
    assert _metric_gpu(result, "memory_gb").difference == 0.0


def test_gpu_missing_value_is_unavailable_not_a_loss():
    result = compare_gpus(
        _gpu("GPU A", memory_gb=24.0, core_clock_mhz=None),
        _gpu("GPU B", memory_gb=16.0, core_clock_mhz=1400.0),
    )

    assert _metric_gpu(result, "memory_gb").winner == "a"
    # core_clock_mhz is missing on A -> unavailable, never a b-win/tie.
    assert _metric_gpu(result, "core_clock_mhz").winner == "unavailable"
    assert _metric_gpu(result, "core_clock_mhz").difference is None


def test_gpu_all_supported_metrics_reported():
    result = compare_gpus(
        _gpu("GPU A", memory_gb=24.0),
        _gpu("GPU B", memory_gb=16.0),
    )

    assert [metric.name for metric in result.metrics] == [
        "memory_gb",
        "vram_bandwidth_gbps",
        "core_clock_mhz",
        "boost_clock_mhz",
        "tdp_w",
        "length_mm",
        "memory_bus_width_bits",
    ]


def test_gpu_requires_specifications_on_both_sides():
    with pytest.raises(ValueError, match="GPU specifications"):
        compare_gpus(
            Hardware(name="GPU A", manufacturer="Vendor", type="GPU"),
            _gpu("GPU B", memory_gb=16.0),
        )

    with pytest.raises(ValueError, match="GPU specifications"):
        compare_gpus(
            _gpu("GPU A", memory_gb=16.0),
            Hardware(name="GPU B", manufacturer="Vendor", type="GPU"),
        )


def _metric_gpu(result, name):
    return next(metric for metric in result.metrics if metric.name == name)
