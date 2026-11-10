from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Source

# The owner-manual provenance source for Build Planner entries (M1 Task 2):
# values the owner types in by hand are their own evidence, license-clear by
# definition. Registered idempotently on first import.
OWNER_MANUAL_SOURCE = {
    "name": "owner-manual",
    "url": "local://owner-manual",
    "license_status": "clear",
    "license_name": "Owner-entered data",
    "terms_notes": (
        "Specs and prices entered manually by the SPECTRA owner; "
        "treated as first-party evidence with license_status 'clear'."
    ),
}


def ensure_owner_manual_source(session_factory=None) -> None:
    """Register the owner-manual source exactly once (idempotent)."""
    if session_factory is None:
        session_factory = SessionLocal

    with session_factory() as session:
        existing = session.scalar(
            select(Source).where(Source.name == OWNER_MANUAL_SOURCE["name"])
        )
        if existing is not None:
            session.rollback()
            return

        session.add(
            Source(
                name=OWNER_MANUAL_SOURCE["name"],
                url=OWNER_MANUAL_SOURCE["url"],
                license_status=OWNER_MANUAL_SOURCE["license_status"],
                license_name=OWNER_MANUAL_SOURCE["license_name"],
                terms_notes=OWNER_MANUAL_SOURCE["terms_notes"],
            )
        )
        session.commit()


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