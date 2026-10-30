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
    # Phase 1.2 additive quality assessment. NULL when no score could be
    # honestly computed (e.g. provenance veto). Optional so the pre-1.2 wire
    # contract is preserved exactly.
    quality: dict | None = None
