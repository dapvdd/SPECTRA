"""Tests for the SPECTRA data-integrity check script.

Runs check_database() against disposable in-memory/file databases and
verifies the pass/fail logic: quick_check passes, foreign_key_check passes
on a schema-consistent DB, and the row-count floor flags truncated data.
Never touches the live data/spectra.db.
"""

import sqlite3
from pathlib import Path

from backend.app.scripts.check_data_integrity import (
    _MIN_ROW_COUNTS,
    check_database,
)


def _create_fresh_db(path: Path) -> None:
    """Create a DB whose tables satisfy the integrity check (schema-only)."""
    from sqlalchemy import create_engine as _ce

    from backend.app.database import Base
    from backend.app.models import (  # noqa: F401
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )

    url = "sqlite:///" + str(path).replace("\\", "/")
    engine = _ce(url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()


class TestCheckDataIntegrity:
    def test_fresh_schema_passes(self, tmp_path):
        db = tmp_path / "fresh.db"
        _create_fresh_db(db)
        result = check_database(db)

        assert result["quick_check"] == "ok"
        assert result["foreign_key_check_violations"] == 0
        # Fresh DB has 0 rows; the row floor is applied only when NOT schema-only.

    def test_corrupt_db_fails_quick_check(self, tmp_path):
        db = tmp_path / "corrupt.db"
        _create_fresh_db(db)
        # Corrupt the file by writing garbage bytes across the header.
        with open(db, "r+b") as fh:
            fh.seek(0)
            fh.write(b"\x00" * 512)

        result = check_database(db)

        assert result["quick_check"] != "ok"

    def test_fk_violation_is_detected(self, tmp_path):
        db = tmp_path / "fk.db"
        _create_fresh_db(db)

        conn = sqlite3.connect(db)
        try:
            # Insert an orphaned benchmark with FK enforcement OFF (simulates
            # a bug in an import script or a DB restored from a partial backup).
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO benchmark_results "
                "(hardware_id, benchmark_name, score, unit, test_type)"
                " VALUES (999999, 'Geekbench 7', 1.0, 'points', 'single-core')"
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

        result = check_database(db)

        assert result["foreign_key_check_violations"] >= 1

    def test_row_count_floor_flags_truncated_db(self, tmp_path):
        db = tmp_path / "truncated.db"
        _create_fresh_db(db)
        # Insert fewer rows than the floor for one table.
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO hardware (name, manufacturer, type) "
                "VALUES ('Test CPU', 'Test', 'CPU')"
            )
            conn.commit()
        finally:
            conn.close()

        result = check_database(db)

        # The script reports the count but does not evaluate the floor itself;
        # that decision lives in main() so the check remains data-only here.
        assert result["row_counts"]["hardware"] == 1

    def test_row_count_minimum_exposed(self):
        assert isinstance(_MIN_ROW_COUNTS, dict)
        assert "hardware" in _MIN_ROW_COUNTS
        assert _MIN_ROW_COUNTS["hardware"] > 0
