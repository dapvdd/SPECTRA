"""M3 Phase 1 — migration v4 tests (RED first).

Pins the migration contract from docs/m3/M3_DATA_CONTRACT.md §2:
- v4 adds canonical_key/product_family/identity_status/record_status/
  superseded_by_id to hardware (additive ALTER TABLE, nullable)
- v4 adds ingestion_runs and publication_batches tables
- unique partial index on canonical_key (WHERE canonical_key IS NOT NULL)
- pre-M3 rows (NULL canonical keys) are untouched and remain valid
- re-run is a no-op; verify() checks the post-state; downgrade documented
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.migrations.runner import (  # noqa: E402
    LATEST_VERSION,
    MIGRATIONS,
    upgrade,
)


def _make_v3_db(path: Path) -> None:
    """Build a minimal v3-shaped DB (spec tables + a hardware row)."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE hardware (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL,
            manufacturer VARCHAR(100) NOT NULL,
            type VARCHAR(50) NOT NULL
        );
        CREATE TABLE sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL,
            url VARCHAR(500) NOT NULL
        );
        CREATE TABLE ram_specifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hardware_id INTEGER REFERENCES hardware(id) UNIQUE,
            ddr_generation VARCHAR(10),
            capacity_gb INTEGER, speed_mhz INTEGER, modules INTEGER,
            ecc INTEGER, voltage_v FLOAT, form_factor VARCHAR(30)
        );
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_version (id, version, applied_at) VALUES (1, 3, 'test');
        INSERT INTO hardware (name, manufacturer, type)
            VALUES ('Legacy CPU', 'Intel', 'CPU');
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def v3_db(tmp_path):
    db = tmp_path / "v3_copy.db"
    _make_v3_db(db)
    return db


class TestMigrationV4Exists:
    def test_v4_registered(self):
        versions = [m.version for m in MIGRATIONS]
        assert 4 in versions

    def test_v4_is_latest(self):
        assert LATEST_VERSION == 4


class TestMigrationV4Additive:
    def test_applies_on_v3_copy(self, v3_db):
        result = upgrade(v3_db)
        assert [m["version"] for m in result["applied"]] == [4]
        conn = sqlite3.connect(v3_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(hardware)").fetchall()}
        assert {"canonical_key", "product_family", "identity_status",
                "record_status", "superseded_by_id"} <= cols
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"ingestion_runs", "publication_batches"} <= tables
        conn.close()

    def test_legacy_rows_untouched(self, v3_db):
        upgrade(v3_db)
        conn = sqlite3.connect(v3_db)
        rows = conn.execute(
            "SELECT name, canonical_key, record_status FROM hardware"
        ).fetchall()
        assert rows == [("Legacy CPU", None, None)]
        conn.close()

    def test_unique_partial_index(self, v3_db):
        upgrade(v3_db)
        conn = sqlite3.connect(v3_db)
        # Two NULL canonical keys are allowed; two equal non-NULL keys are not.
        conn.execute(
            "INSERT INTO hardware (name, manufacturer, type, canonical_key) "
            "VALUES ('A', 'M', 'RAM', 'm|ram|a|k')"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO hardware (name, manufacturer, type, canonical_key) "
                "VALUES ('B', 'M', 'RAM', 'm|ram|a|k')"
            )
        conn.close()

    def test_null_keys_unlimited(self, v3_db):
        upgrade(v3_db)
        conn = sqlite3.connect(v3_db)
        conn.execute(
            "INSERT INTO hardware (name, manufacturer, type) VALUES ('C', 'M', 'CPU')")
        conn.execute(
            "INSERT INTO hardware (name, manufacturer, type) VALUES ('D', 'M', 'CPU')")
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM hardware WHERE canonical_key IS NULL").fetchone()[0]
        assert n == 3  # legacy + 2 new NULL-key rows
        conn.close()

    def test_rerun_noop(self, v3_db):
        upgrade(v3_db)
        result = upgrade(v3_db)
        assert result["applied"] == []

    def test_ingestion_runs_columns(self, v3_db):
        upgrade(v3_db)
        conn = sqlite3.connect(v3_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ingestion_runs)").fetchall()}
        assert {"id", "run_type", "source_id", "category", "mode", "status",
                "rows_seen", "rows_applied", "rows_rejected",
                "rows_quarantined", "started_at", "finished_at",
                "notes"} <= cols
        conn.close()

    def test_publication_batches_columns(self, v3_db):
        upgrade(v3_db)
        conn = sqlite3.connect(v3_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(publication_batches)").fetchall()}
        assert {"id", "batch_no", "category", "record_count", "approved_by",
                "status", "created_at", "published_at", "notes"} <= cols
        conn.close()
