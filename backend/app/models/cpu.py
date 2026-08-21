from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class CPUSpecification(Base):
    __tablename__ = "cpu_specifications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    hardware_id: Mapped[int] = mapped_column(
        ForeignKey("hardware.id"),
        nullable=False,
        unique=True,
    )

    cores: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    threads: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    base_clock_ghz: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    boost_clock_ghz: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    tdp_w: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    process_node_nm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    socket: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="cpu_specification",
    )