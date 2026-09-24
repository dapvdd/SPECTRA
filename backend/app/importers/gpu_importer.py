from datetime import date

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import (
    ExternalIdentifier,
    GPUSpecification,
    Hardware,
    Source,
)

GPU_SOURCE_NAME = "TechPowerUp GPU Database (gpu_1986-2026.csv)"
GPU_SOURCE_URL = "https://www.techpowerup.com/gpu-specs/"

_GPU_SPEC_FIELDS = (
    "memory_gb",
    "memory_type",
    "core_clock_mhz",
    "boost_clock_mhz",
    "vram_bandwidth_gbps",
    "tdp_w",
    "interface",
    "length_mm",
)


def _parse_release_date(value: object | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def gpu_identity_key(data: dict[str, object | None]) -> tuple[object, ...]:
    return (
        str(data.get("manufacturer") or ""),
        str(data.get("name") or ""),
        "GPU",
    )


def build_gpu_hardware(
    data: dict[str, object | None],
) -> Hardware:
    hardware = Hardware(
        name=str(data["name"]),
        manufacturer=str(data["manufacturer"]),
        type="GPU",
        release_date=_parse_release_date(data.get("release_date")),
        architecture=data.get("architecture") or None,
    )

    hardware.gpu_specification = GPUSpecification(
        **{
            field: data.get(field)
            for field in _GPU_SPEC_FIELDS
        }
    )

    return hardware


def get_existing_gpu_keys(
    session,
) -> set[tuple[object, ...]]:
    hardware = session.scalars(
        select(Hardware).where(Hardware.type == "GPU")
    ).all()

    return {
        gpu_identity_key({
            "manufacturer": item.manufacturer,
            "name": item.name,
        })
        for item in hardware
    }


def _get_or_create_source(session) -> Source:
    source = session.scalar(
        select(Source).where(Source.name == GPU_SOURCE_NAME)
    )

    if source is None:
        source = Source(
            name=GPU_SOURCE_NAME,
            url=GPU_SOURCE_URL,
        )
        session.add(source)
        session.flush()

    return source


def get_or_create_gpu_source(session=None) -> Source:
    if session is not None:
        return _get_or_create_source(session)

    with SessionLocal() as owned:
        source = _get_or_create_source(owned)
        owned.commit()
        return source


def attach_external_identifiers(
    session,
    hardware: Hardware,
    identifiers: object,
    source_id: int,
) -> bool:
    if not isinstance(identifiers, list):
        return False

    added = False

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
                ExternalIdentifier.identifier_type
                == str(identifier_type),
                ExternalIdentifier.external_id
                == str(external_id),
            )
        )

        if existing_identifier:
            continue

        session.add(
            ExternalIdentifier(
                hardware=hardware,
                source_id=source_id,
                external_id=str(external_id),
                identifier_type=str(identifier_type),
            )
        )

        added = True

    return added


def _import_gpu_in_session(
    session,
    data: dict[str, object | None],
    source_id: int | None,
) -> bool:
    name = str(data.get("name") or "")
    manufacturer = str(data.get("manufacturer") or "")

    if not name or not manufacturer:
        raise ValueError("GPU record requires a name and manufacturer.")

    existing_hardware = session.scalar(
        select(Hardware).where(
            Hardware.name == name,
            Hardware.manufacturer == manufacturer,
            Hardware.type == "GPU",
        )
    )

    if existing_hardware:
        return False

    hardware = build_gpu_hardware(data)
    identifiers = data.get("external_identifiers", [])

    if identifiers:
        if source_id is None:
            raise ValueError(
                "source_id is required when external identifiers are present."
            )
        attach_external_identifiers(
            session,
            hardware,
            identifiers,
            source_id,
        )

    session.add(hardware)

    return True


def import_gpu(
    data: dict[str, object | None],
    source_id: int | None = None,
    session=None,
) -> bool:
    if session is not None:
        return _import_gpu_in_session(session, data, source_id)

    with SessionLocal() as owned:
        inserted = _import_gpu_in_session(owned, data, source_id)
        owned.commit()
        return inserted