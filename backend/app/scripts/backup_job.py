"""Automated backup job for SPECTRA (M3.4 Task 4).

Wraps the existing consistent-backup machinery
(``backend.app.scripts.backup_database``) with the operational pieces a
scheduled job needs:

- Timestamped, collision-safe backup files inside a backup directory.
- A JSON manifest per backup: timestamp, sha256, size, schema_version,
  integrity_check, foreign-key violations, core row counts.
- A SHA-256 checksum file for the manifest itself (tamper-evidence).
- A ``.last_good`` pointer naming the newest backup that PASSED
  verification — retention never deletes that file.
- Configurable retention (keep-newest-N) that still protects last-good.
- Safe concurrency: an O_EXCL-style lock file with a timestamp payload;
  a fresh lock makes a second run skip (not fail), a stale lock (older
  than ``LOCK_STALE_SECONDS``) is broken and the run proceeds.
- Failure reporting: any verification failure raises RuntimeError with a
  precise reason and always releases the lock.

Production scheduling is USER-GATED: the cron entry in
``ops/backup/cron_backup.sh.example`` is documentation, never installed by
this code. Nothing here ever touches the live database path as a write
target; the source is only ever read (SQLite Online Backup API).

Usage::

    python -m backend.app.scripts.backup_job \
        --source /app/data/spectra.db --backup-dir /backups/spectra --keep 7

    # Verify an existing backup set only:
    python -m backend.app.scripts.backup_job --verify-dir /backups/spectra

Exit codes: 0 = backup created and verified (or skip when locked);
1 = verification/backup failure; 2 = usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.app.scripts.backup_database import (
    _COUNTED_TABLES,
    _foreign_keys_ok,
    _integrity_ok,
    _row_counts,
    create_backup,
    sha256_of,
)
from backend.app.scripts.restore_rehearsal import _BACKUP_NAME

LOCK_NAME = ".backup.lock"
LAST_GOOD_NAME = ".last_good"
LOCK_STALE_SECONDS = 3600  # 1 h: a live backup never takes this long

_MANIFEST_SUMMARY_KEYS = (
    "db_path",
    "manifest_path",
    "sha256",
    "skipped",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _backup_filename(now: datetime) -> str:
    return f"spectra_backup_{now.strftime('%Y%m%dT%H%M%SZ')}.db"


def _schema_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='schema_version'"
        ).fetchone()
        if not has_table:
            return 0
        version = conn.execute(
            "SELECT version FROM schema_version WHERE id=1"
        ).fetchone()
        return int(version[0]) if version is not None and version[0] is not None else 0
    finally:
        conn.close()


def _write_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    # newline="" disables platform translation: bytes on disk are exactly
    # `content`, so checksums are reproducible across Linux/Windows.
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _acquire_lock(backup_dir: Path) -> int | None:
    """Create the lock file; return the fd or None when already locked.

    Uses O_CREAT|O_EXCL (atomic on POSIX and Windows) instead of fcntl,
    which does not exist on Windows; the container runtime is Linux, and
    this keeps local rehearsal environments importable.
    """
    lock_path = backup_dir / LOCK_NAME
    if lock_path.exists():
        try:
            age = time.time() - float(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            age = None
        if age is not None and age < LOCK_STALE_SECONDS:
            return None
        # Stale or corrupt lock: break it and continue.
        lock_path.unlink(missing_ok=True)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Raced between exists() and open: treat as locked.
        return None
    os.write(fd, str(time.time()).encode("ascii"))
    return fd


def _release_lock(backup_dir: Path, fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass
    (backup_dir / LOCK_NAME).unlink(missing_ok=True)


def run_backup_job(
    *,
    source: Path,
    backup_dir: Path,
    keep: int,
    compare_source: bool = True,
) -> dict:
    """Create one verified backup + manifest under the locking protocol.

    Raises RuntimeError when the backup or verification fails; the lock is
    always released. Returns a result dict (db_path, manifest_path, sha256,
    created_at) or {"skipped": True, "reason": "locked"}.
    """
    source = Path(source)
    backup_dir = Path(backup_dir)
    if keep < 1:
        raise ValueError("keep must be >= 1")
    if not source.exists():
        raise RuntimeError(f"source database not found: {source}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    fd = _acquire_lock(backup_dir)
    if fd is None:
        return {"skipped": True, "reason": "locked"}

    try:
        now = datetime.now(timezone.utc)
        db_path = backup_dir / _backup_filename(now)
        try:
            evidence = create_backup(
                source=source,
                output=db_path,
                compare_source=compare_source,
            )
        except Exception as error:  # noqa: BLE001 - report any failure
            raise RuntimeError(f"backup failed: {error}") from error

        manifest = {
            "created_at": _utc_now(),
            "db_file": db_path.name,
            "sha256": evidence["sha256"],
            "size_bytes": db_path.stat().st_size,
            "schema_version": _schema_version(db_path),
            "integrity_check": evidence.get("integrity_check", "ok"),
            "foreign_key_violations": len(evidence.get("foreign_key_violations", []) or []),
            "row_counts": evidence.get("row_counts", {}),
            "source": str(source),
        }
        manifest_path = backup_dir / (db_path.name + ".manifest.json")
        manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
        _write_text_atomic(manifest_path, manifest_json + "\n")

        # Digest the bytes actually on disk (not the in-memory string) so
        # the checksum stays valid regardless of any later text translation.
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        _write_text_atomic(
            Path(str(manifest_path) + ".sha256"), f"{digest}  {manifest_path.name}\n"
        )

        # Only now, after full verification, is this backup last-known-good.
        _write_text_atomic(backup_dir / LAST_GOOD_NAME, db_path.name + "\n")

        backup_retention(backup_dir, keep=keep)

        return {
            "db_path": str(db_path),
            "manifest_path": str(manifest_path),
            "sha256": evidence["sha256"],
            "created_at": manifest["created_at"],
        }
    finally:
        _release_lock(backup_dir, fd)


def backup_retention(backup_dir: Path, *, keep: int) -> dict:
    """Delete oldest backup files beyond keep, protecting .last_good.

    Mirrors restore_rehearsal.prune's safety rules and adds last-good
    protection: the file the pointer names is never deleted even when the
    keep window would remove it. Refuses to produce an empty surviving set.
    """
    backup_dir = Path(backup_dir)
    db_files = sorted(
        (
            p for p in backup_dir.iterdir()
            if p.is_file() and _BACKUP_NAME.match(p.name)
        ),
        key=lambda p: p.stat().st_mtime,
    )

    last_good = read_last_good(backup_dir)
    protected: set[str] = set()
    if last_good:
        protected.add(Path(last_good).name)

    survivors = db_files[-keep:] if keep > 0 else []
    protected.add(survivors[-1].name) if survivors else None

    to_delete = [p for p in db_files if p not in survivors]
    # Last-good protection may re-add a file keep would have deleted.
    to_delete = [
        p for p in to_delete
        if p.name not in protected
        and (p.name + ".manifest.json") not in protected
    ]

    if not to_delete:
        return {"deleted": [], "kept": [p.name for p in survivors], "protected": sorted(protected)}

    kept_names = [p.name for p in survivors] + [
        p.name for p in db_files if p.name in protected
    ]
    if not kept_names:
        raise RuntimeError(
            "retention refuses to delete: surviving set would be empty"
        )

    deleted = []
    for path in to_delete:
        path.unlink(missing_ok=True)
        deleted.append(path.name)
        Path(str(path) + ".manifest.json").unlink(missing_ok=True)
        Path(str(path) + ".manifest.json.sha256").unlink(missing_ok=True)

    return {"deleted": deleted, "kept": sorted(set(kept_names)), "protected": sorted(protected)}


def read_last_good(backup_dir: Path) -> str | None:
    """Return the last-known-good backup filename, or None."""
    pointer = Path(backup_dir) / LAST_GOOD_NAME
    if not pointer.exists():
        return None
    name = pointer.read_text(encoding="utf-8").strip()
    return name or None


def manifest_checksum_matches(manifest_path: Path) -> bool:
    checksum_file = Path(str(manifest_path) + ".sha256")
    if not checksum_file.exists():
        return False
    expected = checksum_file.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return expected == actual


def verify_backup_set(backup_dir: Path) -> dict:
    """Verify every manifest+checksum+db triple in the directory."""
    results = []
    for manifest_path in sorted(backup_dir.glob("*.manifest.json")):
        db_path = backup_dir / manifest_path.name.replace(".manifest.json", "")
        entry = {
            "manifest": manifest_path.name,
            "checksum_ok": manifest_checksum_matches(manifest_path),
            "db_present": db_path.exists(),
        }
        if db_path.exists():
            entry["integrity_check"] = _integrity_ok(db_path)[0]
        results.append(entry)

    last_good = read_last_good(backup_dir)
    last_good_ok = False
    if last_good:
        lg_path = backup_dir / last_good
        last_good_ok = lg_path.exists() and _integrity_ok(lg_path)[0]

    return {"backups": results, "last_good": last_good, "last_good_ok": last_good_ok}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, help="live database path (read-only use)")
    parser.add_argument("--backup-dir", type=Path, help="backup directory")
    parser.add_argument("--keep", type=int, default=7, help="keep-newest-N (default 7)")
    parser.add_argument("--verify-dir", type=Path, help="verify an existing backup set")
    parser.add_argument(
        "--no-compare-source",
        action="store_true",
        help="skip source row-count comparison (live DB under write load)",
    )
    args = parser.parse_args(argv)

    if args.verify_dir:
        report = verify_backup_set(args.verify_dir)
        print(json.dumps(report, indent=2))
        return 0 if report["last_good_ok"] or not report["backups"] else 1

    if not args.source or not args.backup_dir:
        parser.error("--source and --backup-dir are required (or --verify-dir)")

    try:
        result = run_backup_job(
            source=args.source,
            backup_dir=args.backup_dir,
            keep=args.keep,
            compare_source=not args.no_compare_source,
        )
    except RuntimeError as error:
        print(f"BACKUP FAILED: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
