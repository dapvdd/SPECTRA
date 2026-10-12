"""Read-only response schemas for the Batch 015 source-transparency API.

These models describe what is actually recorded: a source's declared
publisher/licence metadata, and the field- or benchmark-level provenance
records that point at a source. Fields are optional because missing evidence is
reported honestly rather than filled with a placeholder.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    publisher: str | None = None
    description: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    license_status: str | None = None
    terms_notes: str | None = None
    attribution: str | None = None
    retrieved_on: date | None = None


class SourceUsageResponse(BaseModel):
    provenance_records: int = 0
    hardware_records: int = 0
    benchmark_records: int = 0


class SourceSummaryResponse(SourceResponse):
    usage: SourceUsageResponse


class ProvenanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str | None = None
    publisher: str | None = None
    source_url: str
    table_name: str
    field_name: str
    evidenced_value: str
    evidence_status: str
    confidence: str | None = None
    access_date: date | None = None
    source_reference: str | None = None
    match_method: str | None = None
    batch_no: int
    recorded_at: datetime | None = None
    license_name: str | None = None
    license_status: str | None = None
    license_notes: str | None = None
    attribution: str | None = None


class FieldProvenanceResponse(BaseModel):
    table_name: str
    field_name: str
    has_value: bool
    status: str
    records: list[ProvenanceRecordResponse]


class BenchmarkProvenanceGroupResponse(BaseModel):
    benchmark_result_id: int
    benchmark_name: str
    unit: str
    test_type: str
    score: float
    records: list[ProvenanceRecordResponse]


class ProvenanceSummaryResponse(BaseModel):
    total_fields: int
    verified_fields: int
    uncertain_fields: int
    excluded_fields: int
    unmatched_fields: int
    unattributed_fields: int
    unavailable_fields: int


class HardwareProvenanceResponse(BaseModel):
    hardware_id: int
    hardware_name: str
    hardware_type: str
    fields: list[FieldProvenanceResponse]
    benchmarks: list[BenchmarkProvenanceGroupResponse]
    summary: ProvenanceSummaryResponse


class BenchmarkProvenanceResponse(BaseModel):
    benchmark_result_id: int
    hardware_id: int
    benchmark_name: str
    unit: str
    test_type: str
    score: float
    source: SourceResponse | None = None
    records: list[ProvenanceRecordResponse]
