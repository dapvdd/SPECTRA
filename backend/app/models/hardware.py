from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.cpu import CPUSpecification
    from backend.app.models.benchmark import BenchmarkResult


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

    cpu_specification: Mapped["CPUSpecification | None"] = relationship(
        back_populates="hardware",
        uselist=False,
    )

    benchmark_results: Mapped[list["BenchmarkResult"]] = relationship(
    back_populates="hardware",
)