from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.database import SessionLocal
from backend.app.models import BenchmarkResult, Hardware, Source

def get_benchmarks_for_hardware(
    hardware_id: int,
    *,
    source_id: int | None = None,
    benchmark_name: str | None = None,
    test_type: str | None = None,
) -> list[BenchmarkResult]:
    """Return benchmark results for a hardware row.

    All filters are optional and combine with AND semantics. When no filter is
    supplied the call is byte-for-byte equivalent to the original behaviour
    (every result for the hardware, ordered by id). Filters are applied as
    parameterised ORM ``WHERE`` clauses; no raw SQL is used and the
    ``source`` relationship is loaded with ``selectinload`` (never a join that
    could duplicate result rows). Since Phase 1.2, ``field_provenance`` is also
    eager-loaded so the route can compute the quality score without lazy-load
    errors after the session closes.
    """

    with SessionLocal() as session:
        hardware = session.scalar(
            select(Hardware).where(Hardware.id == hardware_id)
        )

        if hardware is None:
            raise ValueError(
                f"Hardware not found: {hardware_id}"
            )

        statement = (
            select(BenchmarkResult)
            .options(selectinload(BenchmarkResult.source))
            .options(selectinload(BenchmarkResult.field_provenance))
            .where(
                BenchmarkResult.hardware_id == hardware.id
            )
        )

        if source_id is not None:
            statement = statement.where(
                BenchmarkResult.source_id == source_id
            )

        if benchmark_name is not None:
            statement = statement.where(
                BenchmarkResult.benchmark_name == benchmark_name
            )

        if test_type is not None:
            statement = statement.where(
                BenchmarkResult.test_type == test_type
            )

        return session.scalars(
            statement.order_by(BenchmarkResult.id)
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
