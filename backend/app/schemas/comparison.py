from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class GPUComparisonRequest(BaseModel):
    """Request payload for ``POST /comparison/gpu``.

    Identifies the two GPU hardware records to compare. Both ids are required
    and validated by FastAPI before reaching the service.
    """
    hardware_id_a: int
    hardware_id_b: int


class MetricComparisonResponse(BaseModel):
    """Wire model for one compared metric (serialized by the API)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value_a: float | None = None
    value_b: float | None = None
    unit: str = ""
    winner: Winner
    difference: float | None = None


class ComparisonResultResponse(BaseModel):
    """Wire model for ``POST /comparison/gpu`` and ``POST /comparison/cpu``."""

    model_config = ConfigDict(from_attributes=True)

    hardware_a: str
    hardware_b: str
    metrics: list[MetricComparisonResponse]
