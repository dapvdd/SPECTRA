from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class StorageSpecification(Base):
    __tablename__ = "storage_specifications"
    __table_args__ = (
        CheckConstraint(
            "storage_type IN ('NVMe', 'SATA SSD', 'HDD')",
            name="ck_storage_specifications_storage_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    hardware_id: Mapped[int] = mapped_column(
        ForeignKey("hardware.id"),
        nullable=True,
        unique=True,
    )

    storage_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    capacity_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    interface: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    read_mb_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    write_mb_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    dram_cache: Mapped[bool | None] = mapped_column(
        Integer,
        nullable=True,
    )

    form_factor: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="storage_specification",
    )
