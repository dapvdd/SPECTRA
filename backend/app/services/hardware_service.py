from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.database import SessionLocal
from backend.app.models import Hardware


def get_all_hardware() -> list[Hardware]:
    with SessionLocal() as session:
        return session.scalars(
            select(Hardware).options(
                selectinload(Hardware.cpu_specification)
            )
        ).all()


def get_hardware_by_name(name: str) -> Hardware | None:
    with SessionLocal() as session:
        return session.scalar(
            select(Hardware)
            .options(
                selectinload(Hardware.cpu_specification)
            )
            .where(
                Hardware.name == name
            )
        )