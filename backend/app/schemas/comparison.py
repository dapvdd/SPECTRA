from dataclasses import dataclass
from typing import Literal


Winner = Literal["a", "b", "tie"]


@dataclass
class MetricComparison:
    name: str
    value_a: float
    value_b: float
    unit: str
    winner: Winner
    difference: float


@dataclass
class ComparisonResult:
    hardware_a: str
    hardware_b: str
    metrics: list[MetricComparison]