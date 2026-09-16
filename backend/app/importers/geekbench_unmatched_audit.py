"""Read-only audit explaining unmatched Geekbench CPU names."""

from __future__ import annotations

import argparse
import csv
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.importers.benchmark_matcher import normalize_match_name
from backend.app.importers.benchmark_normalizer import (
    normalize_benchmark_row,
)
from backend.app.importers.geekbench_match_audit import (
    DEFAULT_DATABASE_PATH,
    _read_only_engine,
    audit_dataset,
)
from backend.app.models import Hardware


DEFAULT_GEEKBENCH_PATH = (
    Path.home() / "Downloads" / "benchmark" / "processor-benchmarks.csv"
)
DEFAULT_CATALOG_PATH = (
    Path.home() / "Downloads" / "benchmark" / "benchmark-cpus.csv"
)

CATALOG_NAME_COLUMN = "CpuName"
GEEKBENCH_NAME_COLUMN = "devices/name"

CATALOG_AVAILABLE = "CATALOG_AVAILABLE_NOT_IN_DB"
NORMALIZATION_GAP = "NORMALIZATION_GAP"
NOT_FOUND = "NOT_FOUND_IN_CURRENT_CATALOGS"
NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    manufacturer: str
    cores: int | None
    threads: int | None
    base_clock_ghz: float | None
    boost_clock_ghz: float | None
    tdp_w: float | None
    socket: str | None
    release_date: str | None
    source_url: str | None


@dataclass(frozen=True)
class HardwareEntry:
    name: str
    hardware_id: int
    normalized_name: str


@dataclass(frozen=True)
class UnmatchedAuditRecord:
    name: str
    manufacturer: str
    normalized_name: str | None
    category: str
    catalog_entries: tuple[CatalogEntry, ...] = ()
    hardware: HardwareEntry | None = None
    reason: str = ""


@dataclass(frozen=True)
class UnmatchedAuditResult:
    records: tuple[UnmatchedAuditRecord, ...]


def _read_catalog_rows(catalog_path: Path) -> list[dict[str, str]]:
    with catalog_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or CATALOG_NAME_COLUMN not in reader.fieldnames:
            raise ValueError(
                f"CPU catalog must contain the {CATALOG_NAME_COLUMN!r} column"
            )
        return list(reader)


def _catalog_entry(row: dict[str, str]) -> CatalogEntry | None:
    data = normalize_benchmark_row(row)
    name = data.get("name")
    manufacturer = data.get("manufacturer")
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(manufacturer, str) or not manufacturer:
        return None

    return CatalogEntry(
        name=(row.get(CATALOG_NAME_COLUMN) or "").strip(),
        manufacturer=manufacturer,
        cores=data.get("cores"),
        threads=data.get("threads"),
        base_clock_ghz=data.get("base_clock_ghz"),
        boost_clock_ghz=data.get("boost_clock_ghz"),
        tdp_w=data.get("tdp_w"),
        socket=data.get("socket"),
        release_date=data.get("release_date"),
        source_url=data.get("source_url"),
    )


def _catalog_lookup(
    catalog_rows: Iterable[dict[str, str]],
) -> dict[tuple[str, str], tuple[CatalogEntry, ...]]:
    grouped: defaultdict[tuple[str, str], list[CatalogEntry]] = defaultdict(list)

    for row in catalog_rows:
        entry = _catalog_entry(row)
        if entry is None:
            continue

        normalized_name = normalize_match_name(
            normalize_benchmark_row(row).get("name")
        )
        if not normalized_name:
            continue

        grouped[(entry.manufacturer.lower(), normalized_name)].append(entry)

    return {
        key: tuple(entries)
        for key, entries in grouped.items()
    }


def _strip_format_characters(value: str) -> str:
    return "".join(
        character
        for character in value
        if unicodedata.category(character) != "Cf"
    )


def _hardware_gap_lookup(
    cpus: Iterable[Hardware],
) -> dict[tuple[str, str], tuple[HardwareEntry, ...]]:
    grouped: defaultdict[tuple[str, str], list[HardwareEntry]] = defaultdict(list)

    for cpu in cpus:
        cleaned_name = _strip_format_characters(cpu.name)
        normalized_name = normalize_match_name(cleaned_name)
        if not normalized_name:
            continue

        grouped[(cpu.manufacturer.lower(), normalized_name)].append(
            HardwareEntry(
                name=cpu.name,
                hardware_id=cpu.id,
                normalized_name=normalized_name,
            )
        )

    return {
        key: tuple(entries)
        for key, entries in grouped.items()
    }


def _classify_unmatched(
    unmatched_records: Iterable,
    catalog_lookup: dict[tuple[str, str], tuple[CatalogEntry, ...]],
    hardware_gap_lookup: dict[tuple[str, str], tuple[HardwareEntry, ...]],
) -> UnmatchedAuditResult:
    records: list[UnmatchedAuditRecord] = []

    for unmatched in unmatched_records:
        name = unmatched.name
        manufacturer = unmatched.manufacturer
        normalized_name = unmatched.normalized_name
        key = (
            manufacturer.lower(),
            normalized_name,
        ) if normalized_name else None

        if key is not None:
            hardware_candidates = hardware_gap_lookup.get(key, ())
            if hardware_candidates:
                if len(hardware_candidates) == 1:
                    records.append(
                        UnmatchedAuditRecord(
                            name=name,
                            manufacturer=manufacturer,
                            normalized_name=normalized_name,
                            category=NORMALIZATION_GAP,
                            hardware=hardware_candidates[0],
                            reason=(
                                "existing Hardware name contains Unicode format "
                                "character(s) removed for this diagnostic comparison"
                            ),
                        )
                    )
                    continue

                records.append(
                    UnmatchedAuditRecord(
                        name=name,
                        manufacturer=manufacturer,
                        normalized_name=normalized_name,
                        category=NEEDS_REVIEW,
                        reason=(
                            "normalization repair produces multiple Hardware "
                            "candidates"
                        ),
                    )
                )
                continue

            catalog_candidates = catalog_lookup.get(key, ())
            if len(catalog_candidates) == 1:
                records.append(
                    UnmatchedAuditRecord(
                        name=name,
                        manufacturer=manufacturer,
                        normalized_name=normalized_name,
                        category=CATALOG_AVAILABLE,
                        catalog_entries=catalog_candidates,
                        reason="one exact normalized catalog entry; no DB Hardware match",
                    )
                )
                continue

            if len(catalog_candidates) > 1:
                records.append(
                    UnmatchedAuditRecord(
                        name=name,
                        manufacturer=manufacturer,
                        normalized_name=normalized_name,
                        category=NEEDS_REVIEW,
                        catalog_entries=catalog_candidates,
                        reason=(
                            "multiple exact normalized catalog entries; "
                            "automatic classification is unsafe"
                        ),
                    )
                )
                continue

        records.append(
            UnmatchedAuditRecord(
                name=name,
                manufacturer=manufacturer,
                normalized_name=normalized_name,
                category=NOT_FOUND,
                reason="not found by exact normalized key in current DB or catalog",
            )
        )

    return UnmatchedAuditResult(records=tuple(records))


def audit_unmatched(
    geekbench_path: str | Path,
    catalog_path: str | Path,
    session: Session,
) -> UnmatchedAuditResult:
    """Classify unmatched Geekbench rows without writing to the database."""
    match_result = audit_dataset(geekbench_path, session)
    unmatched_records = (
        record
        for record in match_result.rows
        if record.status == "UNMATCHED"
    )
    catalog_lookup = _catalog_lookup(
        _read_catalog_rows(Path(catalog_path))
    )
    cpus = session.scalars(
        select(Hardware).where(Hardware.type == "CPU")
    ).all()
    return _classify_unmatched(
        unmatched_records,
        catalog_lookup,
        _hardware_gap_lookup(cpus),
    )


def _unique_records(
    records: Iterable[UnmatchedAuditRecord],
    category: str,
) -> list[UnmatchedAuditRecord]:
    result: list[UnmatchedAuditRecord] = []
    seen: set[str] = set()

    for record in records:
        if record.category != category or record.name in seen:
            continue
        seen.add(record.name)
        result.append(record)

    return result


def _format_value(value: object | None) -> str:
    return "-" if value is None or value == "" else str(value)


def _display_name(value: str) -> str:
    """Keep hidden Unicode format characters visible and terminal-safe."""
    return "".join(
        f"<U+{ord(character):04X}>"
        if unicodedata.category(character) == "Cf"
        else character
        for character in value
    )


def _print_catalog_entry(entry: CatalogEntry) -> None:
    print(f"  {_display_name(entry.name)}")
    print(
        "    specs: "
        f"cores={_format_value(entry.cores)}, "
        f"threads={_format_value(entry.threads)}, "
        f"base={_format_value(entry.base_clock_ghz)} GHz, "
        f"boost={_format_value(entry.boost_clock_ghz)} GHz, "
        f"tdp={_format_value(entry.tdp_w)} W, "
        f"socket={_format_value(entry.socket)}, "
        f"release={_format_value(entry.release_date)}"
    )
    print(f"    source: {_format_value(entry.source_url)}")


def _print_report(
    result: UnmatchedAuditResult,
    geekbench_path: Path,
    catalog_path: Path,
    database_path: Path,
) -> None:
    records = result.records
    counts = Counter(record.category for record in records)
    unique_counts = {
        category: len(_unique_records(records, category))
        for category in (
            CATALOG_AVAILABLE,
            NORMALIZATION_GAP,
            NOT_FOUND,
            NEEDS_REVIEW,
        )
    }

    print("Geekbench Unmatched CPU Audit")
    print(f"Geekbench dataset: {geekbench_path}")
    print(f"CPU catalog: {catalog_path}")
    print(f"Database: {database_path}")
    print("Database access: READ-ONLY (SQLite mode=ro)")
    print()

    print("SUMMARY")
    print(f"Total unmatched Geekbench rows: {len(records)}")
    print(f"Unique unmatched CPU names: {len({record.name for record in records})}")
    for category in (
        CATALOG_AVAILABLE,
        NORMALIZATION_GAP,
        NOT_FOUND,
        NEEDS_REVIEW,
    ):
        print(
            f"{category}: {counts[category]} rows, "
            f"{unique_counts[category]} unique names"
        )
    print()

    print("CATEGORY EXAMPLES AND DETAILS")
    catalog_records = _unique_records(records, CATALOG_AVAILABLE)
    print(f"\n{CATALOG_AVAILABLE} ({len(catalog_records)} unique names):")
    for record in catalog_records:
        print(f"  Geekbench: {_display_name(record.name)}")
        for entry in record.catalog_entries:
            print(f"  Catalog:  {_display_name(entry.name)}")
            print(
                "  Specs:    "
                f"cores={_format_value(entry.cores)}, "
                f"threads={_format_value(entry.threads)}, "
                f"base={_format_value(entry.base_clock_ghz)} GHz, "
                f"boost={_format_value(entry.boost_clock_ghz)} GHz, "
                f"tdp={_format_value(entry.tdp_w)} W, "
                f"socket={_format_value(entry.socket)}, "
                f"release={_format_value(entry.release_date)}"
            )
            print(f"  Source:   {_format_value(entry.source_url)}")

    normalization_records = _unique_records(records, NORMALIZATION_GAP)
    print(f"\n{NORMALIZATION_GAP} ({len(normalization_records)} unique names):")
    for record in normalization_records:
        assert record.hardware is not None
        print(f"  {_display_name(record.name)}")
        print(
            "    -> Hardware: "
            f"{_display_name(record.hardware.name)} "
            f"(id={record.hardware.hardware_id})"
        )
        print(f"    -> normalized Geekbench: {record.normalized_name}")
        print(f"    -> normalized Hardware: {record.hardware.normalized_name}")
        print(f"    -> reason: {record.reason}")

    review_records = _unique_records(records, NEEDS_REVIEW)
    print(f"\n{NEEDS_REVIEW} ({len(review_records)} unique names):")
    for record in review_records:
        print(f"  {_display_name(record.name)} -> {record.reason}")
        for entry in record.catalog_entries:
            _print_catalog_entry(entry)

    not_found_records = _unique_records(records, NOT_FOUND)
    print(f"\n{NOT_FOUND} ({len(not_found_records)} unique names):")
    for record in not_found_records:
        print(f"  {_display_name(record.name)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explain unmatched Geekbench CPUs using exact catalog and "
            "normalization checks only."
        )
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

    engine: Engine = _read_only_engine(database_path)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        with session_factory() as session:
            result = audit_unmatched(geekbench_path, catalog_path, session)
        _print_report(result, geekbench_path, catalog_path, database_path)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
