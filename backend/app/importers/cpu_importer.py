from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import (
    CPUSpecification,
    ExternalIdentifier,
    Hardware,
    Source,
)


def import_cpu(
    data: dict[str, object | None],
    source_id: int,
) -> bool:
    with SessionLocal() as session:
        external_id = data.get("external_id")

        if not external_id:
            return False

        existing_identifier = session.scalar(
            select(ExternalIdentifier).where(
                ExternalIdentifier.source_id == source_id,
                ExternalIdentifier.external_id == str(external_id),
            )
        )

        if existing_identifier:
            return False

        hardware = Hardware(
            name=str(data["name"]),
            manufacturer=str(data["manufacturer"]),
            type="CPU",
        )

        hardware.cpu_specification = CPUSpecification(
            cores=data.get("cores"),
            threads=data.get("threads"),
            base_clock_ghz=data.get("base_clock_ghz"),
            boost_clock_ghz=data.get("boost_clock_ghz"),
            tdp_w=data.get("tdp_w"),
            process_node_nm=data.get("process_node_nm"),
            socket=data.get("socket"),
        )

        identifier = ExternalIdentifier(
            hardware=hardware,
            source_id=source_id,
            external_id=str(external_id),
        )

        session.add(hardware)
        session.add(identifier)
        session.commit()

        return True