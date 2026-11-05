"""Tests for Stage 7 data-integrity drill against the dev copy.

Contract:
- ``integrity_verdict(db_path)`` returns a deterministic dict with
  ``verdict`` (``PASS`` | ``FAIL``), ``quick_check``, FK violations,
  row counts, min_met, schema presence, and curated counts.
- ``curated_counts(db_path)`` counts the mission-relevant tables.
- Read-only: the drill never writes to the checked database (verified by
  hashing the file before/after on a scratch copy).
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from backend.app.scripts import data_integrity_verify as div
from backend.app.scripts.check_data_integrity import _MIN_ROW_COUNTS


def _blank_db(path: Path, seed_counts: dict[str, int] | None = None) -> None:
    """Create a small valid DB with the minimum contract tables."""
    conn = sqlite3.connect(path)
    for table, minimum in _MIN_ROW_COUNTS.items():
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY)")
        conn.execute(f"INSERT INTO {table} (id) VALUES (0)")
        for i in range(1, minimum):
            conn.execute(f"INSERT INTO {table} (id) VALUES ({i})")
    conn.commit()
    conn.close()


class TestCuratedCounts:
    def test_counts_all_curated_tables_or_none(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        counts = div.curated_counts(str(db))
        assert set(counts) == set(div._CURATED_TABLES)
        # _blank_db doesn't create non-minimum tables -> those count as None.
        assert all(v is None or isinstance(v, int) for v in counts.values())


class TestIntegrityVerdict:
    def test_blank_min_database_passes(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        result = div.integrity_verdict(str(db))
        assert result["verdict"] == "PASS"
        assert result["quick_check"] == "ok"
        assert result["foreign_key_check_violations"] == 0
        assert all(result["min_met"].values())

    def test_fails_on_truncated_table(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        conn = sqlite3.connect(db)
        # Truncate benchmark_results below its floor -> min_met False.
        conn.execute(f"DELETE FROM benchmark_results WHERE id > 10")
        conn.commit()
        conn.close()
        result = div.integrity_verdict(str(db))
        assert result["min_met"]["benchmark_results"] is False
        assert result["verdict"] == "FAIL"

    def test_schema_presence_reported(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        result = div.integrity_verdict(str(db))
        assert result["schema_present"]["complete"] is True
        for t in _MIN_ROW_COUNTS:
            assert t in result["schema_present"]["tables"]

    def test_verdict_is_deterministic(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        a = div.integrity_verdict(str(db))
        b = div.integrity_verdict(str(db))
        assert a == b

    def test_read_only_never_mutates_database(self, tmp_path):
        db = tmp_path / "x.db"
        _blank_db(db)
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        div.integrity_verdict(str(db))
        div.curated_counts(str(db))
        after = hashlib.sha256(db.read_bytes()).hexdigest()
        assert before == after

    def test_missing_path_yields_fail(self, tmp_path):
        with pytest.raises(Exception):
            div.integrity_verdict(str(tmp_path / "nope.db"))
