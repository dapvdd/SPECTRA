from backend.app.models import Hardware, GPUSpecification
from backend.app.schemas.comparison import (
    ComparisonResult,
    MetricComparison,
)


def _compare_metric(
    name: str,
    value_a: float | None,
    value_b: float | None,
    unit: str,
    direction: str = "higher",
) -> MetricComparison:
    # A metric with an unknown side is reported as unavailable rather than
    # crashing or fabricating a winner, a tie, or a numeric difference.
    if value_a is None or value_b is None:
        return MetricComparison(
            name=name,
            value_a=value_a,
            value_b=value_b,
            unit=unit,
            winner="unavailable",
            difference=None,
        )

    # ``direction`` encodes whether a higher ("higher") or lower ("lower")
    # numeric value is the better outcome. CPU comparison is entirely
    # higher-is-better; GPU comparison adds lower-is-better for TDP and length
    # so the backend matches the frontend's GPU table semantics exactly.
    if direction == "lower":
        a_better = value_a < value_b
        b_better = value_b < value_a
    else:
        a_better = value_a > value_b
        b_better = value_b > value_a

    if a_better:
        winner = "a"
    elif b_better:
        winner = "b"
    else:
        winner = "tie"

    return MetricComparison(
        name=name,
        value_a=value_a,
        value_b=value_b,
        unit=unit,
        winner=winner,
        difference=round(value_a - value_b, 3),
    )


def compare_cpus(
    hardware_a: Hardware,
    hardware_b: Hardware,
) -> ComparisonResult:
    spec_a = hardware_a.cpu_specification
    spec_b = hardware_b.cpu_specification

    if spec_a is None or spec_b is None:
        raise ValueError("Both hardware must have CPU specifications.")

    metrics = [
        _compare_metric(
            "cores",
            spec_a.cores,
            spec_b.cores,
            "cores",
        ),
        _compare_metric(
            "threads",
            spec_a.threads,
            spec_b.threads,
            "threads",
        ),
        _compare_metric(
            "base_clock",
            spec_a.base_clock_ghz,
            spec_b.base_clock_ghz,
            "GHz",
        ),
        _compare_metric(
            "boost_clock",
            spec_a.boost_clock_ghz,
            spec_b.boost_clock_ghz,
            "GHz",
        ),
        # Derived metric: cores per watt of TDP — higher is more power-efficient
        # per core. Requires both tdp_w and cores on both sides.
        # If either side is missing either value, reports unavailable.
        _compare_metric(
            "power_efficiency",
            _cores_per_watt(spec_a.tdp_w, spec_a.cores),
            _cores_per_watt(spec_b.tdp_w, spec_b.cores),
            "cores/W",
        ),
    ]

    return ComparisonResult(
        hardware_a=hardware_a.name,
        hardware_b=hardware_b.name,
        metrics=metrics,
    )


def _cores_per_watt(tdp_w: float | None, cores: int | None) -> float | None:
    """Derived: cores divided by TDP in watts. None if either input is None."""
    if tdp_w is None or cores is None or tdp_w <= 0:
        return None
    return cores / tdp_w


def compare_gpus(
    hardware_a: Hardware,
    hardware_b: Hardware,
) -> ComparisonResult:
    """Compare two GPU hardware records by their specification metrics.

    Metrics follow the same unavailable/tie/winner semantics as CPU comparison.
    Higher-is-better: memory_gb, vram_bandwidth_gbps, core_clock_mhz,
    boost_clock_mhz, memory_bus_width_bits.
    Lower-is-better: tdp_w, length_mm.
    """
    spec_a = hardware_a.gpu_specification
    spec_b = hardware_b.gpu_specification

    if spec_a is None or spec_b is None:
        raise ValueError("Both hardware must have GPU specifications.")

    metrics = [
        _compare_metric(
            "memory_gb",
            spec_a.memory_gb,
            spec_b.memory_gb,
            "GB",
        ),
        _compare_metric(
            "vram_bandwidth_gbps",
            spec_a.vram_bandwidth_gbps,
            spec_b.vram_bandwidth_gbps,
            "GB/s",
        ),
        _compare_metric(
            "core_clock_mhz",
            spec_a.core_clock_mhz,
            spec_b.core_clock_mhz,
            "MHz",
        ),
        _compare_metric(
            "boost_clock_mhz",
            spec_a.boost_clock_mhz,
            spec_b.boost_clock_mhz,
            "MHz",
        ),
        _compare_metric(
            "tdp_w",
            spec_a.tdp_w,
            spec_b.tdp_w,
            "W",
            direction="lower",
        ),
        _compare_metric(
            "length_mm",
            spec_a.length_mm,
            spec_b.length_mm,
            "mm",
            direction="lower",
        ),
        _compare_metric(
            "memory_bus_width_bits",
            spec_a.memory_bus_width_bits,
            spec_b.memory_bus_width_bits,
            "bits",
        ),
    ]

    return ComparisonResult(
        hardware_a=hardware_a.name,
        hardware_b=hardware_b.name,
        metrics=metrics,
    )
