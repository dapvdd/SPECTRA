"""Consistent SQLite backup for SPECTRA.

Copies the live database using SQLite's Online Backup API (``sqlite3``
Connection.backup), which produces a consistent snapshot even while the
source is being written and is WAL-aware (it checkpoints and copies the WAL
content, unlike a raw file copy).

Verification
------------
Every backup is verified before being reported as good:

- ``PRAGMA integrity_check`` returns ``ok``.
- ``PRAGMA foreign_key_check`` returns no violations (when the source has
  foreign keys enabled).
- Row counts of the core tables match the source at snapshot time.

Usage::

    # Backup the container's DB to a file (run inside the container, or point
    # --source at any reachable path):
    python -m backend.app.scripts.backup_database \
        --source /app/data/spectra.db \
        --output /backups/spectra_backup_<ts>.db

    # Verify an existing backup without creating a new one:
    python -m backend.app.scripts.backup_database \
        --verify-only --output /backups/spectra_backup_<ts>.db

Exit codes: 0 = backup created and verified; 1 = verification failed;
2 = usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# Tables whose row counts are compared between source and backup. These are
# the core SPECTRA tables; adding a table later means adding it here.
_COUNTED_TABLES = (
    "hardware",
    "cpu_specifications",
    "gpu_specifications",
    "benchmark_results",
    "sources",
    "build_conversations",
    "build_messages",
    "users",
)


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA256 of a file, streamed in 1 MiB chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        counts: dict[str, int] = {}
        for table in _COUNTED_TABLES:
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                counts[table] = count
            except sqlite3.OperationalError:
                # Table does not exist in this schema (e.g. pre-v2 backup
                # without a users table). Report as -1 so the comparison is
                # meaningful either way.
                counts[table] = -1
        return counts
    finally:
        conn.close()


def _integrity_ok(db_path: Path) -> tuple[bool, str]:
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return result == "ok", result
    finally:
        conn.close()


def _foreign_keys_ok(db_path: Path) -> tuple[bool, list]:
    conn = sqlite3.connect(db_path)
    try:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        return len(violations) == 0, violations
    finally:
        conn.close()


def create_backup(source: Path, output: Path, *, compare_source: bool = True) -> dict:
    """Create a consistent backup of ``source`` at ``output`` and verify it.

    When ``compare_source`` is True (default), row counts in the backup are
    compared against the source after the copy — a strong end-to-end check
    for a quiet database. For a live database under active writes the source
    keeps moving, so pass ``compare_source=False`` and rely on the backup's
    own integrity verification.

    Returns a result dict with paths, sha256, integrity status, foreign-key
    status, and row counts. Raises ``RuntimeError`` on verification failure.
    """
    if not source.exists():
        raise FileNotFoundError(f"source database not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)

    # Remove a stale target so a failed backup can never be mistaken for a
    # successful one.
    if output.exists():
        output.unlink()

    # Online Backup API: consistent under concurrent writes, WAL-aware.
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(output)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()

    return verify_backup(
        output, source=source if compare_source else None
    )


def verify_backup(backup: Path, *, source: Path | None = None) -> dict:
    """Verify a backup file. When ``source`` is given, row counts are
    compared against it as well."""
    result: dict = {"backup": str(backup)}

    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup}")

    result["sha256"] = sha256_of(backup)
    result["size_bytes"] = backup.stat().st_size

    integrity_ok, integrity_detail = _integrity_ok(backup)
    result["integrity_check"] = integrity_detail
    if not integrity_ok:
        raise RuntimeError(f"integrity_check failed: {integrity_detail}")

    fk_ok, fk_violations = _foreign_keys_ok(backup)
    result["foreign_key_check"] = "ok" if fk_ok else f"{len(fk_violations)} violations"
    if not fk_ok:
        raise RuntimeError(f"foreign_key_check failed: {fk_violations}")

    backup_counts = _row_counts(backup)
    result["row_counts"] = backup_counts

    if source is not None and source.exists():
        source_counts = _row_counts(source)
        mismatched = {
            table: (source_counts.get(table), backup_counts.get(table))
            for table in set(source_counts) | set(backup_counts)
            if source_counts.get(table) != backup_counts.get(table)
        }
        result["source_row_counts"] = source_counts
        if mismatched:
            raise RuntimeError(f"row-count mismatch vs source: {mismatched}")
        result["row_counts_match_source"] = True

    result["verified_at"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consistent, verified SQLite backup for SPECTRA.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Live database path (omit with --verify-only).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Backup file path (created) or existing backup (with --verify-only).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing backup instead of creating a new one.",
    )
    args = parser.parse_args()

    import json

    try:
        if args.verify_only:
            result = verify_backup(args.output)
        else:
            if args.source is None:
                print("ERROR: --source is required without --verify-only.", file=sys.stderr)
                return 2
            result = create_backup(args.source, args.output)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"BACKUP FAILED: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
