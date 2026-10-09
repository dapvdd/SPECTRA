from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware
    from backend.app.models.source import Source

# Evidence statuses used across the enrichment batches 001-006.
VERIFIED = "verified"
UNCERTAIN = "uncertain"
EXCLUDED = "excluded"
UNMATCHED = "unmatched"
VALID_STATUSES = (VERIFIED, UNCERTAIN, EXCLUDED, UNMATCHED)

# The only tables that hardware enrichment may record provenance against.
VALID_TABLES = ("hardware", "cpu_specifications", "gpu_specifications")


class FieldProvenance(Base):
    """Field-level provenance linking a hardware entity + specification
    column to the research evidence and source document that supports it.

    Designed to be additive: it records which source, URL, licence and
    confidence backed a value, without ever modifying the specification
    value itself. Multiple rows may support the same field (multiple
    sources). Status distinguishes verified, uncertain, excluded and
    unmatched evidence.
    """

    __tablename__ = "field_provenance"

    __table_args__ = (
        CheckConstraint(
            "evidence_status IN ('verified', 'uncertain', 'excluded', 'unmatched')",
            name="ck_field_provenance_evidence_status",
        ),
        CheckConstraint(
            "table_name IN ('hardware', 'cpu_specifications', 'gpu_specifications')",
            name="ck_field_provenance_table_name",
        ),
        UniqueConstraint(
            "hardware_id",
            "table_name",
            "field_name",
            "source_id",
            "evidenced_value",
            "evidence_status",
            name="uq_field_provenance_identity",
        ),
        Index(
            "ix_field_provenance_lookup",
            "hardware_id",
            "table_name",
            "field_name",
        ),
        Index(
            "ix_field_provenance_source_id",
            "source_id",
        ),
        Index(
            "ix_field_provenance_evidence_status",
            "evidence_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    hardware_id: Mapped[int] = mapped_column(
        ForeignKey("hardware.id"),
        nullable=False,
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id"),
        nullable=False,
    )

    table_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    evidenced_value: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
    )

    source_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    license_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    license_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attribution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    access_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    confidence: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    evidence_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    match_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    batch_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="field_provenance",
    )

    source: Mapped["Source"] = relationship()