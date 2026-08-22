from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Source


def seed_sources() -> None:
    with SessionLocal() as session:
        existing_sources = session.scalars(
            select(Source)
        ).all()

        if existing_sources:
            print("Seed skipped: source data already exists.")
            return

        source = Source(
            name="Felix Steinke CPU Spec Dataset",
            url="https://github.com/felixsteinke/cpu-spec-dataset",
        )

        session.add(source)
        session.commit()

        print("Source seed data inserted successfully.")


if __name__ == "__main__":
    seed_sources()