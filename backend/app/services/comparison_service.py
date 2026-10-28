from backend.app.models import Hardware
from backend.app.schemas.comparison import (
    ComparisonResult,
    MetricComparison,
)


def _compare_metric(
    name: str,
    value_a: float | None,
    value_b: float | None,
    unit: str,
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

    if value_a > value_b:
        winner = "a"
    elif value_b > value_a:
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
