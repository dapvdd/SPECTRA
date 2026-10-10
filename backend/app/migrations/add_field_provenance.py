"""Idempotent creation/upgrade of the ``field_provenance`` provenance table.

Without an established migration framework, schema additions are applied on
existing databases with idempotent SQL and ``Base.metadata.create_all`` keeps
fresh databases in sync.

Two paths:

- Fresh database: ``create_field_provenance`` creates the table (via the model)
  if it does not exist.
- Existing table without the Batch 010 ``benchmark_result_id`` column:
  ``upgrade_field_provenance`` rebuilds the table with the extended schema and
  the partial unique indexes that separately guard specification provenance
  (``benchmark_result_id IS NULL``) and benchmark provenance
  (``benchmark_result_id IS NOT NULL``). The rebuild is a single transaction
  that copies all existing rows unchanged; running it again is a no-op.

Run with ``--dry-run`` to report the state without writing anything.
"""

import argparse
import sqlite3
from pathlib import Path

from backend.app.database import engine
from backend.app.models import FieldProvenance

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "spectra.db"

_COLUMNS = [
    "id", "hardware_id", "source_id", "table_name", "field_name",
    "evidenced_value", "source_url", "license_name", "license_notes",
    "attribution", "access_date", "confidence", "evidence_status",
    "source_reference", "match_method", "batch_no", "notes", "recorded_at",
    "benchmark_result_id",
]

_NEW_TABLE_DDL = """
CREATE TABLE field_provenance_new (
    id INTEGER PRIMARY KEY,
    hardware_id INTEGER NOT NULL REFERENCES hardware (id),
    source_id INTEGER NOT NULL REFERENCES sources (id),
    table_name VARCHAR(50) NOT NULL
        CHECK (table_name IN ('hardware', 'cpu_specifications',
                              'gpu_specifications', 'benchmark_results')),
    field_name VARCHAR(50) NOT NULL,
    evidenced_value VARCHAR(200) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    license_name VARCHAR(100),
    license_notes TEXT,
    attribution TEXT,
    access_date DATE,
    confidence VARCHAR(20),
    evidence_status VARCHAR(20) NOT NULL
        CHECK (evidence_status IN ('verified', 'uncertain',
                                   'excluded', 'unmatched')),
    source_reference VARCHAR(200),
    match_method VARCHAR(100),
    batch_no INTEGER NOT NULL,
    notes TEXT,
    recorded_at DATETIME NOT NULL,
    benchmark_result_id INTEGER REFERENCES benchmark_results (id),
    CHECK (
        (benchmark_result_id IS NULL AND table_name != 'benchmark_results')
        OR (benchmark_result_id IS NOT NULL AND table_name = 'benchmark_results')
    )
)
"""

_INDEXES = [
    (
        "CREATE UNIQUE INDEX uq_field_provenance_identity ON field_provenance "
        "(hardware_id, table_name, field_name, source_id, evidenced_value, "
        "evidence_status) WHERE benchmark_result_id IS NULL"
    ),
    (
        "CREATE UNIQUE INDEX uq_field_provenance_benchmark_identity ON "
        "field_provenance (benchmark_result_id, field_name, source_id, "
        "evidenced_value, evidence_status) WHERE benchmark_result_id IS NOT NULL"
    ),
    (
        "CREATE INDEX ix_field_provenance_lookup ON field_provenance "
        "(hardware_id, table_name, field_name)"
    ),
    (
        "CREATE INDEX ix_field_provenance_source_id ON field_provenance "
        "(source_id)"
    ),
    (
        "CREATE INDEX ix_field_provenance_evidence_status ON field_provenance "
        "(evidence_status)"
    ),
    (
        "CREATE INDEX ix_field_provenance_benchmark_result_id ON "
        "field_provenance (benchmark_result_id)"
    ),
]


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


def has_benchmark_result_id(path: Path | None = None) -> bool:
    target = path or DEFAULT_DB
    connection = sqlite3.connect(target)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(field_provenance)"
            ).fetchall()
        }
        return "benchmark_result_id" in columns
    finally:
        connection.close()


def create_field_provenance() -> bool:
    """Create the table on the configured engine; return True if created."""
    FieldProvenance.__table__.create(bind=engine, checkfirst=True)
    return True


def upgrade_field_provenance(path: Path | None = None) -> bool:
    """Rebuild an existing ``field_provenance`` table to the Batch 010 schema.

    Returns True when a rebuild was performed, False when already current.
    """
    target = path or DEFAULT_DB
    if not field_provenance_exists(target):
        return False
    if has_benchmark_result_id(target):
        return False

    connection = sqlite3.connect(target)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN")
        connection.execute(_NEW_TABLE_DDL)
        connection.execute(
            f"INSERT INTO field_provenance_new ({', '.join(_COLUMNS)}) "
            f"SELECT {', '.join(_COLUMNS[:-1])}, NULL FROM field_provenance"
        )
        connection.execute("DROP TABLE field_provenance")
        connection.execute(
            "ALTER TABLE field_provenance_new RENAME TO field_provenance"
        )
        for statement in _INDEXES:
            connection.execute(statement)
        connection.execute("COMMIT")
        connection.execute("PRAGMA foreign_keys=ON")
    except BaseException:
        connection.execute("ROLLBACK")
        connection.execute("PRAGMA foreign_keys=ON")
        raise
    finally:
        connection.close()

    if not has_benchmark_result_id(target):
        raise RuntimeError("verification FAILED: benchmark_result_id missing after rebuild")
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
    exists = field_provenance_exists(target)
    installed = has_benchmark_result_id(target)
    print(f"field_provenance exists: {exists}")
    print(f"benchmark_result_id installed: {installed}")

    if arguments.dry_run:
        print("dry run: no changes written")
        return 0

    if not exists:
        create_field_provenance()
        print(f"table created on: {engine.url}")
    elif not installed:
        upgraded = upgrade_field_provenance(target)
        print(f"table upgraded (rebuild): {upgraded}")
    else:
        print("table already current; no changes written")

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())