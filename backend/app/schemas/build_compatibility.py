"""Request/response schemas for the build compatibility API (M2 Task 3)."""

from typing import Any

from pydantic import BaseModel, Field


class BuildCompatibilityRequest(BaseModel):
    """IDs of the components currently in the build.

    Every slot is optional: partial builds are valid input, and a partial
    build must never be declared fully compatible.
    """

    cpu: int | None = None
    gpu: int | None = None
    ram: int | None = None
    storage: int | None = None
    motherboard: int | None = None
    psu: int | None = None


class ProvenanceReference(BaseModel):
    """One provenance row backing a spec value used by a rule."""

    table_name: str
    field_name: str
    evidenced_value: str | None = None
    evidence_status: str | None = None
    source_url: str | None = None


class RuleResultOut(BaseModel):
    rule_id: str
    component_hardware_ids: dict[str, int | None]
    state: str
    explanation: str
    spec_fields: list[str]
    missing_information: list[str]
    provenance: list[ProvenanceReference]


class BuildCompatibilityResponse(BaseModel):
    state: str
    explanation: str
    rules_version: str
    rule_results: list[RuleResultOut]
