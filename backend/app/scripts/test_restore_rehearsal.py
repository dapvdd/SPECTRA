"""Restore rehearsal and retention tests.

Covered:
- Restore to a disposable target copies the file and verifies it there
  (integrity, FK, row counts, matching SHA256).
- Refuses live-looking targets (/app/data/spectra.db, data/spectra.db).
- Refuses when backup == target.
- Refuses when the backup is missing.
- An empty restored catalog (0 hardware rows) fails the rehearsal.
- Retention: keep-newest-N prunes only matching names, never the newest N.
"""

import sqlite3
import time
from pathlib import Path

import pytest

from backend.app.scripts import restore_rehearsal as rr
from backend.app.scripts.backup_database import create_backup


SCHEMA = """
CREATE TABLE hardware (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);
CREATE TABLE build_messages (
    id INTEGER PRIMARY KEY,
    content TEXT
);
"""


def _seed(db_path: Path, hardware_rows: int = 12) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO hardware (name, type) VALUES (?, ?)",
            [(f"hw-{i}", "CPU") for i in range(hardware_rows)],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def backup_file(tmp_path):
    source = tmp_path / "source.db"
    _seed(source)
    backup = tmp_path / "backups" / "backup-test.db"
    create_backup(source, backup)
    return backup


class TestRestoreRehearsal:
    def test_restore_to_disposable_target_verifies(self, backup_file, tmp_path):
        target = tmp_path / "scratch" / "restored.db"
        result = rr.restore_rehearsal(backup_file, target)

        assert target.exists()
        assert result["verdict"] == "restore_rehearsal_passed"
        assert result["integrity_check"] == "ok"
        assert result["foreign_key_check"] == "ok"
        assert result["row_counts"]["hardware"] == 12
        assert result["backup_sha256"] == result["restored_sha256"]

    def test_refuses_live_app_path(self, backup_file):
        with pytest.raises(ValueError, match="live-looking path"):
            rr.restore_rehearsal(backup_file, Path("/app/data/spectra.db"))

    def test_refuses_relative_live_path(self, backup_file, tmp_path):
        with pytest.raises(ValueError, match="live-looking path"):
            rr.restore_rehearsal(backup_file, tmp_path / "data" / "spectra.db")

    def test_refuses_same_target_as_backup(self, backup_file):
        with pytest.raises(ValueError, match="must differ"):
            rr.restore_rehearsal(backup_file, backup_file)

    def test_missing_backup_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            rr.restore_rehearsal(tmp_path / "nope.db", tmp_path / "t.db")

    def test_empty_catalog_fails_rehearsal(self, tmp_path):
        # A backup of an empty catalog is not a valid restore target.
        empty_source = tmp_path / "empty.db"
        conn = sqlite3.connect(empty_source)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

        backup = tmp_path / "backup-empty.db"
        create_backup(empty_source, backup)

        with pytest.raises(RuntimeError, match="no hardware rows"):
            rr.restore_rehearsal(backup, tmp_path / "restored.db")


class TestRetention:
    def _make_backups(self, directory: Path, names_and_ages):
        for name, age_hours in names_and_ages:
            p = directory / name
            p.write_bytes(b"sqlite-placeholder")
            stamp = time.time() - age_hours * 3600
            import os
            os.utime(p, (stamp, stamp))

    def test_keep_newest_n(self, tmp_path):
        self._make_backups(tmp_path, [
            ("backup-a.db", 1),
            ("backup-b.db", 2),
            ("backup-c.db", 3),
            ("backup-d.db", 4),
            ("backup-e.db", 5),
        ])
        result = rr.prune_backups(tmp_path, keep=3)

        assert result["kept_count"] == 3
        assert result["pruned_count"] == 2
        assert set(result["kept"]) == {"backup-a.db", "backup-b.db", "backup-c.db"}
        assert set(result["pruned"]) == {"backup-d.db", "backup-e.db"}
        assert not (tmp_path / "backup-d.db").exists()

    def test_never_prunes_below_one(self, tmp_path):
        self._make_backups(tmp_path, [("backup-only.db", 1)])
        result = rr.prune_backups(tmp_path, keep=1)
        assert result["pruned_count"] == 0
        assert (tmp_path / "backup-only.db").exists()

    def test_keep_zero_refused(self, tmp_path):
        with pytest.raises(ValueError, match="at least 1"):
            rr.prune_backups(tmp_path, keep=0)

    def test_no_backups_refused(self, tmp_path):
        (tmp_path / "unrelated.txt").write_text("not a backup")
        with pytest.raises(FileNotFoundError, match="no backup files"):
            rr.prune_backups(tmp_path, keep=3)

    def test_non_backup_files_never_touched(self, tmp_path):
        self._make_backups(tmp_path, [
            ("backup-a.db", 1),
            ("backup-b.db", 2),
            ("backup-c.db", 3),
            ("backup-d.db", 4),
            ("spectra_env.py", 99),      # not a backup pattern
            ("notes.txt", 99),           # not a backup pattern
        ])
        result = rr.prune_backups(tmp_path, keep=2)

        assert set(result["pruned"]) == {"backup-c.db", "backup-d.db"}
        assert (tmp_path / "spectra_env.py").exists()
        assert (tmp_path / "notes.txt").exists()
