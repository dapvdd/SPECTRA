from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class MotherboardSpecification(Base):
    __tablename__ = "motherboard_specifications"

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

    socket: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    chipset: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    form_factor: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    ram_type: Mapped[str | None] = mapped_column(
        # 'DDR4' / 'DDR5' — matched against RAMSpecification.ddr_generation
        # by the compatibility engine (M2).
        String(10),
        nullable=True,
    )

    ram_slots: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    max_ram_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    m2_slots: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sata_ports: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    pcie_slots: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="motherboard_specification",
    )
