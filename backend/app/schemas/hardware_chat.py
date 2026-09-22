from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


ScalarValue: TypeAlias = str | int | float | bool | None


class BenchmarkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None, gt=0)
    hardware_id: int | None = Field(default=None, gt=0)
    benchmark_name: str = Field(min_length=1)
    test_type: str = Field(min_length=1)
    score: float = Field(gt=0)
    unit: str = Field(min_length=1)
    source: str | dict[str, ScalarValue] | None = None
    recorded_at: str | None = None

    @field_validator("benchmark_name", "test_type", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class HardwareContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    type: str | None = None
    specifications: dict[str, ScalarValue] = Field(default_factory=dict)
    benchmarks: list[BenchmarkContext] = Field(default_factory=list)

    @field_validator("name", "manufacturer", "type")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class HardwareChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardware: HardwareContext
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class HardwareChatResponse(BaseModel):
    answer: str = Field(min_length=1)
