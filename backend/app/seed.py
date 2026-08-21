from datetime import date

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware, CPUSpecification


def seed_cpu_data() -> None:
    with SessionLocal() as session:
        existing_hardware = session.scalars(
            select(Hardware)
        ).all()

        if existing_hardware:
            print("Seed skipped: hardware data already exists.")
            return

        ryzen_5600 = Hardware(
            name="Ryzen 5 5600",
            manufacturer="AMD",
            type="CPU",
            release_date=date(2022, 4, 4),
            architecture="Zen 3",
        )

        ryzen_5600.cpu_specification = CPUSpecification(
            cores=6,
            threads=12,
            base_clock_ghz=3.5,
            boost_clock_ghz=4.4,
            tdp_w=65,
            process_node_nm=7,
            socket="AM4",
        )

        i5_12400f = Hardware(
            name="Core i5-12400F",
            manufacturer="Intel",
            type="CPU",
            release_date=date(2022, 1, 4),
            architecture="Alder Lake",
        )

        i5_12400f.cpu_specification = CPUSpecification(
            cores=6,
            threads=12,
            base_clock_ghz=2.5,
            boost_clock_ghz=4.4,
            tdp_w=65,
            process_node_nm=10,
            socket="LGA1700",
        )

        session.add_all([
            ryzen_5600,
            i5_12400f,
        ])

        session.commit()

        print("CPU seed data inserted successfully.")


if __name__ == "__main__":
    seed_cpu_data()