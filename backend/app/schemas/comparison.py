from dataclasses import dataclass
from typing import Literal


# "unavailable" is used when a metric cannot be compared because at least one
# side has no verified value. An unknown value is never coerced to zero and is
# never reported as a winner or as a tie.
Winner = Literal["a", "b", "tie", "unavailable"]


@dataclass
class MetricComparison:
    """The outcome of comparing one metric between two pieces of hardware.

    ``value_a`` / ``value_b`` are ``None`` for any side that has no verified
    value. When either side is missing the metric is reported as
    ``winner="unavailable"`` with ``difference=None`` so that an unknown value
    can never masquerade as a real specification, a fabricated difference, or a
    false tie. ``difference`` is signed (``value_a - value_b``).
    """

    name: str
    value_a: float | None
    value_b: float | None
    unit: str
    winner: Winner
    difference: float | None


@dataclass
class ComparisonResult:
    hardware_a: str
    hardware_b: str
    metrics: list[MetricComparison]
