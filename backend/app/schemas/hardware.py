from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


class HardwareIdentity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    manufacturer: str | None = None
    type: str | None = None
    segment: str | None = None
    release_date: date | None = None
    architecture: str | None = None


class HardwareCatalogItem(HardwareIdentity):
    pass


class FacetCount(BaseModel):
    """One facet bucket: a distinct value and how many rows carry it."""

    value: str
    count: int


class HardwareFacetsResponse(BaseModel):
    """Accurate facet counts under the active catalog filters.

    ``None`` (unknown) facet values are excluded; only real, non-null values are
    counted. Each list is ordered by count (descending), then value (ascending)
    for a deterministic contract.
    """

    types: list[FacetCount]
    manufacturers: list[FacetCount]
    segments: list[FacetCount]


class HardwareDetail(HardwareIdentity):
    """Detail payload whose ``specifications`` shape varies by type.

    The CPU and GPU specification shapes are intentionally not modelled here
    with a union: both are all-nullable so a union would be ambiguous. We keep
    the free-form dict as the contract and validate the scalar constraint in the
    API tests, matching the recorded payload exactly.

    ``specifications`` is ``None`` when no spec row exists (honest unknown).
    """
    specifications: dict[str, Any] | None = None
