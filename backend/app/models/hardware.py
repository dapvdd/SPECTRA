from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.cpu import CPUSpecification
    from backend.app.models.gpu import GPUSpecification
    from backend.app.models.ram import RAMSpecification
    from backend.app.models.storage import StorageSpecification
    from backend.app.models.motherboard import MotherboardSpecification
    from backend.app.models.psu import PSUSpecification
    from backend.app.models.benchmark import BenchmarkResult
    from backend.app.models.external_identifier import ExternalIdentifier
    from backend.app.models.provenance import FieldProvenance


class Hardware(Base):
    __tablename__ = "hardware"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    manufacturer: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    release_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    architecture: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Segment distinguishes product categories so that, e.g., a mobile GPU
    # and a desktop GPU sharing a marketing name are not conflated.
    # Values are intentionally a closed vocabulary so any unexpected string
    # is surfaced rather than silently accepted.
    segment: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # --- M3 migration v4 identity/lifecycle columns (additive, nullable).
    # The ORM mirrors the migration-owned columns (runner.py
    # _HARDWARE_V4_COLUMNS) so create_all-built dev/CI DBs match the
    # migrated schema. Pre-M3 rows keep NULL in all five columns; the
    # unique partial index on canonical_key lives in the DB, not here.
    canonical_key: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    product_family: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # Vocabulary ('confirmed'/'unconfirmed') is validated in application
    # code + tests (SQLite cannot add CHECK via ALTER TABLE).
    identity_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Vocabulary ('APPROVED'/'QUARANTINED'/'PUBLISHED' lifecycle) is
    # validated in application code + tests.
    record_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    superseded_by_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cpu_specification: Mapped["CPUSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    gpu_specification: Mapped["GPUSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    ram_specification: Mapped["RAMSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    storage_specification: Mapped["StorageSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    motherboard_specification: Mapped["MotherboardSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    psu_specification: Mapped["PSUSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    benchmark_results: Mapped[list["BenchmarkResult"]] = relationship(
        back_populates="hardware",
    )

    external_identifiers: Mapped[list["ExternalIdentifier"]] = relationship(
        back_populates="hardware",
    )

    field_provenance: Mapped[list["FieldProvenance"]] = relationship(
        back_populates="hardware",
    )