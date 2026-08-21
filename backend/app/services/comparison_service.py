from backend.app.models import Hardware
from backend.app.schemas.comparison import (
    ComparisonResult,
    MetricComparison,
)


def _compare_metric(
    name: str,
    value_a: float,
    value_b: float,
    unit: str,
) -> MetricComparison:
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
    ]

    return ComparisonResult(
        hardware_a=hardware_a.name,
        hardware_b=hardware_b.name,
        metrics=metrics,
    )