import csv
from pathlib import Path

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.importers.benchmark_normalizer import (
    normalize_benchmark_cpu_name,
    normalize_benchmark_row,
)
from backend.app.models import Hardware
from backend.app.models.cpu import CPUSpecification


def load_existing_cpu_lookup(
    session,
) -> dict[tuple[str, str], Hardware]:
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


def enrich_cpu_specification(
    specification: CPUSpecification,
    data: dict[str, object | None],
) -> int:
    updated = 0

    fields = [
        "cores",
        "threads",
        "base_clock_ghz",
        "boost_clock_ghz",
        "tdp_w",
        "socket",
    ]

    for field in fields:
        current_value = getattr(
            specification,
            field,
        )

        new_value = data.get(field)

        # Isi hanya field yang masih kosong
        if current_value is None and new_value is not None:
            setattr(
                specification,
                field,
                new_value,
            )

            updated += 1

    return updated


def create_cpu_specification(
    hardware: Hardware,
    data: dict[str, object | None],
) -> CPUSpecification:
    return CPUSpecification(
        hardware=hardware,
        cores=data.get("cores"),
        threads=data.get("threads"),
        base_clock_ghz=data.get(
            "base_clock_ghz"
        ),
        boost_clock_ghz=data.get(
            "boost_clock_ghz"
        ),
        tdp_w=data.get("tdp_w"),
        socket=data.get("socket"),
    )


def import_benchmark_cpus(
    csv_path: str | Path,
) -> dict[str, int]:
    csv_path = Path(csv_path)

    imported = 0
    enriched = 0
    skipped = 0
    invalid = 0

    with csv_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = csv.DictReader(file)

        with SessionLocal() as session:

            lookup = load_existing_cpu_lookup(
                session
            )

            for row in rows:

                data = normalize_benchmark_row(row)

                name = normalize_benchmark_cpu_name(
                    data.get("name")
                )

                manufacturer = data.get(
                    "manufacturer"
                )

                if not name or not manufacturer:
                    invalid += 1
                    continue

                key = (
                    str(manufacturer).lower(),
                    str(name).lower(),
                )

                existing = lookup.get(key)

                # =========================
                # EXISTING CPU
                # =========================

                if existing:

                    specification = (
                        existing.cpu_specification
                    )

                    # Belum punya specification
                    if specification is None:

                        specification = (
                            create_cpu_specification(
                                existing,
                                data,
                            )
                        )

                        session.add(specification)

                        enriched += 1

                        continue

                    changes = enrich_cpu_specification(
                        specification,
                        data,
                    )

                    if changes > 0:
                        enriched += 1
                    else:
                        skipped += 1

                    continue

                # =========================
                # NEW CPU
                # =========================

                hardware = Hardware(
                    name=name,
                    manufacturer=manufacturer,
                    type="CPU",
                )

                session.add(hardware)

                specification = (
                    create_cpu_specification(
                        hardware,
                        data,
                    )
                )

                session.add(specification)

                lookup[key] = hardware

                imported += 1

            session.commit()

    return {
        "imported": imported,
        "enriched": enriched,
        "skipped": skipped,
        "invalid": invalid,
    }