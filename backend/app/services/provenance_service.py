"""Field-level provenance storage for hardware specification enrichment.

This service stores which research evidence and source document supports a
specific hardware specification value, without modifying the specification
value itself. It is the persistence side of the Batch 008 provenance audit.

The service is deliberately narrow:

- ``VALID_FIELDS`` is the single source of truth for which (table, column)
  pairs may carry provenance; anything else is rejected.
- Inserts are idempotent: re-running the same evidence produces no
  duplicates (the model unique constraint is the last line of defence).
- No specification value, benchmark, external identifier or build row is
  ever written.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    FieldProvenance,
    Hardware,
    Source,
)

VALID_FIELDS = {
    "hardware": {
        "release_date",
        "architecture",
    },
    "cpu_specifications": {
        "cores",
        "threads",
        "base_clock_ghz",
        "boost_clock_ghz",
        "tdp_w",
        "process_node_nm",
        "socket",
    },
    "gpu_specifications": {
        "memory_gb",
        "memory_type",
        "core_clock_mhz",
        "boost_clock_mhz",
        "vram_bandwidth_gbps",
        "memory_bus_width_bits",
        "tdp_w",
        "interface",
        "length_mm",
    },
}

VALID_STATUSES = ("verified", "uncertain", "excluded", "unmatched")


class ProvenanceValidationError(ValueError):
    """Raised when an evidence record cannot be stored as provenance."""


def source_by_name(session: Session, name: str) -> Source | None:
    return session.scalar(select(Source).where(Source.name == name))


def get_or_create_source(
    session: Session,
    name: str,
    url: str,
) -> Source:
    existing = source_by_name(session, name)
    if existing is not None:
        return existing
    created = Source(name=name, url=url or "")
    session.add(created)
    session.flush()
    return created


def validate_field_reference(table_name: str, field_name: str) -> None:
    if table_name not in VALID_FIELDS:
        raise ProvenanceValidationError(
            f"unknown provenance table: {table_name!r}"
        )
    if field_name not in VALID_FIELDS[table_name]:
        raise ProvenanceValidationError(
            f"unknown provenance field: {table_name}.{field_name}"
        )


def insert_provenance_record(
    session: Session,
    *,
    hardware_id: int,
    table_name: str,
    field_name: str,
    source_id: int,
    source_url: str,
    evidence_status: str,
    batch_no: int,
    evidenced_value: str = "",
    license_name: str | None = None,
    license_notes: str | None = None,
    attribution: str | None = None,
    access_date=None,
    confidence: str | None = None,
    source_reference: str | None = None,
    match_method: str | None = None,
    notes: str | None = None,
) -> tuple[FieldProvenance, bool]:
    """Insert one provenance record and return ``(record, inserted)``.

    ``inserted`` is False when an identical record already exists, making
    replay safe and idempotent.
    """
    if session.get(Hardware, hardware_id) is None:
        raise ProvenanceValidationError(
            f"unknown hardware_id: {hardware_id}"
        )
    validate_field_reference(table_name, field_name)
    if evidence_status not in VALID_STATUSES:
        raise ProvenanceValidationError(
            f"invalid evidence_status: {evidence_status!r}"
        )

    existing = session.scalar(
        select(FieldProvenance).where(
            FieldProvenance.hardware_id == hardware_id,
            FieldProvenance.table_name == table_name,
            FieldProvenance.field_name == field_name,
            FieldProvenance.source_id == source_id,
            FieldProvenance.evidenced_value == (evidenced_value or ""),
            FieldProvenance.evidence_status == evidence_status,
        )
    )
    if existing is not None:
        return existing, False

    record = FieldProvenance(
        hardware_id=hardware_id,
        table_name=table_name,
        field_name=field_name,
        source_id=source_id,
        source_url=source_url,
        evidenced_value=evidenced_value or "",
        license_name=license_name,
        license_notes=license_notes,
        attribution=attribution,
        access_date=access_date,
        confidence=confidence,
        evidence_status=evidence_status,
        source_reference=source_reference,
        match_method=match_method,
        batch_no=batch_no,
        notes=notes,
    )
    session.add(record)
    session.flush()
    return record, True