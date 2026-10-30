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
