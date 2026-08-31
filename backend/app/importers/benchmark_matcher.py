from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware


def load_cpu_lookup() -> dict[tuple[str, str], Hardware]:
    with SessionLocal() as session:
        cpus = session.scalars(
            select(Hardware).where(
                Hardware.type == "CPU"
            )
        ).all()

        return {
            (
                cpu.manufacturer.lower(),
                cpu.name.lower(),
            ): cpu
            for cpu in cpus
        }


def find_matching_cpu(
    name: str | None,
    manufacturer: str | None,
    lookup: dict[tuple[str, str], Hardware],
) -> Hardware | None:
    if not name or not manufacturer:
        return None

    key = (
        manufacturer.lower(),
        name.lower(),
    )

    return lookup.get(key)