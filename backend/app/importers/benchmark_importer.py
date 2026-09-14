import csv
import math
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.importers.benchmark_matcher import (
    find_matching_cpu,
    load_cpu_lookup,
    normalize_match_name,
)
from backend.app.importers.benchmark_normalizer import detect_manufacturer
from backend.app.models import BenchmarkResult, Source


class BenchmarkImportError(ValueError):
    """Raised when a file is not a benchmark score dataset."""


REQUIRED_COLUMNS = {
    "cpuname",
    "benchmarkname",
    "score",
    "unit",
    "testtype",
}


def _column_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise BenchmarkImportError("benchmark score CSV has no header")

    columns = {
        field.strip().lower().replace("_", "").replace(" ", ""):
        field
        for field in fieldnames
        if field
    }

    missing = REQUIRED_COLUMNS - columns.keys()
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise BenchmarkImportError(
            "benchmark score CSV is missing required columns: "
            f"{missing_names}"
        )

    return columns


def _value(
    row: dict[str, str],
    columns: dict[str, str],
    name: str,
) -> str:
    field = columns.get(name)
    if field is None:
        return ""
    return (row.get(field) or "").strip()


def _parse_score(value: str) -> float | None:
    if not value:
        return None

    try:
        score = float(value)
    except ValueError:
        return None

    if not math.isfinite(score) or score <= 0:
        return None

    return score


def _parse_recorded_at(value: str) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_benchmark_score_row(
    row: dict[str, str],
    columns: dict[str, str],
) -> dict[str, object | None]:
    cpu_name = _value(row, columns, "cpuname")
    manufacturer = _value(row, columns, "manufacturer")

    if not manufacturer:
        manufacturer = detect_manufacturer(cpu_name)

    recorded_at_value = _value(row, columns, "recordedat")

    return {
        "cpu_name": cpu_name,
        "manufacturer": manufacturer,
        "benchmark_name": _value(row, columns, "benchmarkname"),
        "score": _parse_score(_value(row, columns, "score")),
        "unit": _value(row, columns, "unit"),
        "test_type": _value(row, columns, "testtype"),
        "recorded_at": _parse_recorded_at(recorded_at_value),
        "recorded_at_value": recorded_at_value,
    }


def validate_benchmark_score_row(
    data: dict[str, object | None],
) -> list[str]:
    errors: list[str] = []

    for field in (
        "cpu_name",
        "manufacturer",
        "benchmark_name",
        "unit",
        "test_type",
    ):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{field} is required")

    score = data.get("score")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not math.isfinite(score)
        or score <= 0
    ):
        errors.append("score must be a positive finite number")

    for field, limit in (
        ("benchmark_name", 100),
        ("unit", 50),
        ("test_type", 50),
    ):
        value = data.get(field)
        if isinstance(value, str) and len(value) > limit:
            errors.append(f"{field} exceeds {limit} characters")

    recorded_at_value = data.get("recorded_at_value")
    if recorded_at_value and data.get("recorded_at") is None:
        errors.append("recorded_at must be an ISO datetime")

    return errors


def _duplicate_key(
    hardware_id: int,
    data: dict[str, object | None],
    source_id: int,
) -> tuple[object, ...]:
    return (
        hardware_id,
        data["benchmark_name"],
        data["score"],
        data["unit"],
        data["test_type"],
        source_id,
        data["recorded_at"],
    )


def _benchmark_exists(
    session,
    hardware_id: int,
    data: dict[str, object | None],
    source_id: int,
) -> bool:
    conditions = [
        BenchmarkResult.hardware_id == hardware_id,
        BenchmarkResult.benchmark_name == data["benchmark_name"],
        BenchmarkResult.score == data["score"],
        BenchmarkResult.unit == data["unit"],
        BenchmarkResult.test_type == data["test_type"],
        BenchmarkResult.source_id == source_id,
    ]

    recorded_at = data["recorded_at"]
    if recorded_at is None:
        conditions.append(BenchmarkResult.recorded_at.is_(None))
    else:
        conditions.append(BenchmarkResult.recorded_at == recorded_at)

    return session.scalar(
        select(BenchmarkResult.id).where(*conditions)
    ) is not None


def import_benchmark_scores(
    csv_path: str | Path,
    source_name: str,
    source_url: str,
) -> dict[str, int]:
    """Import validated benchmark scores without creating hardware records.

    The CSV must contain CpuName, BenchmarkName, Score, Unit, and TestType.
    CPU catalog files such as benchmark-cpus.csv therefore fail before any
    database write is attempted.
    """
    if not source_name.strip() or not source_url.strip():
        raise ValueError("source_name and source_url are required")

    path = Path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = _column_map(reader.fieldnames)
        rows = list(reader)

    summary = {
        "total": len(rows),
        "imported": 0,
        "skipped": 0,
        "invalid": 0,
        "unmatched": 0,
        "ambiguous": 0,
    }

    normalized_rows = [
        normalize_benchmark_score_row(row, columns)
        for row in rows
    ]

    for data in normalized_rows:
        if validate_benchmark_score_row(data):
            summary["invalid"] += 1

    if summary["invalid"] == summary["total"]:
        return summary

    with SessionLocal() as session:
        lookup = load_cpu_lookup(session)
        source = None
        seen: set[tuple[object, ...]] = set()

        for data in normalized_rows:
            if validate_benchmark_score_row(data):
                continue

            cpu_name = str(data["cpu_name"])
            manufacturer = str(data["manufacturer"])
            normalized_name = normalize_match_name(cpu_name)
            lookup_key = (
                manufacturer.lower(),
                normalized_name,
            )

            if lookup_key not in lookup:
                summary["unmatched"] += 1
                continue

            hardware = find_matching_cpu(
                cpu_name,
                manufacturer,
                lookup,
            )
            if hardware is None:
                summary["ambiguous"] += 1
                continue

            if source is None:
                source = session.scalar(
                    select(Source).where(
                        Source.name == source_name,
                        Source.url == source_url,
                    )
                )
                if source is None:
                    source = Source(
                        name=source_name,
                        url=source_url,
                    )
                    session.add(source)
                    session.flush()

            duplicate_key = _duplicate_key(
                hardware.id,
                data,
                source.id,
            )
            if (
                duplicate_key in seen
                or _benchmark_exists(
                    session,
                    hardware.id,
                    data,
                    source.id,
                )
            ):
                summary["skipped"] += 1
                seen.add(duplicate_key)
                continue

            session.add(
                BenchmarkResult(
                    hardware_id=hardware.id,
                    benchmark_name=data["benchmark_name"],
                    score=data["score"],
                    unit=data["unit"],
                    test_type=data["test_type"],
                    source_id=source.id,
                    recorded_at=data["recorded_at"],
                )
            )
            seen.add(duplicate_key)
            summary["imported"] += 1

        session.commit()

    return summary
