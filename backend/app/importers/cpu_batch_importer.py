from pathlib import Path

from backend.app.importers.cpu_csv import read_cpu_csv
from backend.app.importers.cpu_importer import import_cpu
from backend.app.importers.cpu_normalizer import (
    normalize_amd_row,
    normalize_intel_row,
)
from backend.app.importers.cpu_validator import validate_cpu


def import_cpu_csv(
    path: Path,
    manufacturer: str,
    source_id: int,
) -> dict[str, int]:

    rows = read_cpu_csv(path)

    imported = 0
    skipped = 0
    invalid = 0

    for row in rows:
        if manufacturer == "AMD":
            data = normalize_amd_row(row)
        elif manufacturer == "Intel":
            data = normalize_intel_row(row)
        else:
            invalid += 1
            continue

        errors = validate_cpu(data)

        if errors:
            invalid += 1
            continue

        result = import_cpu(data, source_id)

        if result:
            imported += 1
        else:
            skipped += 1

    return {
        "total": len(rows),
        "imported": imported,
        "skipped": skipped,
        "invalid": invalid,
    }