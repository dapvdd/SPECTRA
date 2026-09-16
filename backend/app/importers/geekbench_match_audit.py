"""Read-only exact-match audit for the Geekbench 7 CPU catalog."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.importers.benchmark_matcher import (
    find_matching_cpu,
    load_cpu_lookup,
    normalize_match_name,
)
from backend.app.importers.benchmark_normalizer import detect_manufacturer
from backend.app.models import Hardware


DATASET_NAME_COLUMN = "devices/name"
DEFAULT_DATASET_PATH = (
    Path.home() / "Downloads" / "benchmark" / "processor-benchmarks.csv"
)
DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "spectra.db"
)


@dataclass(frozen=True)
class Candidate:
    name: str
    hardware_id: int


@dataclass(frozen=True)
class AuditRecord:
    name: str
    manufacturer: str
    normalized_name: str | None
    status: str
    hardware: Candidate | None = None
    candidates: tuple[Candidate, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class AuditResult:
    rows: tuple[AuditRecord, ...]
    duplicate_names: tuple[tuple[str, int], ...]


def _read_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or DATASET_NAME_COLUMN not in reader.fieldnames:
            raise ValueError(
                f"Geekbench CSV must contain the {DATASET_NAME_COLUMN!r} column"
            )
        return list(reader)


def _candidate_groups(
    cpus: Iterable[Hardware],
) -> dict[tuple[str, str], tuple[Candidate, ...]]:
    grouped: defaultdict[tuple[str, str], list[Candidate]] = defaultdict(list)

    for cpu in cpus:
        normalized_name = normalize_match_name(cpu.name)
        if not normalized_name:
            continue

        key = (cpu.manufacturer.lower(), normalized_name)
        grouped[key].append(
            Candidate(name=cpu.name, hardware_id=cpu.id)
        )

    return {
        key: tuple(candidates)
        for key, candidates in grouped.items()
    }


def _classify_rows(
    rows: Iterable[dict[str, str]],
    lookup: dict[tuple[str, str], Hardware | None],
    candidates_by_key: dict[tuple[str, str], tuple[Candidate, ...]],
) -> AuditResult:
    records: list[AuditRecord] = []
    names = Counter()

    for row in rows:
        name = (row.get(DATASET_NAME_COLUMN) or "").strip()
        names[name] += 1
        manufacturer = detect_manufacturer(name)
        normalized_name = normalize_match_name(name)

        if not normalized_name:
            records.append(
                AuditRecord(
                    name=name,
                    manufacturer=manufacturer,
                    normalized_name=None,
                    status="UNMATCHED",
                    reason="CPU name is empty",
                )
            )
            continue

        key = (manufacturer.lower(), normalized_name)
        if key not in lookup:
            reason = f"no exact normalized key for manufacturer {manufacturer!r}"
            if manufacturer == "Unknown":
                reason = (
                    "manufacturer could not be determined from the CPU name; "
                    "no exact key available"
                )
            records.append(
                AuditRecord(
                    name=name,
                    manufacturer=manufacturer,
                    normalized_name=normalized_name,
                    status="UNMATCHED",
                    reason=reason,
                )
            )
            continue

        hardware = find_matching_cpu(name, manufacturer, lookup)
        if hardware is None:
            records.append(
                AuditRecord(
                    name=name,
                    manufacturer=manufacturer,
                    normalized_name=normalized_name,
                    status="AMBIGUOUS",
                    candidates=candidates_by_key.get(key, ()),
                    reason="normalized key maps to multiple Hardware records",
                )
            )
            continue

        records.append(
            AuditRecord(
                name=name,
                manufacturer=manufacturer,
                normalized_name=normalized_name,
                status="MATCHED",
                hardware=Candidate(
                    name=hardware.name,
                    hardware_id=hardware.id,
                ),
            )
        )

    duplicate_names = tuple(
        (name, count)
        for name, count in names.items()
        if count > 1
    )
    return AuditResult(
        rows=tuple(records),
        duplicate_names=duplicate_names,
    )


def audit_dataset(dataset_path: str | Path, session: Session) -> AuditResult:
    """Audit a Geekbench CPU CSV using the existing exact matcher."""
    rows = _read_rows(Path(dataset_path))
    cpus = session.scalars(
        select(Hardware).where(Hardware.type == "CPU")
    ).all()
    lookup = load_cpu_lookup(session)
    candidates_by_key = _candidate_groups(cpus)
    return _classify_rows(rows, lookup, candidates_by_key)


def _read_only_engine(database_path: Path) -> Engine:
    database_uri = f"file:{database_path.resolve().as_posix()}?mode=ro"

    def connect():
        return sqlite3.connect(database_uri, uri=True)

    return create_engine(
        "sqlite://",
        creator=connect,
        poolclass=NullPool,
    )


def _unique_examples(
    records: Iterable[AuditRecord],
    status: str,
    limit: int,
) -> list[AuditRecord]:
    examples: list[AuditRecord] = []
    seen: set[str] = set()

    for record in records:
        if record.status != status or record.name in seen:
            continue
        seen.add(record.name)
        examples.append(record)
        if len(examples) >= limit:
            break

    return examples


def _print_report(
    result: AuditResult,
    dataset_path: Path,
    database_path: Path,
) -> None:
    records = result.rows
    total = len(records)
    status_counts = Counter(record.status for record in records)
    matched = status_counts["MATCHED"]
    match_rate = matched / total * 100 if total else 0.0
    duplicate_extra_rows = sum(count - 1 for _, count in result.duplicate_names)

    print("Geekbench 7 CPU Match Audit")
    print(f"Dataset: {dataset_path}")
    print(f"Database: {database_path}")
    print("Database access: READ-ONLY (SQLite mode=ro)")
    print()

    print("Dataset:")
    print(f"TOTAL rows: {total}")
    print(f"UNIQUE CPU names: {len({record.name for record in records})}")
    print(
        "DUPLICATE CPU names: "
        f"{len(result.duplicate_names)} groups "
        f"({duplicate_extra_rows} duplicate rows)"
    )
    for name, count in result.duplicate_names:
        print(f"  {name} ({count} rows)")
    print()

    print("Matching:")
    print(f"MATCHED: {matched}")
    print(f"AMBIGUOUS: {status_counts['AMBIGUOUS']}")
    print(f"UNMATCHED: {status_counts['UNMATCHED']}")
    print(f"MATCH RATE: {match_rate:.2f}% ({matched}/{total} rows)")
    print()

    manufacturers = sorted({record.manufacturer for record in records})
    print("BREAKDOWN BY MANUFACTURER:")
    print("Manufacturer | Total | Matched | Ambiguous | Unmatched")
    for manufacturer in manufacturers:
        manufacturer_records = [
            record
            for record in records
            if record.manufacturer == manufacturer
        ]
        counts = Counter(record.status for record in manufacturer_records)
        print(
            f"{manufacturer} | {len(manufacturer_records)} | "
            f"{counts['MATCHED']} | {counts['AMBIGUOUS']} | "
            f"{counts['UNMATCHED']}"
        )
    print()

    matched_examples = _unique_examples(records, "MATCHED", 10)
    print(f"MATCHED EXAMPLES ({len(matched_examples)} unique names, up to 10):")
    for record in matched_examples:
        assert record.hardware is not None
        print(
            f"  {record.name} -> {record.hardware.name} "
            f"-> hardware_id={record.hardware.hardware_id}"
        )
    print()

    ambiguous_examples = _unique_examples(records, "AMBIGUOUS", 20)
    print(
        f"AMBIGUOUS EXAMPLES ({len(ambiguous_examples)} unique names, up to 20):"
    )
    for record in ambiguous_examples:
        candidates = "; ".join(
            f"{candidate.name} (hardware_id={candidate.hardware_id})"
            for candidate in record.candidates
        )
        print(
            f"  {record.name} -> {record.normalized_name} -> {candidates}"
        )
    print()

    unmatched_examples = _unique_examples(records, "UNMATCHED", 20)
    print(
        f"UNMATCHED EXAMPLES ({len(unmatched_examples)} unique names, up to 20):"
    )
    for record in unmatched_examples:
        print(f"  {record.name} -> {record.reason}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit exact Geekbench CPU matches without writing to SPECTRA."
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Geekbench CSV (default: {DEFAULT_DATASET_PATH})",
    )
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"SPECTRA SQLite database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    dataset_path = args.dataset.resolve()
    database_path = args.database.resolve()

    if not dataset_path.is_file():
        raise SystemExit(f"Dataset not found: {dataset_path}")
    if not database_path.is_file():
        raise SystemExit(f"Database not found: {database_path}")

    engine = _read_only_engine(database_path)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        with session_factory() as session:
            result = audit_dataset(dataset_path, session)
        _print_report(result, dataset_path, database_path)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
