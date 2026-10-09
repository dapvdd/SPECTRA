"""Idempotent creation of the ``field_provenance`` provenance table.

Without an established migration framework, schema additions are applied
with idempotent ``CREATE TABLE IF NOT EXISTS`` on existing databases while
``Base.metadata.create_all`` keeps fresh databases in sync. This migration
follows that pattern: it only creates the new table and never touches any
existing table or row, so running it again is a no-op.

Run with ``--dry-run`` to report whether the table exists without creating it.
"""

import argparse
import sqlite3
from pathlib import Path

from backend.app.database import engine
from backend.app.models import FieldProvenance

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "spectra.db"


def field_provenance_exists(path: Path | None = None) -> bool:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name = ?",
            ("field_provenance",),
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def create_field_provenance() -> bool:
    """Create the table on the configured engine; return True if created."""
    FieldProvenance.__table__.create(bind=engine, checkfirst=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report whether the table exists without creating it.",
    )
    arguments = parser.parse_args()

    exists = field_provenance_exists()
    print(f"field_provenance exists: {exists}")

    if arguments.dry_run:
        print("dry run: no changes written")
        return 0

    if exists:
        print("table already present; no changes written")
        return 0

    create_field_provenance()
    print(f"table created on: {engine.url}")

    if not field_provenance_exists():
        print("verification FAILED: table not found after creation")
        return 1

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())