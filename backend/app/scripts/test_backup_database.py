"""Backup utility tests — consistency, verification, failure modes.

Covered:
- Backup of a quiet DB is verified (integrity, FK, row counts, sha256).
- Backup taken WHILE the source is being written still verifies (WAL/online
  backup API consistency, vs a raw file copy which would tear).
- Row-count mismatch between source and backup is detected.
- Corrupt backup fails verification.
- verify-only mode works on an existing file.
- Missing source/backup files raise FileNotFoundError.
"""

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from backend.app.scripts import backup_database as bk


SCHEMA = """
CREATE TABLE hardware (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);
CREATE TABLE cpu_specifications (
    id INTEGER PRIMARY KEY,
    hardware_id INTEGER NOT NULL REFERENCES hardware(id),
    cores INTEGER
);
CREATE TABLE build_messages (
    id INTEGER PRIMARY KEY,
    content TEXT
);
"""


def _seed(db_path: Path, hardware_rows: int = 10, messages: int = 5) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO hardware (name, type) VALUES (?, ?)",
            [(f"hw-{i}", "CPU") for i in range(hardware_rows)],
        )
        conn.executemany(
            "INSERT INTO cpu_specifications (hardware_id, cores) VALUES (?, ?)",
            [(i + 1, 6) for i in range(hardware_rows)],
        )
        conn.executemany(
            "INSERT INTO build_messages (content) VALUES (?)",
            [(f"message {i}",) for i in range(messages)],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def source_db(tmp_path):
    db = tmp_path / "source.db"
    _seed(db)
    return db


class TestCreateBackup:
    def test_quiet_backup_verifies(self, source_db, tmp_path):
        output = tmp_path / "backup.db"
        result = bk.create_backup(source_db, output)

        assert output.exists()
        assert result["integrity_check"] == "ok"
        assert result["foreign_key_check"] == "ok"
        assert result["row_counts"]["hardware"] == 10
        assert result["row_counts"]["cpu_specifications"] == 10
        assert result["row_counts"]["build_messages"] == 5
        assert len(result["sha256"]) == 64

    def test_row_counts_match_source(self, source_db, tmp_path):
        output = tmp_path / "backup.db"
        result = bk.create_backup(source_db, output)
        assert result["row_counts_match_source"] is True
        assert result["source_row_counts"]["hardware"] == 10

    def test_missing_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            bk.create_backup(tmp_path / "nope.db", tmp_path / "out.db")

    def test_stale_output_replaced(self, source_db, tmp_path):
        output = tmp_path / "backup.db"
        output.write_bytes(b"stale content from an earlier run")
        bk.create_backup(source_db, output)
        result = bk.verify_backup(output)
        assert result["integrity_check"] == "ok"


class TestWALConsistency:
    def test_backup_during_writes_is_consistent(self, tmp_path):
        """A backup taken while the source is under active writes must still
        verify. This is the property a raw file copy does NOT have."""
        source = tmp_path / "busy.db"
        _seed(source, hardware_rows=200, messages=0)

        output = tmp_path / "busy-backup.db"
        errors: list[Exception] = []
        stop = threading.Event()

        def writer():
            conn = sqlite3.connect(source)
            try:
                i = 0
                while not stop.is_set():
                    try:
                        conn.execute(
                            "INSERT INTO build_messages (content) VALUES (?)",
                            (f"write {i}",),
                        )
                        conn.commit()
                        i += 1
                    except sqlite3.Error as exc:  # pragma: no cover
                        errors.append(exc)
                        return
                    time.sleep(0.001)
            finally:
                conn.close()

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)  # let the writer get going
            result = bk.create_backup(source, output, compare_source=False)
        finally:
            stop.set()
            thread.join(timeout=5)

        assert not errors
        assert result["integrity_check"] == "ok"
        assert result["foreign_key_check"] == "ok"
        # The snapshot is a point-in-time consistent state: message count is
        # whatever was committed at backup moment — never torn. Under active
        # writes the source keeps moving, so a source-vs-backup count
        # comparison is not meaningful here; structural verification is.
        assert result["row_counts"]["build_messages"] >= 0
        # The backup file itself must re-verify standalone.
        recheck = bk.verify_backup(output)
        assert recheck["integrity_check"] == "ok"
        assert (
            recheck["row_counts"]["build_messages"]
            == result["row_counts"]["build_messages"]
        )

    def test_backup_in_wal_mode_works(self, tmp_path):
        source = tmp_path / "wal.db"
        conn = sqlite3.connect(source)
        try:
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executemany(
                "INSERT INTO hardware (name, type) VALUES (?, ?)",
                [(f"gpu-{i}", "GPU") for i in range(25)],
            )
            conn.commit()
            # Leave WAL content in place (no checkpoint) to prove the backup
            # API reads through the WAL.
        finally:
            conn.close()

        output = tmp_path / "wal-backup.db"
        result = bk.create_backup(source, output)
        assert result["row_counts"]["hardware"] == 25
        assert result["integrity_check"] == "ok"


class TestVerifyBackup:
    def test_verify_only_mode(self, source_db, tmp_path):
        output = tmp_path / "backup.db"
        bk.create_backup(source_db, output)
        result = bk.verify_backup(output)
        assert result["integrity_check"] == "ok"

    def test_missing_backup_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            bk.verify_backup(tmp_path / "nope.db")

    def test_corrupt_backup_fails(self, tmp_path):
        corrupt = tmp_path / "corrupt.db"
        # Not a SQLite file at all.
        corrupt.write_bytes(b"this is not a database" * 100)
        with pytest.raises(Exception):
            bk.verify_backup(corrupt)

    def test_row_count_mismatch_detected(self, source_db, tmp_path):
        output = tmp_path / "backup.db"
        bk.create_backup(source_db, output)

        # Change the source after the backup.
        conn = sqlite3.connect(source_db)
        try:
            conn.execute(
                "INSERT INTO hardware (name, type) VALUES ('extra', 'CPU')"
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(RuntimeError, match="row-count mismatch"):
            bk.verify_backup(output, source=source_db)


class TestSha256:
    def test_sha256_of_known_content(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"spectra")
        assert bk.sha256_of(f) == (
            "e285cdd85064e369f2a8abef7052b621d9e596b3a29a8aadba8070de08c566c0"
        )

    def test_sha256_is_streamed(self, tmp_path):
        # A file larger than the 1 MiB chunk size still hashes correctly.
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * (1 << 21))  # 2 MiB
        import hashlib
        assert bk.sha256_of(f) == hashlib.sha256(b"x" * (1 << 21)).hexdigest()
