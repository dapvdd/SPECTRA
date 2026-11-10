from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware


class PSUSpecification(Base):
    __tablename__ = "psu_specifications"
    __table_args__ = (
        CheckConstraint(
            "efficiency_rating IN ('80 Plus White', '80 Plus Bronze', "
            "'80 Plus Gold', '80 Plus Platinum', '80 Plus Titanium')",
            name="ck_psu_specifications_efficiency_rating",
        ),
        CheckConstraint(
            "wattage IS NULL OR wattage > 0",
            name="ck_psu_specifications_wattage_positive",
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

    wattage: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    efficiency_rating: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    modular: Mapped[bool | None] = mapped_column(
        Integer,
        nullable=True,
    )

    pcie_8pin_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    pcie_12vhpwr: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="psu_specification",
    )
