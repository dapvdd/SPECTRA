"""Restore rehearsal and backup retention for SPECTRA.

Restore rehearsal (M3.2)
------------------------
A backup is only as good as its last successful restore. This script
rehearses a restore against a DISPOSABLE target: it copies the backup to a
scratch location, verifies integrity/foreign-keys/row counts there, and
leaves the live database untouched. It never writes to a production
database path.

Retention (M3.1)
----------------
``prune`` mode enforces a keep-last-N policy over a backup directory,
deleting only files matching the SPECTRA backup naming pattern
(``backup*.db`` / ``spectra_backup*.db``). It refuses to delete anything
when the surviving set would be empty, and never touches files outside the
given directory.

Usage::

    # Rehearse a restore of a backup to a disposable target:
    python -m backend.app.scripts.restore_rehearsal \
        --backup /backups/spectra_backup_20261110.db \
        --target /tmp/restore_rehearsal.db

    # Prune old backups, keeping the newest 7:
    python -m backend.app.scripts.restore_rehearsal \
        --prune /backups --keep 7

Exit codes: 0 = rehearsal passed / prune done; 1 = verification failed;
2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

from backend.app.scripts.backup_database import (
    _COUNTED_TABLES,
    _integrity_ok,
    _foreign_keys_ok,
    _row_counts,
    sha256_of,
)


_BACKUP_NAME = re.compile(r"(?:backup|spectra_backup).*\.db$", re.IGNORECASE)


def restore_rehearsal(backup: Path, target: Path) -> dict:
    """Copy ``backup`` to the disposable ``target`` and verify it there.

    This exercises the real restore path (file copy into place) plus full
    verification, without touching any live database. The target directory
    is created if needed; an existing target file is overwritten (it is
    disposable by definition).
    """
    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup}")

    if target.resolve() == backup.resolve():
        raise ValueError("restore target must differ from the backup file")

    target.parent.mkdir(parents=True, exist_ok=True)

    # Guard: refuse targets that look like a live app database path. A
    # rehearsal writes only to scratch files.
    forbidden = re.compile(r"/app/data/spectra\.db$|data[/\\]spectra\.db$")
    if forbidden.search(str(target)):
        raise ValueError(
            f"refusing to rehearse against a live-looking path: {target}"
        )

    # File-copy restore (the realistic recovery action: put the backup file
    # where the app expects it). Verification then proves the copy is sound.
    shutil.copy2(backup, target)

    result: dict = {
        "backup": str(backup),
        "restored_to": str(target),
        "backup_sha256": sha256_of(backup),
        "restored_sha256": sha256_of(target),
    }
    if result["backup_sha256"] != result["restored_sha256"]:
        raise RuntimeError(
            "restore copy mismatch: restored file differs from backup"
        )

    integrity_ok, integrity_detail = _integrity_ok(target)
    result["integrity_check"] = integrity_detail
    if not integrity_ok:
        raise RuntimeError(f"restored DB integrity_check failed: {integrity_detail}")

    fk_ok, fk_violations = _foreign_keys_ok(target)
    result["foreign_key_check"] = "ok" if fk_ok else f"{len(fk_violations)} violations"
    if not fk_ok:
        raise RuntimeError(f"restored DB foreign_key_check failed: {fk_violations}")

    counts = _row_counts(target)
    result["row_counts"] = counts

    # The restore must contain the core catalog at plausible volume: an empty
    # hardware table after a restore of a production backup means the copy
    # went somewhere wrong.
    if counts.get("hardware", -1) <= 0:
        raise RuntimeError(
            "restored DB has no hardware rows — refusing to call this a "
            "successful restore"
        )

    result["verdict"] = "restore_rehearsal_passed"
    return result


def prune_backups(directory: Path, keep: int) -> dict:
    """Keep the newest ``keep`` backup files in ``directory``, delete the rest.

    Only files matching the SPECTRA backup naming pattern are candidates.
    Refuses when ``keep`` < 1 or when the directory holds no candidates.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")

    candidates = sorted(
        (p for p in directory.iterdir() if p.is_file() and _BACKUP_NAME.match(p.name)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no backup files found in {directory}")

    survivors = candidates[:keep]
    expired = candidates[keep:]

    for path in expired:
        path.unlink()

    return {
        "directory": str(directory),
        "kept": [p.name for p in survivors],
        "pruned": [p.name for p in expired],
        "kept_count": len(survivors),
        "pruned_count": len(expired),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore rehearsal (disposable target) and backup retention.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--backup", type=Path, help="Backup file to rehearse with.")
    parser.add_argument(
        "--target", type=Path, help="Disposable restore target path."
    )
    parser.add_argument(
        "--prune", type=Path, help="Backup directory to prune (keep-newest-N)."
    )
    parser.add_argument(
        "--keep", type=int, default=7, help="Backups to keep when pruning (default 7)."
    )
    args = parser.parse_args()

    try:
        if args.prune is not None:
            result = prune_backups(args.prune, args.keep)
        elif args.backup is not None and args.target is not None:
            result = restore_rehearsal(args.backup, args.target)
        else:
            print(
                "ERROR: provide --backup + --target, or --prune.", file=sys.stderr
            )
            return 2
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"REHEARSAL FAILED: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
