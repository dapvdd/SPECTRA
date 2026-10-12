"""Idempotent, additive Batch 015 upgrade of the ``sources`` table.

Batch 015 records licence, publisher and attribution metadata on the source
registry itself. There is no migration framework in this project, so the
upgrade is applied to an existing database with idempotent
``ALTER TABLE ... ADD COLUMN`` statements while ``Base.metadata.create_all``
keeps fresh databases in sync with the ORM model.

Design constraints:

- Every added column is nullable, so no existing row is rewritten, no source id
  is remapped, and no unrelated column is touched. This is a purely additive
  change; a database that already has the columns is left byte-for-byte intact.
- The column is plain text (no SQL ``CHECK``) so the upgrade is a single
  ``ALTER TABLE`` per column and never requires rebuilding ``sources`` — which
  would risk the foreign keys that reference it.
- Running the script again is a no-op.

Run with ``--dry-run`` to report the state without writing anything, and with
``--database <path>`` to target a disposable copy before the live database.
"""

import argparse
import sqlite3
from pathlib import Path

from backend.app.database import engine
from backend.app.models import Source

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "spectra.db"

# (column name, SQLite column definition) added to ``sources`` in Batch 015.
_ADDED_COLUMNS = (
    ("publisher", "VARCHAR(200)"),
    ("description", "TEXT"),
    ("license_name", "VARCHAR(100)"),
    ("license_url", "VARCHAR(500)"),
    ("license_status", "VARCHAR(20)"),
    ("terms_notes", "TEXT"),
    ("attribution", "TEXT"),
    ("retrieved_on", "DATE"),
)


def existing_columns(path: Path | None = None) -> list[str]:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        return [
            row[1]
            for row in connection.execute("PRAGMA table_info(sources)").fetchall()
        ]
    finally:
        connection.close()


def sources_exists(path: Path | None = None) -> bool:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name = 'sources'",
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def missing_columns(path: Path | None = None) -> list[str]:
    present = set(existing_columns(path))
    return [name for name, _ in _ADDED_COLUMNS if name not in present]


def upgrade_sources(path: Path | None = None) -> list[str]:
    """Add any missing Batch 015 columns; return the list of columns added."""
    target = path or DEFAULT_DB
    if not sources_exists(target):
        return []

    added: list[str] = []
    connection = sqlite3.connect(target)
    try:
        present = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(sources)"
            ).fetchall()
        }
        for name, definition in _ADDED_COLUMNS:
            if name in present:
                continue
            connection.execute(
                f"ALTER TABLE sources ADD COLUMN {name} {definition}"
            )
            added.append(name)
        connection.commit()
    finally:
        connection.close()

    remaining = missing_columns(target)
    if remaining:
        raise RuntimeError(
            f"verification FAILED: sources columns still missing: {remaining}"
        )
    return added


def create_fresh_sources(target: Path | None = None) -> bool:
    """Create the ``sources`` table (with Batch 015 columns) if absent."""
    if target is None:
        Source.__table__.create(bind=engine, checkfirst=True)
        return True
    from sqlalchemy import create_engine

    target_engine = create_engine(
        "sqlite:///" + str(target).replace("\\", "/")
    )
    try:
        Source.__table__.create(bind=target_engine, checkfirst=True)
    finally:
        target_engine.dispose()
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
    exists = sources_exists(target)
    missing = (
        missing_columns(target)
        if exists
        else [name for name, _ in _ADDED_COLUMNS]
    )
    print(f"sources exists: {exists}")
    print(f"missing Batch 015 columns: {missing}")

    if arguments.dry_run:
        print("dry run: no changes written")
        return 0

    if not exists:
        create_fresh_sources(
            Path(arguments.database) if arguments.database else None
        )
        print(f"table created for: {target}")
    else:
        added = upgrade_sources(target)
        print(f"columns added: {added}")

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
