from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BenchmarkSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str


class BenchmarkResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hardware_id: int
    benchmark_name: str
    score: float
    unit: str
    test_type: str
    source: BenchmarkSourceResponse | None = None
    recorded_at: datetime | None = None
