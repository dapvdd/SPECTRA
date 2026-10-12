from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base

# License/terms status vocabulary for a data source. Kept as a plain string
# column (validated in application code and tests) rather than a SQL CHECK so
# the Batch 015 upgrade can be applied to existing databases with a single
# additive ``ALTER TABLE ... ADD COLUMN`` and no table rebuild.
LICENSE_STATUSES = ("clear", "unknown", "restricted", "unresolved")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Batch 015 transparency metadata. Every column is nullable so the columns
    # are additive and existing rows/relationships are preserved untouched;
    # an absent value is reported honestly as unknown rather than fabricated.
    publisher: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    license_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    license_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    license_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    terms_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attribution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    retrieved_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
