"""Import exact-match Geekbench 7 CPU scores without creating hardware."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import SessionLocal
from backend.app.importers.geekbench_match_audit import (
    DEFAULT_DATASET_PATH,
    DEFAULT_DATABASE_PATH,
    _read_rows,
    audit_dataset,
)
from backend.app.models import BenchmarkResult, CPUSpecification, Hardware, Source


GEEKBENCH_SOURCE_NAME = "Geekbench Browser - Geekbench 7 CPU"
GEEKBENCH_SOURCE_URL = "https://browser.geekbench.com/"
BENCHMARK_NAME = "Geekbench 7"
SCORE_UNIT = "points"
SINGLE_CORE_TEST_TYPE = "single-core"
MULTI_CORE_TEST_TYPE = "multi-core"


@dataclass(frozen=True)
class PlannedScore:
    hardware_id: int
    hardware_name: str
    cpu_name: str
    score: float
    test_type: str
    samples: int | None


@dataclass(frozen=True)
class ScoreImportPlan:
    scores: tuple[PlannedScore, ...]
    matched_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    invalid_rows: int
    invalid_score_fields: int
    duplicate_source_rows: int
    duplicate_logical_scores: int
    skipped_existing: int = 0
    errors: tuple[str, ...] = ()

    @property
    def single_core_scores(self) -> tuple[PlannedScore, ...]:
        return tuple(
            score
            for score in self.scores
            if score.test_type == SINGLE_CORE_TEST_TYPE
        )

    @property
    def multi_core_scores(self) -> tuple[PlannedScore, ...]:
        return tuple(
            score
            for score in self.scores
            if score.test_type == MULTI_CORE_TEST_TYPE
        )


@dataclass(frozen=True)
class ScoreImportSummary:
    planned: int
    inserted: int
    skipped: int
    invalid: int
    invalid_score_fields: int
    unmatched: int
    ambiguous: int
    duplicate_source_rows: int
    duplicate_logical_scores: int
    errors: int
    error_messages: tuple[str, ...] = ()


def _parse_score(value: str | None) -> float | None:
    if not value:
        return None
    try:
        score = float(value.strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or score <= 0:
        return None
    return score


def _parse_samples(value: str | None) -> int | None:
    if not value:
        return None
    try:
        samples = int(value.strip())
    except (TypeError, ValueError):
        return None
    return samples if samples > 0 else None


def _logical_key(
    hardware_id: int,
    score: float,
    test_type: str,
    source_id: int | None = None,
) -> tuple[object, ...]:
    return (
        hardware_id,
        BENCHMARK_NAME,
        score,
        SCORE_UNIT,
        test_type,
        source_id,
        None,
    )


def _existing_result_keys(
    session: Session,
    source_id: int,
) -> set[tuple[object, ...]]:
    results = session.scalars(
        select(BenchmarkResult).where(
            BenchmarkResult.source_id == source_id,
            BenchmarkResult.benchmark_name == BENCHMARK_NAME,
            BenchmarkResult.unit == SCORE_UNIT,
            BenchmarkResult.recorded_at.is_(None),
        )
    ).all()
    return {
        _logical_key(
            result.hardware_id,
            result.score,
            result.test_type,
            source_id,
        )
        for result in results
    }


def _source_id(session: Session) -> int | None:
    source = session.scalar(
        select(Source).where(
            Source.name == GEEKBENCH_SOURCE_NAME,
            Source.url == GEEKBENCH_SOURCE_URL,
        )
    )
    return source.id if source is not None else None


def build_score_import_plan(
    csv_path: str | Path,
    session: Session,
) -> ScoreImportPlan:
    """Build a complete exact-match score plan without writing anything."""
    rows = _read_rows(Path(csv_path))
    audit = audit_dataset(csv_path, session)
    source_id = _source_id(session)
    existing_keys = (
        _existing_result_keys(session, source_id)
        if source_id is not None
        else set()
    )
    planned: list[PlannedScore] = []
    seen_keys: set[tuple[object, ...]] = set()
    invalid_rows = 0
    invalid_score_fields = 0
    duplicate_source_rows = 0
    duplicate_logical_scores = 0
    skipped_existing = 0
    errors: list[str] = []

    if len(rows) != len(audit.rows):
        errors.append("dataset audit row count does not match CSV row count")

    for row, match in zip(rows, audit.rows):
        single_score = _parse_score(row.get("devices/score"))
        multi_score = _parse_score(row.get("devices/multicore_score"))
        if single_score is None:
            invalid_score_fields += 1
        if multi_score is None:
            invalid_score_fields += 1
        if single_score is None and multi_score is None:
            invalid_rows += 1

        if match.status != "MATCHED":
            continue
        if match.hardware is None:
            errors.append(f"{match.name}: matched row has no hardware")
            continue

        samples = _parse_samples(row.get("devices/samples"))
        for score, test_type in (
            (single_score, SINGLE_CORE_TEST_TYPE),
            (multi_score, MULTI_CORE_TEST_TYPE),
        ):
            if score is None:
                continue

            key = _logical_key(
                match.hardware.hardware_id,
                score,
                test_type,
                source_id,
            )
            if key in seen_keys:
                duplicate_logical_scores += 1
                continue
            if key in existing_keys:
                skipped_existing += 1
                seen_keys.add(key)
                continue

            seen_keys.add(key)
            planned.append(
                PlannedScore(
                    hardware_id=match.hardware.hardware_id,
                    hardware_name=match.hardware.name,
                    cpu_name=match.name,
                    score=score,
                    test_type=test_type,
                    samples=samples,
                )
            )

    source_name_counts: dict[str, int] = {}
    for row in rows:
        name = (row.get("devices/name") or "").strip()
        source_name_counts[name] = source_name_counts.get(name, 0) + 1
    duplicate_source_rows = sum(
        count - 1
        for count in source_name_counts.values()
        if count > 1
    )

    return ScoreImportPlan(
        scores=tuple(planned),
        matched_rows=sum(match.status == "MATCHED" for match in audit.rows),
        unmatched_rows=sum(match.status == "UNMATCHED" for match in audit.rows),
        ambiguous_rows=sum(match.status == "AMBIGUOUS" for match in audit.rows),
        invalid_rows=invalid_rows,
        invalid_score_fields=invalid_score_fields,
        duplicate_source_rows=duplicate_source_rows,
        duplicate_logical_scores=duplicate_logical_scores,
        skipped_existing=skipped_existing,
        errors=tuple(errors),
    )


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(
        select(Source).where(
            Source.name == GEEKBENCH_SOURCE_NAME,
            Source.url == GEEKBENCH_SOURCE_URL,
        )
    )
    if source is None:
        source = Source(
            name=GEEKBENCH_SOURCE_NAME,
            url=GEEKBENCH_SOURCE_URL,
        )
        session.add(source)
        session.flush()
    return source


def apply_score_import_plan(
    plan: ScoreImportPlan,
    session: Session,
) -> ScoreImportSummary:
    """Apply the complete plan atomically; integrity errors propagate."""
    if plan.errors:
        session.rollback()
        return ScoreImportSummary(
            planned=len(plan.scores),
            inserted=0,
            skipped=plan.skipped_existing + plan.duplicate_logical_scores,
            invalid=plan.invalid_rows,
            invalid_score_fields=plan.invalid_score_fields,
            unmatched=plan.unmatched_rows,
            ambiguous=plan.ambiguous_rows,
            duplicate_source_rows=plan.duplicate_source_rows,
            duplicate_logical_scores=plan.duplicate_logical_scores,
            errors=len(plan.errors),
            error_messages=plan.errors,
        )

    if not plan.scores:
        session.rollback()
        return ScoreImportSummary(
            planned=0,
            inserted=0,
            skipped=plan.skipped_existing + plan.duplicate_logical_scores,
            invalid=plan.invalid_rows,
            invalid_score_fields=plan.invalid_score_fields,
            unmatched=plan.unmatched_rows,
            ambiguous=plan.ambiguous_rows,
            duplicate_source_rows=plan.duplicate_source_rows,
            duplicate_logical_scores=plan.duplicate_logical_scores,
            errors=0,
        )

    session.rollback()
    inserted = 0
    try:
        with session.begin():
            source = _get_or_create_source(session)
            for score in plan.scores:
                session.add(
                    BenchmarkResult(
                        hardware_id=score.hardware_id,
                        benchmark_name=BENCHMARK_NAME,
                        score=score.score,
                        unit=SCORE_UNIT,
                        test_type=score.test_type,
                        source_id=source.id,
                        recorded_at=None,
                    )
                )
                inserted += 1
    except Exception:
        session.rollback()
        raise

    return ScoreImportSummary(
        planned=len(plan.scores),
        inserted=inserted,
        skipped=plan.skipped_existing + plan.duplicate_logical_scores,
        invalid=plan.invalid_rows,
        invalid_score_fields=plan.invalid_score_fields,
        unmatched=plan.unmatched_rows,
        ambiguous=plan.ambiguous_rows,
        duplicate_source_rows=plan.duplicate_source_rows,
        duplicate_logical_scores=plan.duplicate_logical_scores,
        errors=0,
    )


def import_geekbench_scores(
    csv_path: str | Path,
    session: Session | None = None,
) -> ScoreImportSummary:
    if session is not None:
        plan = build_score_import_plan(csv_path, session)
        return apply_score_import_plan(plan, session)

    with SessionLocal() as owned_session:
        plan = build_score_import_plan(csv_path, owned_session)
        return apply_score_import_plan(plan, owned_session)


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _print_plan(plan: ScoreImportPlan) -> None:
    print("GEEKBENCH 7 SCORE IMPORT PREFLIGHT")
    print(f"Matched rows: {plan.matched_rows}")
    print(f"Unmatched rows: {plan.unmatched_rows}")
    print(f"Ambiguous rows: {plan.ambiguous_rows}")
    print(f"Invalid rows: {plan.invalid_rows}")
    print(f"Invalid score fields skipped: {plan.invalid_score_fields}")
    print(f"Duplicate source rows: {plan.duplicate_source_rows}")
    print(f"Duplicate logical scores skipped: {plan.duplicate_logical_scores}")
    print(f"Already-existing results skipped: {plan.skipped_existing}")
    print(f"Planned single-core inserts: {len(plan.single_core_scores)}")
    print(f"Planned multi-core inserts: {len(plan.multi_core_scores)}")
    print(f"Planned total inserts: {len(plan.scores)}")
    print(f"Plan errors: {len(plan.errors)}")
    for error in plan.errors:
        print(f"  {error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import exact-match Geekbench 7 CPU scores."
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    dataset_path = args.dataset.resolve()
    database_path = args.database.resolve()
    for path, label in (
        (dataset_path, "Dataset"),
        (database_path, "Database"),
    ):
        if not path.is_file():
            raise SystemExit(f"{label} not found: {path}")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        before_hardware = _count(session, Hardware)
        before_specs = _count(session, CPUSpecification)
        before_results = _count(session, BenchmarkResult)
        before_sources = _count(session, Source)
        plan = build_score_import_plan(dataset_path, session)
        _print_plan(plan)
        summary = apply_score_import_plan(plan, session)
        after_hardware = _count(session, Hardware)
        after_specs = _count(session, CPUSpecification)
        after_results = _count(session, BenchmarkResult)
        after_sources = _count(session, Source)
    engine.dispose()

    print("\nGEEKBENCH 7 SCORE IMPORT RESULT")
    print(f"Hardware before/after: {before_hardware}/{after_hardware}")
    print(f"CPUSpecification before/after: {before_specs}/{after_specs}")
    print(f"BenchmarkResult before/after: {before_results}/{after_results}")
    print(f"Source before/after: {before_sources}/{after_sources}")
    print(f"Inserted: {summary.inserted}")
    print(f"Skipped: {summary.skipped}")
    print(f"Invalid: {summary.invalid}")
    print(f"Invalid score fields skipped: {summary.invalid_score_fields}")
    print(f"Errors: {summary.errors}")
    if summary.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
