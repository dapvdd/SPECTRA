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


class HardwareDetail(HardwareIdentity):
    """Detail payload whose ``specifications`` shape varies by type.

    The CPU and GPU specification shapes are intentionally not modelled here
    with a union: both are all-nullable so a union would be ambiguous. We keep
    the free-form dict as the contract and validate the scalar constraint in the
    API tests, matching the recorded payload exactly.

    ``specifications`` is ``None`` when no spec row exists (honest unknown).
    """
    specifications: dict[str, Any] | None = None
