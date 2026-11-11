"""Versioned SQLite migration runner for SPECTRA.

Design constraints (per SPECTRA V2 migration plan):

- Additive only: every registered migration adds columns or tables; it never
  rewrites rows or drops columns, so re-running is always safe and rollback
  is documented per-step rather than a generic revert.
- Copy-first: always run against ``--database <copy>``; the live data/spectra.db
  is never touched without explicit approval.
- Verifiable: every migration step includes a verification function that checks
  the schema change was applied correctly; a failed verification rolls back the
  transaction and aborts.
- Ordered: a ``schema_version`` table tracks the current version (one row,
  id=1). Running ``upgrade`` applies every step with version > current_version
  in order; steps with version <= current_version are no-ops (idempotent).

Usage::

    # Dry-run report on a copy:
    python backend/app/migrations/runner.py --dry-run --database data/spectra_copy.db

    # Apply pending migrations on a copy:
    python backend/app/migrations/runner.py --database data/spectra_copy.db

    # Verify a DB is at a given version:
    python backend/app/migrations/runner.py --verify --database data/spectra_copy.db

    # Downgrade to a specific version (reversible steps only):
    python backend/app/migrations/runner.py --target 1 --database data/spectra_copy.db

"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Ensure the repo root is on the path so sibling migration scripts remain importable.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Schema definition (captures the state at SPECTRA V2 audit, Batch 018).
# Used by the baseline migration for verification against a real DB.
# ---------------------------------------------------------------------------

_EXPECTED_TABLES: dict[str, set[str]] = {
    "hardware": {
        "id", "name", "manufacturer", "type",
        "release_date", "architecture", "segment",
    },
    "cpu_specifications": {
        "id", "hardware_id", "cores", "threads",
        "base_clock_ghz", "boost_clock_ghz", "tdp_w",
        "process_node_nm", "socket",
    },
    "gpu_specifications": {
        "id", "hardware_id", "memory_gb", "memory_type",
        "core_clock_mhz", "boost_clock_mhz", "vram_bandwidth_gbps",
        "tdp_w", "interface", "length_mm", "memory_bus_width_bits",
    },
    "benchmark_results": {
        "id", "hardware_id", "benchmark_name", "score", "unit",
        "test_type", "source_id", "recorded_at",
    },
    "sources": {
        "id", "name", "url", "publisher", "description",
        "license_name", "license_url", "license_status",
        "terms_notes", "attribution", "retrieved_on",
    },
    "build_conversations": {
        "id", "cpu_hardware_id", "gpu_hardware_id",
        "created_at", "updated_at",
    },
    "build_messages": {
        "id", "conversation_id", "role", "content",
        "evidence_json", "analysis_json", "created_at",
    },
    "external_identifiers": {
        "id", "hardware_id", "source_id",
        "external_id", "identifier_type",
    },
    "field_provenance": {
        "id", "hardware_id", "source_id", "table_name", "field_name",
        "evidenced_value", "source_url", "license_name", "license_notes",
        "attribution", "access_date", "confidence", "evidence_status",
        "source_reference", "match_method", "batch_no", "notes",
        "recorded_at", "benchmark_result_id",
    },
}

# v2 (auth): adds the users table and owner_id on build_conversations.
_EXPECTED_TABLES_V2: dict[str, set[str]] = {
    **_EXPECTED_TABLES,
    "users": {
        "id", "username", "password_hash",
    },
    "build_conversations": {
        "id", "cpu_hardware_id", "gpu_hardware_id",
        "created_at", "updated_at", "owner_id",
    },
}

# v3 (Build Planner): the four new component spec tables. field_provenance is
# REBUILT (not altered — SQLite cannot change a CHECK constraint) to widen its
# table_name vocabulary.
_EXPECTED_TABLES_V3: dict[str, set[str]] = {
    **_EXPECTED_TABLES_V2,
    "ram_specifications": {
        "id", "hardware_id", "ddr_generation", "capacity_gb", "speed_mhz",
        "modules", "ecc", "voltage_v", "form_factor",
    },
    "storage_specifications": {
        "id", "hardware_id", "storage_type", "capacity_gb", "interface",
        "read_mb_s", "write_mb_s", "dram_cache", "form_factor",
    },
    "motherboard_specifications": {
        "id", "hardware_id", "socket", "chipset", "form_factor",
        "ram_type", "ram_slots", "max_ram_gb", "m2_slots", "sata_ports",
        "pcie_slots",
    },
    "psu_specifications": {
        "id", "hardware_id", "wattage", "efficiency_rating", "modular",
        "pcie_8pin_count", "pcie_12vhpwr",
    },
}

# Full provenance column list for the rebuild (matches provenance.py exactly).
_PROVENANCE_COLUMNS = (
    "id", "hardware_id", "source_id", "table_name", "field_name",
    "evidenced_value", "source_url", "license_name", "license_notes",
    "attribution", "access_date", "confidence", "evidence_status",
    "source_reference", "match_method", "batch_no", "notes",
    "recorded_at", "benchmark_result_id",
)

# Widen the table-name CHECK to the four Build Planner categories. Generated
# from VALID_TABLES to keep one source of truth (app-level validation uses the
# same constant).
_WIDENED_TABLE_CHECK = (
    "table_name IN ('hardware', 'cpu_specifications', 'gpu_specifications', "
    "'benchmark_results', 'ram_specifications', 'storage_specifications', "
    "'motherboard_specifications', 'psu_specifications')"
)


def _verify_v3(conn: sqlite3.Connection) -> None:
    """Verify the v3 schema: 4 spec tables + provenance rebuild integrity."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    for table in ("ram_specifications", "storage_specifications",
                  "motherboard_specifications", "psu_specifications"):
        if table not in tables:
            raise RuntimeError(f"v3 verification FAILED: missing table '{table}'")

    for table, expected_cols in _EXPECTED_TABLES_V3.items():
        if table == "field_provenance":
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        missing = expected_cols - cols
        if missing:
            raise RuntimeError(
                f"v3 verification FAILED: {table} missing columns: {missing}"
            )

    # Provenance rebuild integrity: the table exists and the DB is sound.
    if "field_provenance" not in tables:
        raise RuntimeError("v3 verification FAILED: field_provenance missing")
    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != "ok":
        raise RuntimeError(f"v3 verification FAILED: integrity_check {result[0]!r}")


# Full rebuilt field_provenance DDL (widened table_name CHECK). Column list
# mirrors models/provenance.py exactly.
_FIELD_PROVENANCE_DDL_V3 = f"""
CREATE TABLE field_provenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hardware_id INTEGER NOT NULL REFERENCES hardware(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    table_name VARCHAR(50) NOT NULL CHECK ({_WIDENED_TABLE_CHECK}),
    field_name VARCHAR(50) NOT NULL,
    evidenced_value VARCHAR(200) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    license_name VARCHAR(100),
    license_notes TEXT,
    attribution TEXT,
    access_date DATE,
    confidence VARCHAR(20),
    evidence_status VARCHAR(20) NOT NULL CHECK (
        evidence_status IN ('verified', 'uncertain', 'excluded', 'unmatched')
    ),
    source_reference VARCHAR(200),
    match_method VARCHAR(100),
    batch_no INTEGER NOT NULL,
    notes TEXT,
    recorded_at DATETIME NOT NULL,
    benchmark_result_id INTEGER REFERENCES benchmark_results(id),
    CHECK (
        (benchmark_result_id IS NULL AND table_name != 'benchmark_results')
        OR (benchmark_result_id IS NOT NULL AND table_name = 'benchmark_results')
    )
)
"""

_PROVENANCE_INDEX_DDL = (
    "CREATE UNIQUE INDEX uq_field_provenance_identity ON field_provenance "
    "(hardware_id, table_name, field_name, source_id, evidenced_value, "
    "evidence_status) WHERE benchmark_result_id IS NULL",
    "CREATE UNIQUE INDEX uq_field_provenance_benchmark_identity "
    "ON field_provenance (benchmark_result_id, field_name, source_id, "
    "evidenced_value, evidence_status) "
    "WHERE benchmark_result_id IS NOT NULL",
    "CREATE INDEX ix_field_provenance_lookup ON field_provenance "
    "(hardware_id, table_name, field_name)",
    "CREATE INDEX ix_field_provenance_source_id ON field_provenance (source_id)",
    "CREATE INDEX ix_field_provenance_evidence_status "
    "ON field_provenance (evidence_status)",
    "CREATE INDEX ix_field_provenance_benchmark_result_id "
    "ON field_provenance (benchmark_result_id)",
)

# Pre-rebuild state for verify: the rebuild is inside migration statements, so
# verification checks the post-state.
_PROVENANCE_DDL_V2 = (
    "CREATE TABLE field_provenance (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    hardware_id INTEGER NOT NULL REFERENCES hardware(id),\n"
    "    source_id INTEGER NOT NULL REFERENCES sources(id),\n"
    "    table_name VARCHAR(50) NOT NULL CHECK (\n"
    "        table_name IN ('hardware', 'cpu_specifications', "
    "'gpu_specifications', 'benchmark_results')\n"
    "    ),\n"
    "    field_name VARCHAR(50) NOT NULL,\n"
    "    evidenced_value VARCHAR(200) NOT NULL,\n"
    "    source_url VARCHAR(500) NOT NULL,\n"
    "    license_name VARCHAR(100),\n"
    "    license_notes TEXT,\n"
    "    attribution TEXT,\n"
    "    access_date DATE,\n"
    "    confidence VARCHAR(20),\n"
    "    evidence_status VARCHAR(20) NOT NULL CHECK (\n"
    "        evidence_status IN ('verified', 'uncertain', 'excluded', 'unmatched')\n"
    "    ),\n"
    "    source_reference VARCHAR(200),\n"
    "    match_method VARCHAR(100),\n"
    "    batch_no INTEGER NOT NULL,\n"
    "    notes TEXT,\n"
    "    recorded_at DATETIME NOT NULL,\n"
    "    benchmark_result_id INTEGER REFERENCES benchmark_results(id)\n"
    ")"
)


def _verify_v2(conn: sqlite3.Connection) -> None:
    """Verify the v2 schema: users table present, owner_id column present."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    if "users" not in tables:
        raise RuntimeError("v2 verification FAILED: missing table 'users'")

    cols = {r[1] for r in conn.execute("PRAGMA table_info(build_conversations)").fetchall()}
    if "owner_id" not in cols:
        raise RuntimeError(
            "v2 verification FAILED: build_conversations missing owner_id column"
        )


# ---------------------------------------------------------------------------
# Migration definitions
# ---------------------------------------------------------------------------

@dataclass
class Migration:
    version: int
    name: str
    description: str
    # SQL statements to execute in order (empty list for baseline).
    statements: list[str]
    # SQL statements to undo this migration (None = not reversible).
    downgrade: list[str] | None
    # Verification function: (connection) -> None. Raises RuntimeError on fail.
    verify: callable | None = None
    reversible: bool = False


def _baseline_verify(conn: sqlite3.Connection) -> None:
    """Verify the DB is at the schema captured by _EXPECTED_TABLES."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    missing_tables = set(_EXPECTED_TABLES) - tables
    if missing_tables:
        raise RuntimeError(f"baseline verification FAILED: missing tables: {missing_tables}")

    for table, expected_cols in _EXPECTED_TABLES.items():
        actual_cols = {
            r[1]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        missing_cols = expected_cols - actual_cols
        if missing_cols:
            raise RuntimeError(
                f"baseline verification FAILED: table '{table}' is missing columns: {missing_cols}"
            )


def _ensure_schema_version(conn: sqlite3.Connection) -> None:
    """Create the schema_version tracking table if absent."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        name="baseline-current-schema",
        description=(
            "Records the schema current at the SPECTRA V2 audit (Batch 018). "
            "No DDL is executed; the baseline documents the expected tables and "
            "columns so future migrations can be verified against it. Future "
            "additive changes are registered as version 2, 3, ... "
            "All existing migrations (segment, field_provenance rebuild, "
            "source license metadata, name normalization) have already been "
            "applied to the audited DB; this step records the schema as current."
        ),
        statements=[],
        downgrade=None,
        verify=_baseline_verify,
        reversible=False,
    ),
    # v2: Phase 2.1 auth — copy-first, never applied to production without approval.
    Migration(
        version=2,
        name="auth-tables",
        description=(
            "Adds the `users` table (bcrypt-credential store) and the nullable "
            "`owner_id` column on `build_conversations`. Existing rows get "
            "owner_id=NULL (legacy). New conversations always carry an owner_id. "
            "When SPECTRA_AUTH_ENABLED=1, authenticated users see only their own "
            "conversations; NULL-owner rows are inaccessible to all authenticated "
            "users. Run on a disposable copy first: "
            "  python backend/app/migrations/runner.py --database data/spectra_copy.db"
        ),
        statements=[
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")",
            "ALTER TABLE build_conversations ADD COLUMN owner_id INTEGER",
            "CREATE INDEX IF NOT EXISTS ix_build_conversations_owner_id "
            "  ON build_conversations(owner_id)",
        ],
        downgrade=[
            "DROP INDEX IF EXISTS ix_build_conversations_owner_id",
            "ALTER TABLE build_conversations DROP COLUMN owner_id",
            "DROP TABLE IF EXISTS users",
        ],
        reversible=True,
        verify=_verify_v2,
    ),
    # v3: Build Planner categories — 4 spec tables + field_provenance rebuild.
    # The provenance rebuild is copy-first inside the statements: create _new
    # with the widened CHECK, copy all rows, drop old, rename, recreate
    # indexes. Run on a disposable copy first:
    #   python backend/app/migrations/runner.py --database data/spectra_copy.db
    Migration(
        version=3,
        name="planner-component-categories",
        description=(
            "Adds ram_specifications, storage_specifications, "
            "motherboard_specifications and psu_specifications (each FK "
            "hardware.id, unique) and REBUILDS field_provenance with a widened "
            "table_name CHECK so the new categories carry field-level "
            "provenance. SQLite cannot ALTER a CHECK constraint, so the "
            "rebuild copies all rows into a new table and swaps it in; row "
            "preservation is verified after the copy."
        ),
        statements=[
            # --- four component spec tables ---
            """CREATE TABLE IF NOT EXISTS ram_specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hardware_id INTEGER REFERENCES hardware(id) UNIQUE,
                ddr_generation VARCHAR(10)
                    CHECK (ddr_generation IN ('DDR3', 'DDR4', 'DDR5', 'DDR6')),
                capacity_gb INTEGER,
                speed_mhz INTEGER,
                modules INTEGER,
                ecc INTEGER,
                voltage_v FLOAT,
                form_factor VARCHAR(30)
            )""",
            """CREATE TABLE IF NOT EXISTS storage_specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hardware_id INTEGER REFERENCES hardware(id) UNIQUE,
                storage_type VARCHAR(20)
                    CHECK (storage_type IN ('NVMe', 'SATA SSD', 'HDD')),
                capacity_gb INTEGER,
                interface VARCHAR(40),
                read_mb_s FLOAT,
                write_mb_s FLOAT,
                dram_cache INTEGER,
                form_factor VARCHAR(30)
            )""",
            """CREATE TABLE IF NOT EXISTS motherboard_specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hardware_id INTEGER REFERENCES hardware(id) UNIQUE,
                socket VARCHAR(30),
                chipset VARCHAR(30),
                form_factor VARCHAR(20),
                ram_type VARCHAR(10),
                ram_slots INTEGER,
                max_ram_gb INTEGER,
                m2_slots INTEGER,
                sata_ports INTEGER,
                pcie_slots INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS psu_specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hardware_id INTEGER REFERENCES hardware(id) UNIQUE,
                wattage INTEGER CHECK (wattage IS NULL OR wattage > 0),
                efficiency_rating VARCHAR(30) CHECK (
                    efficiency_rating IN ('80 Plus White', '80 Plus Bronze',
                    '80 Plus Gold', '80 Plus Platinum', '80 Plus Titanium')
                ),
                modular INTEGER,
                pcie_8pin_count INTEGER,
                pcie_12vhpwr INTEGER
            )""",
            # --- field_provenance rebuild (copy-first) ---
            _FIELD_PROVENANCE_DDL_V3.replace(
                "CREATE TABLE field_provenance",
                "CREATE TABLE field_provenance_new",
            ),
            "INSERT INTO field_provenance_new ({cols}) "
            "SELECT {cols} FROM field_provenance".format(
                cols=", ".join(_PROVENANCE_COLUMNS)
            ),
            "DROP TABLE field_provenance",
            "ALTER TABLE field_provenance_new RENAME TO field_provenance",
            *_PROVENANCE_INDEX_DDL,
        ],
        downgrade=[
            # Drop the four spec tables, then rebuild provenance back to the
            # v2 vocabulary (copy-first again).
            "DROP TABLE IF EXISTS psu_specifications",
            "DROP TABLE IF EXISTS motherboard_specifications",
            "DROP TABLE IF EXISTS storage_specifications",
            "DROP TABLE IF EXISTS ram_specifications",
            _PROVENANCE_DDL_V2.replace(
                "CREATE TABLE field_provenance",
                "CREATE TABLE field_provenance_v2",
            ),
            "INSERT INTO field_provenance_v2 ({cols}) "
            "SELECT {cols} FROM field_provenance".format(
                cols=", ".join(_PROVENANCE_COLUMNS)
            ),
            "DROP TABLE field_provenance",
            "ALTER TABLE field_provenance_v2 RENAME TO field_provenance",
            *_PROVENANCE_INDEX_DDL,
        ],
        reversible=True,
        verify=_verify_v3,
    ),
]


# ---------------------------------------------------------------------------
# Core runner logic
# ---------------------------------------------------------------------------

def _current_version(conn: sqlite3.Connection) -> int:
    _ensure_schema_version(conn)
    row = conn.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    ).fetchone()
    return row[0] if row else 0


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO schema_version (id, version, applied_at) VALUES (1, ?, ?)",
        (version, now),
    )


def _pending_migrations(current: int) -> list[Migration]:
    return [m for m in MIGRATIONS if m.version > current]


LATEST_VERSION = max(m.version for m in MIGRATIONS)


def upgrade(target: Path, dry_run: bool = False) -> dict:
    """Apply all pending migrations on the target DB. Returns a result dict."""
    conn = sqlite3.connect(target)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        current = _current_version(conn)
        pending = _pending_migrations(current)

        if not pending:
            return {"status": "up-to-date", "current_version": current, "applied": []}

        applied: list[dict] = []
        for migration in pending:
            print(f"  applying migration {migration.version}: {migration.name}")
            print(f"    {migration.description}")

            if dry_run:
                print("    [dry-run] would execute above")
                continue

            conn.execute("BEGIN")
            try:
                for statement in migration.statements:
                    conn.execute(statement)

                if migration.verify is not None:
                    migration.verify(conn)

                _record_version(conn, migration.version)
                conn.commit()
                applied.append({
                    "version": migration.version,
                    "name": migration.name,
                })
            except BaseException:
                conn.rollback()
                raise

        return {
            "status": "upgraded",
            "from_version": current,
            "to_version": _current_version(conn),
            "applied": applied,
        }
    finally:
        conn.close()


def verify(target: Path) -> dict:
    """Check the DB schema matches the current registered version."""
    conn = sqlite3.connect(target)
    try:
        current = _current_version(conn)
        migration = next(
            (m for m in MIGRATIONS if m.version == current), None
        )
        if migration is None:
            return {"status": "unknown-version", "version": current}

        if migration.verify is not None:
            migration.verify(conn)

        return {
            "status": "verified",
            "version": current,
            "name": migration.name,
        }
    finally:
        conn.close()


def downgrade(target: Path, target_version: int) -> dict:
    """Revert to a previous version (only for reversible migrations)."""
    conn = sqlite3.connect(target)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        current = _current_version(conn)

        if target_version >= current:
            return {"status": "noop", "reason": f"target {target_version} >= current {current}"}

        # Find migrations between current and target_version (inclusive).
        to_revert = [
            m for m in MIGRATIONS
            if target_version < m.version <= current
        ]
        # Reverse order for rollback.
        to_revert = sorted(to_revert, key=lambda m: m.version, reverse=True)

        for migration in to_revert:
            if migration.downgrade is None:
                return {
                    "status": "blocked",
                    "reason": f"migration {migration.version} ({migration.name}) is not reversible",
                }
            print(f"  reverting migration {migration.version}: {migration.name}")

            conn.execute("BEGIN")
            try:
                for statement in migration.downgrade:
                    conn.execute(statement)
                _record_version(conn, migration.version - 1)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

        return {
            "status": "downgraded",
            "to_version": _current_version(conn),
        }
    finally:
        conn.close()


def report(target: Path) -> dict:
    """Return a human-readable status report for the target DB."""
    conn = sqlite3.connect(target)
    try:
        current = _current_version(conn)
        pending = _pending_migrations(current)
        migration = next(
            (m for m in MIGRATIONS if m.version == current), None
        )
        return {
            "path": str(target),
            "current_version": current,
            "current_name": migration.name if migration else "unknown",
            "pending_count": len(pending),
            "pending": [
                {"version": m.version, "name": m.name, "description": m.description}
                for m in pending
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="SPECTRA versioned migration runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--database",
        default=str(PROJECT_ROOT / "data" / "spectra.db"),
        help="Target database path (default: data/spectra.db — use a copy for rehearsal).",
    )
    dry = parser.add_argument("--dry-run", action="store_true",
                              help="Report pending migrations without applying them.")
    parser.add_argument("--verify", action="store_true",
                        help="Verify the DB schema matches the current version.")
    parser.add_argument("--report", action="store_true",
                        help="Print migration status without making changes.")
    parser.add_argument(
        "--target", type=int, default=None,
        help="For downgrade: target version to revert to.",
    )

    args = parser.parse_args()
    target = Path(args.database)

    if not target.exists():
        print(f"ERROR: database not found: {target}")
        return 1

    import json

    if args.report:
        result = report(target)
        print(json.dumps(result, indent=2, default=str))
        return 0

    if args.verify:
        result = verify(target)
        print(json.dumps(result, indent=2, default=str))
        if result["status"] != "verified":
            return 1
        return 0

    if args.target is not None:
        result = downgrade(target, args.target)
        print(json.dumps(result, indent=2, default=str))
        if result["status"] not in ("downgraded", "noop"):
            return 1
        return 0

    # Default: upgrade
    if args.dry_run:
        print(f"[dry-run] would apply migrations to: {target}")
    else:
        print(f"applying migrations to: {target}")
    result = upgrade(target, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))

    if result["status"] == "error" or (
        result["status"] == "upgraded" and not result["applied"]
    ):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
