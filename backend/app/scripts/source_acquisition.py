"""Stage 2 — modular source-acquisition framework (verified data acquisition).

Defines a ``SourceAdapter`` contract shared by every acquisition path
(manufacturer specs, benchmark datasets, versioned local research, and
user-supplied verified files), plus the normalized ``AcquiredValue`` record
that carries full per-value provenance. An explicit license gate quarantines
unclear/restricted permission evidence instead of publishing it.

Design notes
------------
- Every acquired value records: source identity, URL / document pointer,
  retrieval timestamp, license status + name, hardware model identity, field
  name, raw value, normalized value, unit, validation status, confidence.
- Adapters are declarative: a subclass declares ``source_name``, ``source_url``,
  ``license_*`` and a ``map_record`` that turns one source row into extracted
  fields. Nothing is written to the database here — this stage only produces
  provenance-carrying acquisitions (the enrichment pipeline consumes them).
- The license gate is the single point of permission policy: only ``clear``
  sources pass; ``restricted`` and ``unknown`` are quarantined.
"""

from __future__ import annotations

import csv
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# License gate
# ---------------------------------------------------------------------------

CLEAR_STATUSES = ("clear",)
QUARANTINE_STATUSES = ("restricted", "unknown", "unresolved")


@dataclasses.dataclass(frozen=True)
class LicenseVerdict:
    """Permission verdict for a candidate source adapter."""

    allow: bool
    action: str
    reason: str


class SourceLicenseGate:
    """Decides whether a source may feed the published catalog.

    Only ``clear``-licensed sources pass. Restricted / unknown / unresolved
    sources are quarantined: their acquisitions may be recorded for review but
    never imported as published evidence.
    """

    def verdict(self, adapter: "SourceAdapter") -> LicenseVerdict:
        status = (getattr(adapter, "license_status", None) or "unknown").lower()
        if status in CLEAR_STATUSES:
            return LicenseVerdict(
                allow=True,
                action="publish",
                reason=f"license status '{status}' is clear",
            )
        if status in QUARANTINE_STATUSES:
            return LicenseVerdict(
                allow=False,
                action="quarantine",
                reason=(
                    f"license status '{status}' is not clear; evidence must "
                    "be quarantined for review, not published"
                ),
            )
        return LicenseVerdict(
            allow=False,
            action="quarantine",
            reason=f"license status '{status}' is unrecognised; quarantine",
        )


# ---------------------------------------------------------------------------
# Acquired value record
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class AcquiredValue:
    """One normalised, provenance-carrying value extracted from a source."""

    source_id: str
    source_name: str
    source_url: str
    source_reference: str
    license_status: str
    license_name: str
    hardware_name: str
    hardware_id: int | None = None
    hardware_kind: str = "GPU"
    segment_hint: str | None = None
    field: str = ""
    raw_value: object = None
    normalized_value: object = None
    unit: str = ""
    validation_status: str = "proposed"
    confidence: str = "high"
    retrieval_timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_publication_date: str | None = None

    @property
    def retrieved_at(self) -> str:
        """Alias kept for the acquisition contract (retrieval timestamp)."""
        return self.retrieval_timestamp

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_reference": self.source_reference,
            "license_status": self.license_status,
            "license_name": self.license_name,
            "hardware_name": self.hardware_name,
            "hardware_id": self.hardware_id,
            "field": self.field,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "validation_status": self.validation_status,
            "confidence": self.confidence,
            "retrieval_timestamp": self.retrieval_timestamp,
            "source_publication_date": self.source_publication_date,
        }


# ---------------------------------------------------------------------------
# Adapter base + CSV adapter
# ---------------------------------------------------------------------------


class SourceAdapter:
    """Contract every acquisition source must implement."""

    source_type: str = "generic"
    source_name: str = "unnamed"
    source_url: str = ""
    source_reference: str = ""
    license_status: str = "unknown"
    license_name: str | None = None
    source_publication_date: str | None = None

    def map_record(self, row: dict[str, str]) -> dict:
        """Map one source row to extracted field values (``hardware_name``, etc.)."""
        raise NotImplementedError

    def description(self) -> str:
        return f"{self.source_name} ({self.license_status})"


class CsvSourceAdapter(SourceAdapter):
    """Adapter over a CSV/table source with a declared header contract."""

    required_columns: tuple[str, ...] = ()
    encoding: str = "utf-8-sig"

    def __init__(self, rows: list[dict[str, str]] | None = None):
        self._rows = rows or []

    @classmethod
    def from_csv(cls, path: str | Path) -> "CsvSourceAdapter":
        with Path(path).open(encoding=cls.encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        missing = [c for c in cls.required_columns if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"{cls.source_name} CSV missing required columns: {missing}"
            )
        return cls(rows)

    def rows_for(self) -> list[dict[str, str]]:
        return list(self._rows)

    def normalize_field_value(self, field: str, value: object) -> tuple[object, str]:
        """Return (normalized_value, unit) for an extracted value."""
        return value, ""


def build_acquired_value(
    adapter: SourceAdapter,
    hardware_name: str,
    field: str,
    raw_value: object,
    normalized_value: object,
    unit: str = "",
    source_pointer: str = "",
    confidence: str = "high",
    hardware_id: int | None = None,
    hardware_kind: str = "GPU",
) -> AcquiredValue:
    """Construct an ``AcquiredValue`` with the adapter's provenance filled in."""
    return AcquiredValue(
        source_id=adapter.source_name,
        source_name=adapter.source_name,
        source_url=adapter.source_url,
        source_reference=source_pointer or adapter.source_reference,
        license_status=adapter.license_status,
        license_name=adapter.license_name or "",
        hardware_name=hardware_name,
        hardware_id=hardware_id,
        hardware_kind=hardware_kind,
        field=field,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=unit,
        validation_status="proposed",
        confidence=confidence,
        source_publication_date=adapter.source_publication_date,
    )


def acquire(adapter: SourceAdapter, field: str) -> list[AcquiredValue]:
    """Run one adapter and emit provenance-carrying acquisitions for ``field``.

    Each source row produces one ``AcquiredValue`` for ``field`` using the
    adapter's ``map_record`` and ``normalize_field_value``. This is a pure
    transformation: no database writes, no license gate applied here (the
    gate is applied at ingestion/review time so quarantined evidence stays
    auditable).
    """
    values: list[AcquiredValue] = []
    for index, row in enumerate(adapter.rows_for()):
        mapped = adapter.map_record(row)
        hardware_name = str(
            mapped.get("hardware_name") or mapped.get("cpu_name") or ""
        ).strip()
        if not hardware_name:
            continue
        raw_value = mapped.get(field)
        normalized_value, unit = adapter.normalize_field_value(field, raw_value)
        values.append(
            build_acquired_value(
                adapter,
                hardware_name=hardware_name,
                field=field,
                raw_value=raw_value,
                normalized_value=normalized_value,
                unit=unit,
                source_pointer=f"row {index + 1}",
                confidence=str(mapped.get("confidence") or "high"),
                hardware_kind=str(mapped.get("hardware_kind") or "GPU"),
            )
        )
    return values


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, Callable[[], SourceAdapter]] = {}


def register_adapter(key: str, factory: Callable[[], SourceAdapter]) -> None:
    """Register a named adapter factory (module-level registry)."""
    ADAPTER_REGISTRY[key] = factory


# ---------------------------------------------------------------------------
# Concrete adapter: GPU Ark spec sheets (CC BY 4.0 — source 4, clear)
# ---------------------------------------------------------------------------


class GpuArkAdapter(CsvSourceAdapter):
    """Adapter over `data/research/batch017/gpuark-gpu-specs.csv`.

    GPU Ark publishes GPU specification sheets under CC BY 4.0, so this is a
    *clear* source whose acquisitions may feed the published catalog. Only
    well-attested spec columns are mapped; unknown values stay ``None``
    rather than being invented.
    """

    source_type = "vendor_gpu_specs"
    source_name = "GPU Ark"
    source_url = "https://www.gpuark.com"
    source_reference = "gpuark-gpu-specs.csv (batch017)"
    license_status = "clear"
    license_name = "CC BY 4.0"
    required_columns = ("name",)

    # Mapped field name -> (CSV column, unit)
    _COLUMN_MAP = {
        "base_clock_mhz": ("base_clock", "MHz"),
        "boost_clock_mhz": ("boost_clock", "MHz"),
        "memory_size_gb": ("ram", "GB"),
        "memory_type": ("ram_type", ""),
        "memory_bus_bits": ("bus_width", "bit"),
        "tdp_w": ("tdp", "W"),
        "cuda_cores": ("cores", "cores"),
        "sm_count": ("sm_count", "count"),
        "architecture": ("arch_name", ""),
    }

    def map_record(self, row: dict[str, str]) -> dict:
        extracted = {
            "hardware_name": (row.get("name") or "").strip(),
            "hardware_kind": "gpu",
        }
        for mapped, (csv_col, _unit) in self._COLUMN_MAP.items():
            extracted[mapped] = row.get(csv_col)
        return extracted

    def normalize_field_value(self, field: str, value: object) -> tuple[object, str]:
        unit = self._COLUMN_MAP.get(field, (None, ""))[1]
        if value is None or str(value).strip() == "":
            return None, unit
        return value, unit


register_adapter("gpuark", GpuArkAdapter)


# ---------------------------------------------------------------------------
# Restricted / unknown adapters — exist so the license gate can be exercised
# against the real blocked sources. They must NOT be wired into ingestion;
# the gate quarantines them before anything is published.
# ---------------------------------------------------------------------------


class PassMarkAdapter(SourceAdapter):
    """PassMark GPU/cpu benchmark ratings — restricted license (source 1)."""

    source_type = "benchmark"
    source_name = "PassMark Software"
    source_url = "https://www.passmark.com"
    license_status = "restricted"
    license_name = "proprietary / on-site only"

    def rows_for(self):
        return []


class TechPowerUpAdapter(SourceAdapter):
    """TechPowerUp GPU database — restricted license (source 3)."""

    source_type = "vendor_gpu_specs"
    source_name = "TechPowerUp"
    source_url = "https://www.techpowerup.com/gpu-specs/"
    license_status = "restricted"
    license_name = "all rights reserved"

    def rows_for(self):
        return []
