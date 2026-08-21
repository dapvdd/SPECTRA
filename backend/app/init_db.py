from backend.app.database import Base, engine
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    Hardware,
    Source,
)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("SPECTRA database initialized.")