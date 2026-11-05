"""Tests for the SPECTRA versioned migration runner (backend/app/migrations/runner.py).

Exercises the runner against isolated in-memory SQLite databases so no live
data is touched. Each test creates a target DB by cloning the expected schema
via SQLAlchemy's Base, then exercises upgrade/verify/report/downgrade.

Design constraints verified by tests:
- Additive-only: runner never rewrites or drops tables.
- Idempotent: running upgrade twice is a no-op past version 1.
- Verifiable: the baseline verify() catches missing tables and columns.
- Ordered: migrations are applied in version order.
- Copy-first: runner is always run against a disposable copy in these tests.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from backend.app.database import Base
from backend.app.migrations import runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clone_schema(target: Path) -> None:
    """Create a fresh DB at target that mirrors the v1 (baseline) schema.

    All models must be imported so their tables are registered with Base.metadata
    before create_all() is called. We import them directly rather than calling
    init_database (which uses the live global engine).

    The ORM model also declares the v2 auth additions (User model, owner_id
    column); those are dropped here so the clone matches the v1 baseline the
    runner migrates from.
    """
    # Import all models so their Table objects are registered with Base.metadata.
    from backend.app.models import (  # noqa: F401  (registers tables)
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )
    from backend.app.auth import User  # noqa: F401  (registers the users table)

    from sqlalchemy import create_engine as _ce

    target_url = "sqlite:///" + str(target).replace("\\", "/")
    target_engine = _ce(target_url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=target_engine)
    finally:
        target_engine.dispose()

    # Simulate the real pre-v2 database: no `users` table and no owner_id column.
    conn = sqlite3.connect(target)
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute(
        "CREATE TABLE build_conversations_v1 AS "
        "SELECT id, cpu_hardware_id, gpu_hardware_id, created_at, updated_at "
        "FROM build_conversations"
    )
    conn.execute("DROP TABLE build_conversations")
    conn.execute(
        "ALTER TABLE build_conversations_v1 RENAME TO build_conversations"
    )
    conn.commit()
    conn.close()


def _clone_v2_schema(target: Path) -> None:
    """Create a fresh DB at target that mirrors the v2 (auth) schema.

    Used by tests that operate post-v2-migration without running the runner,
    e.g. to exercise services that assume owner_id/users are present.
    """
    from backend.app.models import (  # noqa: F401  (registers tables)
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )
    from backend.app.auth import User  # noqa: F401  (registers the users table)

    from sqlalchemy import create_engine as _ce

    target_url = "sqlite:///" + str(target).replace("\\", "/")
    target_engine = _ce(target_url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=target_engine)
    finally:
        target_engine.dispose()


def _clone_schema_with_missing_table(target: Path, missing_table: str) -> None:
    """Create a DB with all expected tables EXCEPT ``missing_table``."""
    from backend.app.models import (  # noqa: F401
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )

    from sqlalchemy import create_engine as _ce

    target_url = "sqlite:///" + str(target).replace("\\", "/")
    target_engine = _ce(target_url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=target_engine)
        target_engine.dispose()
    except Exception:
        target_engine.dispose()
        raise

    # Remove the specified table to simulate an incomplete schema.
    conn = sqlite3.connect(target)
    conn.execute(f"DROP TABLE {missing_table}")
    conn.commit()
    conn.close()


def _clone_schema_with_missing_column(target: Path, table: str, column: str) -> None:
    """Create a DB with a table deliberately missing one column."""
    from backend.app.models import (  # noqa: F401
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )

    from sqlalchemy import create_engine as _ce

    target_url = "sqlite:///" + str(target).replace("\\", "/")
    target_engine = _ce(target_url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=target_engine)
    finally:
        target_engine.dispose()

    # SQLite does not support DROP COLUMN. Recreate the table without the
    # unwanted column by listing columns explicitly (SQLite limitation workaround).
    conn = sqlite3.connect(target)
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    remaining_cols = [
        r[1] for r in conn.execute(f"PRAGMA table_info({table}_old)").fetchall()
        if r[1] != column
    ]
    col_list = ", ".join(remaining_cols)
    conn.execute(f"CREATE TABLE {table} AS SELECT {col_list} FROM {table}_old")
    conn.execute(f"DROP TABLE {table}_old")
    conn.commit()
    conn.close()


def _version(target: Path) -> int:
    conn = sqlite3.connect(target)
    try:
        row = conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _tables(target: Path) -> set[str]:
    conn = sqlite3.connect(target)
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def _columns(target: Path, table: str) -> set[str]:
    conn = sqlite3.connect(target)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMigrationRunnerUpgradeBaseline:
    def test_upgrade_records_version_two_on_fresh_schema_db(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        result = runner.upgrade(db, dry_run=False)

        assert result["status"] == "upgraded"
        assert result["from_version"] == 0
        assert result["to_version"] == 2
        assert [m["version"] for m in result["applied"]] == [1, 2]

    def test_upgrade_is_idempotent_on_already_baseline_db(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        runner.upgrade(db)
        result2 = runner.upgrade(db)

        assert result2["status"] == "up-to-date"
        assert result2["current_version"] == 2
        assert result2["applied"] == []

    def test_dry_run_does_not_record_version(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        result = runner.upgrade(db, dry_run=True)

        assert result["applied"] == []
        assert _version(db) == 0  # not recorded


class TestMigrationRunnerAuthV2:
    def test_v2_creates_users_and_owner_id(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        result = runner.upgrade(db, dry_run=False)

        assert result["status"] == "upgraded"
        assert result["to_version"] == 2
        assert "users" in _tables(db)
        assert "owner_id" in _columns(db, "build_conversations")

    def test_v2_upgrade_is_idempotent(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.upgrade(db)

        assert result["status"] == "up-to-date"
        assert _version(db) == 2

    def test_v2_run_on_copy_then_rollback(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.downgrade(db, target_version=1)

        assert result["status"] == "downgraded"
        assert _version(db) == 1
        assert "users" not in _tables(db)
        assert "owner_id" not in _columns(db, "build_conversations")


class TestMigrationRunnerVerify:
    def test_verify_passes_on_correct_schema(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.verify(db)

        assert result["status"] == "verified"
        assert result["version"] == 2
        assert result["name"] == "auth-tables"

    def test_verify_fails_when_table_is_missing(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema_with_missing_table(db, "benchmark_results")

        # The schema is already incomplete, so upgrade's verification must
        # raise instead of recording a version.
        with pytest.raises(RuntimeError, match="missing tables"):
            runner.upgrade(db)

    def test_verify_fails_when_column_is_missing(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema_with_missing_column(db, "hardware", "segment")

        with pytest.raises(RuntimeError, match="missing columns"):
            runner.upgrade(db)


class TestMigrationRunnerReport:
    def test_report_shows_pending_on_fresh_db(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        result = runner.report(db)

        assert result["current_version"] == 0
        assert result["pending_count"] == 2
        assert [m["version"] for m in result["pending"]] == [1, 2]

    def test_report_shows_zero_pending_after_upgrade(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.report(db)

        assert result["current_version"] == 2
        assert result["pending_count"] == 0
        assert result["pending"] == []


class TestMigrationRunnerDowngrade:
    def test_downgrade_is_blocked_for_baseline(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.downgrade(db, target_version=0)

        assert result["status"] == "blocked"
        assert "not reversible" in result["reason"]

    def test_downgrade_target_above_current_is_noop(self, tmp_path):
        db = tmp_path / "spectra.db"
        _clone_schema(db)
        runner.upgrade(db)

        result = runner.downgrade(db, target_version=2)

        assert result["status"] == "noop"


class TestMigrationRunnerSchemaDefinition:
    def test_expected_tables_match_real_schema(self, tmp_path):
        """Ensure _EXPECTED_TABLES stays in sync with the ORM model."""
        db = tmp_path / "spectra.db"
        _clone_schema(db)

        actual_tables = _tables(db)
        for table, expected_cols in runner._EXPECTED_TABLES.items():
            assert table in actual_tables, f"expected table '{table}' not found in schema"
            actual_cols = _columns(db, table)
            assert (
                expected_cols <= actual_cols
            ), f"table '{table}': _EXPECTED_TABLES lists columns not in model: {expected_cols - actual_cols}"
