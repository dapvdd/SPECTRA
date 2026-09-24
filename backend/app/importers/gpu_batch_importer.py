from pathlib import Path

from backend.app.database import SessionLocal
from backend.app.importers.gpu_csv import read_gpu_csv
from backend.app.importers.gpu_importer import (
    attach_external_identifiers,
    build_gpu_hardware,
    get_existing_gpu_keys,
    get_or_create_gpu_source,
    gpu_identity_key,
)
from backend.app.importers.gpu_normalizer import normalize_gpu_row
from backend.app.importers.gpu_validator import validate_gpu


def _run_import(
    session,
    path: Path,
    source_id: int | None,
) -> dict[str, int]:
    rows = read_gpu_csv(path)
    records = [
        normalize_gpu_row(row)
        for row in rows
    ]
    valid_records = [
        record
        for record in records
        if not validate_gpu(record)
    ]
    invalid_count = len(records) - len(valid_records)

    if source_id is None:
        source = get_or_create_gpu_source(session)
        actual_source_id = source.id
    else:
        actual_source_id = source_id

    existing = get_existing_gpu_keys(session)

    inserted = 0
    skipped_existing = 0

    for record in valid_records:
        key = gpu_identity_key(record)

        if key in existing:
            skipped_existing += 1
            continue

        hardware = build_gpu_hardware(record)

        if record.get("external_identifiers"):
            attach_external_identifiers(
                session,
                hardware,
                record.get("external_identifiers"),
                actual_source_id,
            )

        session.add(hardware)
        existing.add(key)
        inserted += 1

    return {
        "input": len(rows),
        "valid": len(valid_records),
        "invalid": invalid_count,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "failed": 0,
    }


def import_gpu_csv(
    path: Path,
    source_id: int | None = None,
    session=None,
) -> dict[str, int]:
    owned = None
    target = session

    if target is None:
        owned = SessionLocal()
        target = owned

    try:
        result = _run_import(target, path, source_id)
        target.commit()
        return result
    except BaseException:
        target.rollback()
        raise
    finally:
        if owned is not None:
            owned.close()