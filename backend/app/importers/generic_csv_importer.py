"""Generic component CSV importer with field provenance (M1 Task 3).

One importer for all four Build Planner categories: reads a CSV via stdlib
``csv.DictReader``, validates each row through ``validate_component_row``,
upserts ``Hardware`` (by name+manufacturer+type) plus the category spec row
(unique per hardware), and writes a ``field_provenance`` row for every
populated spec field (owner-manual entries: evidence_status='verified',
batch_no=0).

Per-row try/except keeps one bad row from killing the batch (importer family
convention, pattern: cpu_importer.py). Ops tool — API endpoints never call
this directly.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.importers.component_validators import (
    CATEGORY_TYPES,
    validate_component_row,
)
from backend.app.models import (
    FieldProvenance,
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    Source,
    StorageSpecification,
)

# Category slug -> (Hardware.type, spec model, spec table name for provenance).
_CATEGORY_MODELS: dict[str, tuple[str, type, str]] = {
    "ram": ("RAM", RAMSpecification, "ram_specifications"),
    "storage": ("STORAGE", StorageSpecification, "storage_specifications"),
    "motherboard": (
        "MOTHERBOARD", MotherboardSpecification, "motherboard_specifications",
    ),
    "psu": ("PSU", PSUSpecification, "psu_specifications"),
}

_SPEC_RELATIONSHIP = {
    "ram": "ram_specification",
    "storage": "storage_specification",
    "motherboard": "motherboard_specification",
    "psu": "psu_specification",
}

# Provenance for owner-entered rows: first-party evidence, not from a
# research batch.
_OWNER_BATCH_NO = 0


@dataclass
class ImportReport:
    imported: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _resolve_source(session, source_name: str) -> Source:
    source = session.scalar(select(Source).where(Source.name == source_name))
    if source is None:
        raise ValueError(
            f"source '{source_name}' not registered; "
            "call ensure_owner_manual_source() first"
        )
    return source


def _upsert_hardware(session, identity: dict[str, Any]) -> tuple[Hardware, bool]:
    """Return (hardware, created) for name+manufacturer+type."""
    existing = session.scalar(
        select(Hardware).where(
            Hardware.name == identity["name"],
            Hardware.manufacturer == identity["manufacturer"],
            Hardware.type == identity["type"],
        )
    )
    if existing is not None:
        return existing, False
    hardware = Hardware(
        name=identity["name"],
        manufacturer=identity["manufacturer"],
        type=identity["type"],
    )
    session.add(hardware)
    session.flush()  # assign id before spec/provenance rows reference it
    return hardware, True


def _spec_fields_populated(spec: Any, model: type) -> list[str]:
    """Populated spec column names (provenance is written only for these)."""
    return [
        column.name
        for column in model.__table__.columns
        if column.name not in ("id", "hardware_id")
        and getattr(spec, column.name, None) is not None
    ]


def import_component_csv(
    session_factory,
    category: str,
    csv_path: Path,
    source_name: str = "owner-manual",
) -> ImportReport:
    """Import a component CSV for one category, writing field provenance.

    Raises FileNotFoundError / ValueError up front for a missing file or an
    unknown category; per-row problems land in the report instead of
    aborting the batch.
    """
    if category not in CATEGORY_TYPES:
        raise ValueError(
            f"unknown category '{category}' (expected one of {sorted(CATEGORY_TYPES)})"
        )
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    _, spec_model, table_name = _CATEGORY_MODELS[category]
    relationship_name = _SPEC_RELATIONSHIP[category]
    report = ImportReport()

    with session_factory() as session:
        source = _resolve_source(session, source_name)

        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        for offset, raw_row in enumerate(rows):
            row_label = f"row {offset + 2}"  # +2: header is line 1
            try:
                # Savepoint per row: a failure rolls back only this row, so
                # good siblings already staged in the open transaction
                # survive (per-row isolation).
                with session.begin_nested():
                    validated = validate_component_row(category, raw_row)

                    hardware, _created = _upsert_hardware(session, validated)

                    if getattr(hardware, relationship_name) is not None:
                        raise ValueError(
                            f"duplicate: spec row for {validated['name']!r} "
                            f"({validated['manufacturer']}, {validated['type']}) "
                            "already exists"
                        )

                    spec_kwargs = {
                        key: value
                        for key, value in validated.items()
                        if key not in ("name", "manufacturer", "type")
                    }
                    spec = spec_model(**spec_kwargs)
                    setattr(hardware, relationship_name, spec)
                    session.flush()

                    for field_name in _spec_fields_populated(spec, spec_model):
                        session.add(
                            FieldProvenance(
                                hardware_id=hardware.id,
                                source_id=source.id,
                                table_name=table_name,
                                field_name=field_name,
                                evidenced_value=str(getattr(spec, field_name)),
                                source_url=source.url,
                                evidence_status="verified",
                                batch_no=_OWNER_BATCH_NO,
                                recorded_at=datetime.now(),
                            )
                        )
                    session.flush()

                report.imported += 1
            except (ValueError, IntegrityError) as exc:
                report.failed += 1
                report.errors.append(f"{row_label}: {exc}")

        session.commit()

    return report
