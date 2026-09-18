"""Enrich existing CPU specifications with exact benchmark catalog values."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import SessionLocal
from backend.app.importers.benchmark_matcher import normalize_match_name
from backend.app.importers.benchmark_normalizer import normalize_benchmark_row
from backend.app.importers.geekbench_match_audit import DEFAULT_DATABASE_PATH
from backend.app.models import BenchmarkResult, CPUSpecification, Hardware, Source


SOURCE_NAME = "PassMark CPU benchmark catalog (benchmark-cpus.csv)"
SOURCE_URL = "https://www.cpubenchmark.net/"
DEFAULT_CATALOG_PATH = (
    Path.home() / "Downloads" / "benchmark" / "benchmark-cpus.csv"
)
CATALOG_NAME_COLUMN = "CpuName"


@dataclass(frozen=True)
class CatalogRecord:
    name: str
    manufacturer: str
    socket: str | None
    threads: str | None
    source_row: int


@dataclass(frozen=True)
class PlannedUpdate:
    hardware_id: int
    hardware_name: str
    field: str
    value: str | int


@dataclass(frozen=True)
class EnrichmentPlan:
    updates: tuple[PlannedUpdate, ...]
    matched_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    invalid_rows: int
    skipped_existing: int
    errors: tuple[str, ...] = ()

    @property
    def socket_updates(self) -> tuple[PlannedUpdate, ...]:
        return tuple(update for update in self.updates if update.field == "socket")

    @property
    def threads_updates(self) -> tuple[PlannedUpdate, ...]:
        return tuple(update for update in self.updates if update.field == "threads")


@dataclass(frozen=True)
class EnrichmentSummary:
    planned_updates: int
    actual_updates: int
    socket_updates: int
    threads_updates: int
    matched_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    invalid_rows: int
    skipped_existing: int
    errors: int
    error_messages: tuple[str, ...] = ()


def _read_catalog(path: Path) -> list[CatalogRecord]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or CATALOG_NAME_COLUMN not in reader.fieldnames:
            raise ValueError(f"CPU catalog must contain {CATALOG_NAME_COLUMN!r}")

        records: list[CatalogRecord] = []
        for source_row, row in enumerate(reader, start=2):
            data = normalize_benchmark_row(row)
            name = data.get("name")
            manufacturer = data.get("manufacturer")
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(manufacturer, str) or not manufacturer:
                continue

            socket = row.get("Socket")
            socket = socket.strip() if socket is not None else None
            socket = socket or None
            records.append(
                CatalogRecord(
                    name=(row.get(CATALOG_NAME_COLUMN) or "").strip(),
                    manufacturer=manufacturer,
                    socket=socket,
                    threads=(row.get("Threads") or "").strip() or None,
                    source_row=source_row,
                )
            )
        return records


def _parse_positive_threads(value: object | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[1-9]\d*", text):
        return None
    return int(text)


def _catalog_key(record: CatalogRecord) -> tuple[str, str] | None:
    normalized_name = normalize_match_name(record.name)
    if not normalized_name or not record.manufacturer:
        return None
    return record.manufacturer.lower(), normalized_name


def _hardware_lookup(
    hardware: list[Hardware],
) -> dict[tuple[str, str], tuple[Hardware, ...]]:
    grouped: defaultdict[tuple[str, str], list[Hardware]] = defaultdict(list)
    for item in hardware:
        normalized_name = normalize_match_name(item.name)
        if normalized_name:
            grouped[(item.manufacturer.lower(), normalized_name)].append(item)
    return {key: tuple(items) for key, items in grouped.items()}


def _catalog_lookup(
    records: list[CatalogRecord],
) -> dict[tuple[str, str], tuple[CatalogRecord, ...]]:
    grouped: defaultdict[tuple[str, str], list[CatalogRecord]] = defaultdict(list)
    for record in records:
        key = _catalog_key(record)
        if key is not None:
            grouped[key].append(record)
    return {key: tuple(items) for key, items in grouped.items()}


def _empty_summary(plan: EnrichmentPlan) -> EnrichmentSummary:
    return EnrichmentSummary(
        planned_updates=len(plan.updates),
        actual_updates=0,
        socket_updates=len(plan.socket_updates),
        threads_updates=len(plan.threads_updates),
        matched_rows=plan.matched_rows,
        unmatched_rows=plan.unmatched_rows,
        ambiguous_rows=plan.ambiguous_rows,
        invalid_rows=plan.invalid_rows,
        skipped_existing=plan.skipped_existing,
        errors=len(plan.errors),
        error_messages=plan.errors,
    )


def build_enrichment_plan(
    catalog_path: str | Path,
    session: Session,
) -> EnrichmentPlan:
    """Build and validate all exact-match field updates without writing."""
    records = _read_catalog(Path(catalog_path))
    hardware = session.scalars(select(Hardware).where(Hardware.type == "CPU")).all()
    hardware_by_key = _hardware_lookup(hardware)
    catalog_by_key = _catalog_lookup(records)
    updates: list[PlannedUpdate] = []
    skipped_existing = 0
    invalid_rows = 0
    matched_rows = 0
    unmatched_rows = 0
    ambiguous_rows = 0
    errors: list[str] = []

    for item in hardware:
        key = (item.manufacturer.lower(), normalize_match_name(item.name))
        if key[1] is None:
            unmatched_rows += 1
            continue
        candidates = catalog_by_key.get(key, ())
        if not candidates:
            unmatched_rows += 1
            continue
        if len(hardware_by_key.get(key, ())) != 1 or len(candidates) != 1:
            ambiguous_rows += 1
            continue

        matched_rows += 1
        record = candidates[0]
        specification = item.cpu_specification
        if specification is None:
            errors.append(f"{item.name}: matched Hardware has no CPUSpecification")
            continue

        valid_threads = _parse_positive_threads(record.threads)
        if record.threads and valid_threads is None:
            invalid_rows += 1
        if specification.socket is None:
            if record.socket is not None:
                updates.append(
                    PlannedUpdate(item.id, item.name, "socket", record.socket)
                )
        else:
            skipped_existing += 1

        if specification.threads is None:
            if valid_threads is not None:
                updates.append(
                    PlannedUpdate(item.id, item.name, "threads", valid_threads)
                )
        else:
            skipped_existing += 1

    return EnrichmentPlan(
        updates=tuple(updates),
        matched_rows=matched_rows,
        unmatched_rows=unmatched_rows,
        ambiguous_rows=ambiguous_rows,
        invalid_rows=invalid_rows,
        skipped_existing=skipped_existing,
        errors=tuple(errors),
    )


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(
        select(Source).where(Source.name == SOURCE_NAME, Source.url == SOURCE_URL)
    )
    if source is None:
        source = Source(name=SOURCE_NAME, url=SOURCE_URL)
        session.add(source)
        session.flush()
    return source


def apply_enrichment_plan(
    plan: EnrichmentPlan,
    session: Session,
) -> EnrichmentSummary:
    """Apply a validated plan atomically; database failures propagate."""
    if plan.errors or not plan.updates:
        session.rollback()
        return _empty_summary(plan)

    session.rollback()
    actual_updates = 0
    socket_updates = 0
    threads_updates = 0
    try:
        with session.begin():
            _get_or_create_source(session)
            for update in plan.updates:
                specification = session.scalar(
                    select(CPUSpecification).where(
                        CPUSpecification.hardware_id == update.hardware_id
                    )
                )
                if specification is None or getattr(specification, update.field) is not None:
                    raise RuntimeError(
                        f"precondition changed for Hardware {update.hardware_id}"
                    )
                setattr(specification, update.field, update.value)
                actual_updates += 1
                if update.field == "socket":
                    socket_updates += 1
                else:
                    threads_updates += 1
    except Exception:
        session.rollback()
        raise

    return EnrichmentSummary(
        planned_updates=len(plan.updates),
        actual_updates=actual_updates,
        socket_updates=socket_updates,
        threads_updates=threads_updates,
        matched_rows=plan.matched_rows,
        unmatched_rows=plan.unmatched_rows,
        ambiguous_rows=plan.ambiguous_rows,
        invalid_rows=plan.invalid_rows,
        skipped_existing=plan.skipped_existing,
        errors=0,
    )


def enrich_catalog_cpus_v2(
    catalog_path: str | Path,
    session: Session | None = None,
) -> EnrichmentSummary:
    if session is not None:
        plan = build_enrichment_plan(catalog_path, session)
        return apply_enrichment_plan(plan, session)

    with SessionLocal() as owned_session:
        plan = build_enrichment_plan(catalog_path, owned_session)
        return apply_enrichment_plan(plan, owned_session)


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _print_plan(plan: EnrichmentPlan) -> None:
    print("CPU CATALOG ENRICHMENT V2 PREFLIGHT")
    print(f"Matched rows: {plan.matched_rows}")
    print(f"Unmatched rows: {plan.unmatched_rows}")
    print(f"Ambiguous rows: {plan.ambiguous_rows}")
    print(f"Invalid rows: {plan.invalid_rows}")
    print(f"Existing field values skipped: {plan.skipped_existing}")
    print(f"Planned socket updates: {len(plan.socket_updates)}")
    print(f"Planned threads updates: {len(plan.threads_updates)}")
    print(f"Planned total updates: {len(plan.updates)}")
    print(f"Plan errors: {len(plan.errors)}")
    for error in plan.errors:
        print(f"  {error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enrich existing CPU socket and threads values by exact match."
    )
    parser.add_argument("catalog", nargs="?", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("database", nargs="?", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply the validated plan; default is read-only preflight.",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Expect an already-enriched database and require a 0-update plan.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    catalog_path = args.catalog.resolve()
    database_path = args.database.resolve()
    for path, label in ((catalog_path, "CPU catalog"), (database_path, "Database")):
        if not path.is_file():
            raise SystemExit(f"{label} not found: {path}")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        with factory() as session:
            before = {
                "hardware": _count(session, Hardware),
                "specifications": _count(session, CPUSpecification),
                "benchmarks": _count(session, BenchmarkResult),
                "sources": _count(session, Source),
            }
            plan = build_enrichment_plan(catalog_path, session)
            _print_plan(plan)
            expected_plan = (0, 0, 0) if args.rerun else (26, 11, 37)
            actual_plan = (
                len(plan.socket_updates),
                len(plan.threads_updates),
                len(plan.updates),
            )
            if actual_plan != expected_plan:
                raise SystemExit(
                    "Preflight discrepancy: expected socket=26, threads=11, total=37 "
                    "for a new import or 0/0/0 with --rerun"
                )
            summary = apply_enrichment_plan(plan, session) if args.execute else _empty_summary(plan)
            after = {
                "hardware": _count(session, Hardware),
                "specifications": _count(session, CPUSpecification),
                "benchmarks": _count(session, BenchmarkResult),
                "sources": _count(session, Source),
            }
    finally:
        engine.dispose()

    print("\nCPU CATALOG ENRICHMENT V2 RESULT")
    print(f"Counts before: {before}")
    print(f"Counts after: {after}")
    print(f"Planned updates: {summary.planned_updates}")
    print(f"Actual updates: {summary.actual_updates}")
    print(f"Socket updates: {summary.socket_updates}")
    print(f"Threads updates: {summary.threads_updates}")
    print(f"Errors: {summary.errors}")
    if summary.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
