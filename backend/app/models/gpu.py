from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class GPUSpecification(Base):
    __tablename__ = "gpu_specifications"

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

    memory_gb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    memory_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    core_clock_mhz: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    boost_clock_mhz: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    vram_bandwidth_gbps: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    tdp_w: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    interface: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    length_mm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="gpu_specification",
    )