from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class RAMSpecification(Base):
    __tablename__ = "ram_specifications"
    __table_args__ = (
        CheckConstraint(
            "ddr_generation IN ('DDR3', 'DDR4', 'DDR5', 'DDR6')",
            name="ck_ram_specifications_ddr_generation",
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

    ddr_generation: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    capacity_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    speed_mhz: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    modules: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ecc: Mapped[bool | None] = mapped_column(
        # SQLite has no native BOOLEAN; SQLAlchemy stores 0/1.
        Integer,
        nullable=True,
    )

    voltage_v: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    form_factor: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="ram_specification",
    )
