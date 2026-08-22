from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.hardware import Hardware
    from backend.app.models.source import Source


class ExternalIdentifier(Base):
    __tablename__ = "external_identifiers"

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

    external_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    hardware: Mapped["Hardware"] = relationship(
        back_populates="external_identifiers",
    )

    source: Mapped["Source"] = relationship()