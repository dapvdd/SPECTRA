"""Idempotent, additive Batch 017 upgrade of the ``hardware`` table.

Batch 017 records the product ``segment`` on the ``hardware`` table so products
that share a marketing name across form factors (for example a "GTX 1650"
desktop vs mobile part) can be told apart instead of conflating laptop and
desktop performance. The column is nullable and additive: it never rewrites
existing rows and an absent value is reported honestly as unknown.

Run with ``--dry-run`` to report the state without writing anything, and with
``--database <path>`` to target a disposable copy before the live database.
"""

import argparse
import sqlite3
from pathlib import Path

from backend.app.database import engine
from backend.app.models import Hardware

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "spectra.db"

SEGMENT_VALUES = (
    "desktop",
    "mobile",
    "server",
    "workstation",
    "embedded",
    "integrated",
)


def hardware_exists(path: Path | None = None) -> bool:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name = 'hardware'",
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def existing_columns(path: Path | None = None) -> list[str]:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        return [
            row[1]
            for row in connection.execute("PRAGMA table_info(hardware)").fetchall()
        ]
    finally:
        connection.close()


def segment_column_installed(path: Path | None = None) -> bool:
    return "segment" in existing_columns(path)


def upgrade_hardware(path: Path | None = None) -> bool:
    """Add the ``segment`` column if missing; return True when added."""
    target = path or DEFAULT_DB
    if not hardware_exists(target):
        return False
    if segment_column_installed(target):
        return False

    connection = sqlite3.connect(target)
    try:
        connection.execute(
            "ALTER TABLE hardware ADD COLUMN segment VARCHAR(50)"
        )
        connection.commit()
    finally:
        connection.close()

    if not segment_column_installed(target):
        raise RuntimeError("verification FAILED: segment column missing after upgrade")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report state without writing anything.",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Target database path (default: data/spectra.db).",
    )
    arguments = parser.parse_args()

    target = Path(arguments.database) if arguments.database else DEFAULT_DB
    exists = hardware_exists(target)
    installed = segment_column_installed(target)
    print(f"hardware exists: {exists}")
    print(f"segment column installed: {installed}")

    if arguments.dry_run:
        print("dry run: no changes written")
        return 0

    if not exists:
        print(f"table not found at: {target}")
        return 1

    if not installed:
        added = upgrade_hardware(target)
        print(f"segment column added: {added}")
    else:
        print("column already present; no changes written")

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


segments = SEGMENT_VALUES  # exposed for tests/backfill scripts
