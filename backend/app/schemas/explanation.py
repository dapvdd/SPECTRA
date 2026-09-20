from typing import Literal

from pydantic import BaseModel, Field, field_validator


Winner = Literal["cpu_a", "cpu_b", "tie"]
MetricSource = Literal["benchmark", "specification"]
MetricDirection = Literal["higher", "lower"]


class CpuIdentity(BaseModel):
    name: str = Field(min_length=1)
    manufacturer: str = Field(min_length=1)

    @field_validator("name", "manufacturer")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ComparisonMetricFact(BaseModel):
    metric_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value_a: float = Field(gt=0)
    value_b: float = Field(gt=0)
    unit: str = ""
    source: MetricSource
    direction: MetricDirection
    winner: Winner
    difference_percent: float = Field(ge=0)


class TieMetricFact(BaseModel):
    metric_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value_a: float = Field(gt=0)
    value_b: float = Field(gt=0)
    unit: str = ""
    source: MetricSource
    direction: MetricDirection
    winner: Literal["tie"]
    difference_percent: Literal[0] = 0


class UnavailableMetricFact(BaseModel):
    metric_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: MetricSource
    reason: Literal["unavailable", "pending"]


class ComparisonFacts(BaseModel):
    cpu_a: CpuIdentity
    cpu_b: CpuIdentity
    metrics: list[ComparisonMetricFact] = Field(default_factory=list)
    ties: list[TieMetricFact] = Field(default_factory=list)
    unavailable_metrics: list[UnavailableMetricFact] = Field(default_factory=list)


class ExplanationRequest(BaseModel):
    comparison: ComparisonFacts


class ExplanationResponse(BaseModel):
    explanation: str = Field(min_length=1)
