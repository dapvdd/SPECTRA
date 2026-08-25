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
    identifiers = data.get("external_identifiers", [])

    if not isinstance(identifiers, list):
        return False

    with SessionLocal() as session:
        if not identifiers:
            existing_hardware = session.scalar(
                select(Hardware).where(
                    Hardware.name == str(data["name"]),
                    Hardware.manufacturer == str(data["manufacturer"]),
                    Hardware.type == str(data["type"]),
                )
            )

        if existing_hardware:
            return False    
        
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue

            identifier_type = identifier.get("type")
            external_id = identifier.get("value")

            if not identifier_type or not external_id:
                continue

            existing_identifier = session.scalar(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.source_id == source_id,
                    ExternalIdentifier.identifier_type == str(identifier_type),
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

        session.add(hardware)

        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue

            identifier_type = identifier.get("type")
            external_id = identifier.get("value")

            if not identifier_type or not external_id:
                continue

            session.add(
                ExternalIdentifier(
                    hardware=hardware,
                    source_id=source_id,
                    external_id=str(external_id),
                    identifier_type=str(identifier_type),
                )
            )

        session.commit()

        return True