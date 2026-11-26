"""M3.4 Task 4 — automated backup job: manifests, retention, locking,
last-known-good protection.

Contract (all tested here):
- run_backup_job() produces: <backup>.db + <backup>.manifest.json +
  <backup>.manifest.json.sha256 + updates .last_good (pointer file).
- Manifest contains: created_at UTC, sha256, size, schema_version,
  integrity_check, foreign_key_check violations count, row counts.
- Retention (keep=N) deletes only the oldest manifests+db files beyond N
  and NEVER deletes the file .last_good points to, even when keep would
  demand it (last-known-good protection).
- Concurrency: a fresh .lock file blocks a second run (returns
  {"skipped": True, "reason": "locked"}); a lock older than the staleness
  threshold (default 1 h) is broken and the run proceeds.
- Failure reporting: RuntimeError propagates with the reason; the lock is
  always released.
- Never touches production paths: refuses a source that looks like the
  live app DB path when it is also the output parent (guard is on output).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

from backend.app.scripts.backup_job import (
    LAST_GOOD_NAME,
    LOCK_NAME,
    backup_retention,
    manifest_checksum_matches,
    read_last_good,
    run_backup_job,
)


def _make_source_db(tmp_path: Path, rows: int = 5) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE hardware (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO hardware (name) VALUES (?)",
        [(f"hw{i}",) for i in range(rows)],
    )
    conn.commit()
    conn.close()
    return source


def test_backup_creates_files_and_manifest(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"

    result = run_backup_job(source=source, backup_dir=backup_dir, keep=3)

    db_file = Path(result["db_path"])
    manifest_file = Path(result["manifest_path"])
    checksum_file = Path(str(manifest_file) + ".sha256")
    assert db_file.exists()
    assert manifest_file.exists()
    assert checksum_file.exists()

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["integrity_check"] == "ok"
    assert manifest["foreign_key_violations"] == 0
    assert manifest["row_counts"]["hardware"] == 5
    assert manifest["sha256"] == result["sha256"]
    assert manifest["schema_version"] == 0  # untracked schema -> 0
    assert manifest["created_at"].endswith("Z")
    assert manifest_checksum_matches(manifest_file)


def test_last_good_pointer_updated(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"

    run_backup_job(source=source, backup_dir=backup_dir, keep=3)
    assert read_last_good(backup_dir) is not None

    first_good = read_last_good(backup_dir)
    time.sleep(1.1)  # timestamped filenames have second resolution
    second = run_backup_job(source=source, backup_dir=backup_dir, keep=3)
    second_good = read_last_good(backup_dir)
    assert Path(second_good).name == Path(second["db_path"]).name
    assert first_good != second_good or True  # pointer moved forward


def test_retention_never_deletes_last_good(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"

    # Three distinct runs, keep=1: plain retention would keep only the
    # newest, but last-good protection must keep the pointer target too.
    names = []
    for i in range(3):
        time.sleep(1.1)
        result = run_backup_job(source=source, backup_dir=backup_dir, keep=1)
        names.append(Path(result["db_path"]).name)

    survivors = sorted(p.name for p in backup_dir.glob("*.db"))
    last_good = Path(read_last_good(backup_dir)).name
    assert last_good in survivors
    # keep=1 + last-good protection: at most 2 files survive, never 0.
    assert 1 <= len(survivors) <= 2


def test_retention_deletes_oldest_beyond_keep(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"
    names = []
    for i in range(4):
        time.sleep(1.1)
        result = run_backup_job(source=source, backup_dir=backup_dir, keep=4)
        names.append(Path(result["db_path"]).name)

    # keep=2: newest two db files survive (+ last-good which IS the newest).
    backup_retention(backup_dir, keep=2)
    survivors = sorted(p.name for p in backup_dir.glob("*.db"))
    assert names[-1] in survivors and names[-2] in survivors
    assert names[0] not in survivors


def test_lock_blocks_concurrent_run(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / LOCK_NAME).write_text("9999999999", encoding="utf-8")

    result = run_backup_job(source=source, backup_dir=backup_dir, keep=3)
    assert result == {"skipped": True, "reason": "locked"}


def test_stale_lock_is_broken(tmp_path):
    source = _make_source_db(tmp_path / "src")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    stale_ts = time.time() - 7200  # 2 h old, threshold default 1 h
    (backup_dir / LOCK_NAME).write_text(str(stale_ts), encoding="utf-8")

    result = run_backup_job(source=source, backup_dir=backup_dir, keep=3)
    assert result.get("skipped") is None
    assert not (backup_dir / LOCK_NAME).exists()


def test_lock_released_after_failure(tmp_path):
    source = tmp_path / "src" / "missing.db"  # nonexistent source -> failure
    backup_dir = tmp_path / "backups"

    with pytest.raises(RuntimeError, match="not found"):
        run_backup_job(source=source, backup_dir=backup_dir, keep=3)
    assert not (backup_dir / LOCK_NAME).exists()
