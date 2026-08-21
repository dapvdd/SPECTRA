from datetime import datetime

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import BenchmarkResult, Hardware, Source

def get_benchmarks_for_hardware(
    hardware_name: str,
) -> list[BenchmarkResult]:

    with SessionLocal() as session:
        hardware = session.scalar(
            select(Hardware).where(
                Hardware.name == hardware_name
            )
        )

        if hardware is None:
            raise ValueError(
                f"Hardware not found: {hardware_name}"
            )

        return session.scalars(
            select(BenchmarkResult)
            .where(
                BenchmarkResult.hardware_id == hardware.id
            )
        ).all()

def add_benchmark_result(
    hardware_name: str,
    benchmark_name: str,
    score: float,
    unit: str,
    test_type: str,
    source_name: str,
    source_url: str,
) -> BenchmarkResult:

    with SessionLocal() as session:
        hardware = session.scalar(
            select(Hardware).where(
                Hardware.name == hardware_name
            )
        )

        if hardware is None:
            raise ValueError(
                f"Hardware not found: {hardware_name}"
            )

        source = session.scalar(
            select(Source).where(
                Source.name == source_name
            )
        )

        if source is None:
            source = Source(
                name=source_name,
                url=source_url,
            )
            session.add(source)
            session.flush()

        benchmark = BenchmarkResult(
            hardware_id=hardware.id,
            benchmark_name=benchmark_name,
            score=score,
            unit=unit,
            test_type=test_type,
            source_id=source.id,
            recorded_at=datetime.now(),
        )

        session.add(benchmark)
        session.commit()
        session.refresh(benchmark)

        return benchmark