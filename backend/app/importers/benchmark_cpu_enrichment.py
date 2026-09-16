"""Transactional import of deterministic CPU catalog candidates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.importers.benchmark_matcher import (
    load_cpu_lookup,
    normalize_match_name,
)
from backend.app.importers.geekbench_match_audit import (
    DEFAULT_DATABASE_PATH,
)
from backend.app.importers.geekbench_unmatched_audit import (
    CATALOG_AVAILABLE,
    DEFAULT_CATALOG_PATH,
    DEFAULT_GEEKBENCH_PATH,
    CatalogEntry,
    audit_unmatched,
)
from backend.app.models import CPUSpecification, Hardware, Source


SOURCE_NAME = "PassMark CPU benchmark catalog (benchmark-cpus.csv)"
SOURCE_URL = "https://www.cpubenchmark.net/"


@dataclass(frozen=True)
class EnrichmentPlan:
    candidates: tuple[CatalogEntry, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class EnrichmentSummary:
    candidates: int
    inserted: int
    skipped: int
    errors: int
    error_messages: tuple[str, ...] = ()


def _parse_release_date(value: str | None) -> date | None:
    """Only accept an exact date; catalog quarters are not guessed."""
    if not value:
        return None

    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _entry_key(entry: CatalogEntry) -> tuple[str, str] | None:
    normalized_name = normalize_match_name(entry.name)
    if not normalized_name or not entry.manufacturer:
        return None
    return entry.manufacturer.lower(), normalized_name


def _validate_entry(entry: CatalogEntry) -> list[str]:
    errors: list[str] = []

    if not entry.name:
        errors.append("name is required")
    if not entry.manufacturer or entry.manufacturer == "Unknown":
        errors.append("manufacturer must be deterministically known")
    if not normalize_match_name(entry.name):
        errors.append("name has no normalized identity")
    if not entry.source_url:
        errors.append("source URL is required for catalog provenance")

    return errors


def build_enrichment_plan(
    geekbench_path: str | Path,
    catalog_path: str | Path,
    session: Session,
) -> EnrichmentPlan:
    """Build and validate the exact catalog-only insertion plan."""
    audit = audit_unmatched(geekbench_path, catalog_path, session)
    records = [
        record
        for record in audit.records
        if record.category == CATALOG_AVAILABLE
    ]
    lookup = load_cpu_lookup(session)
    candidates: list[CatalogEntry] = []
    skipped: list[str] = []
    errors: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for record in records:
        if len(record.catalog_entries) != 1:
            errors.append(
                f"{record.name}: catalog candidate is not unique"
            )
            continue

        entry = record.catalog_entries[0]
        entry_errors = _validate_entry(entry)
        key = _entry_key(entry)

        if key is None:
            entry_errors.append("unable to construct exact normalized identity")
        elif key in seen_keys:
            entry_errors.append("duplicate candidate identity in import batch")
        elif key in lookup:
            skipped.append(entry.name)
            continue

        if entry_errors:
            errors.extend(
                f"{entry.name}: {error}"
                for error in entry_errors
            )
            continue

        assert key is not None
        seen_keys.add(key)
        candidates.append(entry)

    return EnrichmentPlan(
        candidates=tuple(candidates),
        skipped=tuple(skipped),
        errors=tuple(errors),
    )


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(
        select(Source).where(
            Source.name == SOURCE_NAME,
            Source.url == SOURCE_URL,
        )
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
    """Apply a fully validated plan atomically, or roll it back entirely."""
    if plan.errors:
        session.rollback()
        return EnrichmentSummary(
            candidates=len(plan.candidates),
            inserted=0,
            skipped=len(plan.skipped),
            errors=len(plan.errors),
            error_messages=plan.errors,
        )

    if not plan.candidates:
        session.rollback()
        return EnrichmentSummary(
            candidates=0,
            inserted=0,
            skipped=len(plan.skipped),
            errors=0,
        )

    inserted = 0
    try:
        session.rollback()
        with session.begin():
            _get_or_create_source(session)
            for entry in plan.candidates:
                hardware = Hardware(
                    name=entry.name,
                    manufacturer=entry.manufacturer,
                    type="CPU",
                    release_date=_parse_release_date(entry.release_date),
                )
                hardware.cpu_specification = CPUSpecification(
                    cores=entry.cores,
                    threads=entry.threads,
                    base_clock_ghz=entry.base_clock_ghz,
                    boost_clock_ghz=entry.boost_clock_ghz,
                    tdp_w=entry.tdp_w,
                    socket=entry.socket,
                )
                session.add(hardware)
                inserted += 1
    except Exception as error:
        session.rollback()
        return EnrichmentSummary(
            candidates=len(plan.candidates),
            inserted=0,
            skipped=len(plan.skipped),
            errors=1,
            error_messages=(f"transaction rolled back: {error}",),
        )

    return EnrichmentSummary(
        candidates=len(plan.candidates),
        inserted=inserted,
        skipped=len(plan.skipped),
        errors=0,
    )


def enrich_catalog_cpus(
    geekbench_path: str | Path,
    catalog_path: str | Path,
    session: Session | None = None,
) -> EnrichmentSummary:
    """Enrich only exact catalog candidates using one transaction."""
    if session is not None:
        plan = build_enrichment_plan(geekbench_path, catalog_path, session)
        return apply_enrichment_plan(plan, session)

    from backend.app.database import SessionLocal

    with SessionLocal() as owned_session:
        plan = build_enrichment_plan(
            geekbench_path,
            catalog_path,
            owned_session,
        )
        return apply_enrichment_plan(plan, owned_session)


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _print_plan(plan: EnrichmentPlan) -> None:
    print("ENRICHMENT PLAN")
    print(f"Candidates to insert: {len(plan.candidates)}")
    for entry in plan.candidates:
        print(f"  {entry.name}")
    print(f"Already present/skipped: {len(plan.skipped)}")
    for name in plan.skipped:
        print(f"  {name}")
    print(f"Validation errors: {len(plan.errors)}")
    for error in plan.errors:
        print(f"  {error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import deterministic benchmark CPU catalog candidates."
    )
    parser.add_argument(
        "geekbench",
        nargs="?",
        type=Path,
        default=DEFAULT_GEEKBENCH_PATH,
    )
    parser.add_argument(
        "catalog",
        nargs="?",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
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
    geekbench_path = args.geekbench.resolve()
    catalog_path = args.catalog.resolve()
    database_path = args.database.resolve()

    for path, label in (
        (geekbench_path, "Geekbench dataset"),
        (catalog_path, "CPU catalog"),
        (database_path, "Database"),
    ):
        if not path.is_file():
            raise SystemExit(f"{label} not found: {path}")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    before_engine_session = session_factory()
    try:
        before_hardware = _count(before_engine_session, Hardware)
        before_specs = _count(before_engine_session, CPUSpecification)
        plan = build_enrichment_plan(
            geekbench_path,
            catalog_path,
            before_engine_session,
        )
        _print_plan(plan)
        summary = apply_enrichment_plan(plan, before_engine_session)
        after_hardware = _count(before_engine_session, Hardware)
        after_specs = _count(before_engine_session, CPUSpecification)
    finally:
        before_engine_session.close()
        engine.dispose()

    print()
    print("ENRICHMENT RESULT")
    print(f"Hardware before: {before_hardware}")
    print(f"Hardware after: {after_hardware}")
    print(f"CPUSpecification before: {before_specs}")
    print(f"CPUSpecification after: {after_specs}")
    print(f"Candidates: {summary.candidates}")
    print(f"Inserted: {summary.inserted}")
    print(f"Skipped: {summary.skipped}")
    print(f"Errors: {summary.errors}")
    for error in summary.error_messages:
        print(f"  {error}")

    if summary.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
