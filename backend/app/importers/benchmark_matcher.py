import re
from collections.abc import Iterable

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware


def normalize_match_name(name: str | None) -> str | None:
    if not name:
        return None

    name = name.strip()

    # Remove multi-CPU configuration prefix
    # Example: [Dual CPU] AMD EPYC 7252
    name = re.sub(
        r"^\[(?:Dual|Quad|\d+-Way)\s+CPU\]\s*",
        "",
        name,
        flags=re.IGNORECASE,
    )

    # Remove clock suffix
    # Example: Intel Atom D525 @ 1.80GHz
    name = re.sub(
        r"\s*@\s*\d+(?:\.\d+)?\s*GHz$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    # Remove common processor suffixes
    name = re.sub(
        r"\s+X-series Processor$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"\s+Processor$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"\s+CPU$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(r"\s+", " ", name)

    return name.strip().lower()


def build_cpu_lookup(
    cpus: Iterable[Hardware],
) -> dict[tuple[str, str], Hardware | None]:
    lookup: dict[tuple[str, str], Hardware | None] = {}

    for cpu in cpus:
        normalized_name = normalize_match_name(cpu.name)

        if not normalized_name:
            continue

        key = (
            cpu.manufacturer.lower(),
            normalized_name,
        )

        if key in lookup:
            # Do not select one hardware record when the normalized identity
            # is shared by multiple records.
            lookup[key] = None
        else:
            lookup[key] = cpu

    return lookup


def load_cpu_lookup(
    session=None,
) -> dict[tuple[str, str], Hardware | None]:
    if session is not None:
        cpus = session.scalars(
            select(Hardware).where(
                Hardware.type == "CPU"
            )
        ).all()
        return build_cpu_lookup(cpus)

    with SessionLocal() as session:
        return load_cpu_lookup(session)


def find_matching_cpu(
    name: str | None,
    manufacturer: str | None,
    lookup: dict[tuple[str, str], Hardware | None],
) -> Hardware | None:
    normalized_name = normalize_match_name(name)

    if not normalized_name or not manufacturer:
        return None

    key = (
        manufacturer.lower(),
        normalized_name,
    )

    return lookup.get(key)
