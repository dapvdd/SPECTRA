"""Data-integrity check for the SPECTRA SQLite database.

Runs against SPECTRA_DATABASE_URL (defaults to data/spectra.db) and verifies:
1. PRAGMA quick_check — confirms the DB file is not corrupted.
2. PRAGMA foreign_key_check — confirms referential integrity.
3. Expected minimum row counts (detects accidental truncation during import).

Exits 0 on pass, 1 on any failure. Does NOT write anything; read-only.

Usage::

    python backend/app/scripts/check_data_integrity.py
    python backend/app/scripts/check_data_integrity.py --database data/spectra_copy.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Minimum expected row counts based on the Batch 018 audit baseline.
# Any count below these thresholds indicates a truncated import and must block
# promotion, even if integrity_check passes (SQLite can be internally consistent
# yet incomplete). These are not hard coverage targets — they reflect the
# minimum that proves a full rehearsal ran.
_MIN_ROW_COUNTS = {
    "hardware": 4500,
    "sources": 5,
    "benchmark_results": 800,
    "field_provenance": 1000,
}


def check_database(path: Path) -> dict:
    """Run all integrity checks; return results dict."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")

    checks: dict = {}

    # 1. quick_check
    try:
        quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        checks["quick_check"] = quick
    except sqlite3.Error as e:
        checks["quick_check"] = f"ERROR: {e}"

    # 2. foreign_key_check
    try:
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        checks["foreign_key_check_violations"] = len(fk_rows)
        checks["foreign_key_check_detail"] = [
            dict(zip([c[0] for c in conn.execute("PRAGMA foreign_key_check")], r))
            for r in fk_rows
        ] if fk_rows else []
    except sqlite3.Error as e:
        checks["foreign_key_check_violations"] = f"ERROR: {e}"

    # 3. Row counts
    counts = {}
    for table, minimum in _MIN_ROW_COUNTS.items():
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.Error:
            n = -1
        counts[table] = n

    checks["row_counts"] = counts
    checks["row_counts_minimum"] = _MIN_ROW_COUNTS

    conn.close()
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.getenv(
            "SPECTRA_DATABASE_URL",
            str(PROJECT_ROOT / "data" / "spectra.db"),
        ),
        help="Path to the database (default: SPECTRA_DATABASE_URL or data/spectra.db).",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help=(
            "Skip the row-count floor. Use for a freshly-initialized schema "
            "(e.g. in CI where the production database is not committed and a "
            "fresh DB legitimately has 0 rows). quick_check and FK integrity "
            "are still enforced."
        ),
    )
    args = parser.parse_args()
    target = Path(args.database)

    # Handle sqlite:// URLs from SQLAlchemy.
    if "sqlite://" in args.database:
        target = Path(args.database.replace("sqlite:///", ""))

    if not target.exists():
        print(f"ERROR: database not found: {target}")
        return 1

    import json

    result = check_database(target)
    print(json.dumps(result, indent=2, default=str))

    # Evaluation: pass only if quick_check is 'ok', FK violations == 0,
    # and (unless schema-only) every table meets its minimum.
    passed = True

    if result["quick_check"] != "ok":
        print(f"\nFAIL: quick_check = {result['quick_check']}")
        passed = False

    if result["foreign_key_check_violations"] != 0:
        print(f"\nFAIL: {result['foreign_key_check_violations']} FK violations")
        passed = False

    if not args.schema_only:
        for table, minimum in _MIN_ROW_COUNTS.items():
            n = result["row_counts"].get(table, -1)
            if n < minimum:
                print(f"\nFAIL: {table} has {n} rows (minimum {minimum})")
                passed = False
    else:
        print("schema-only: row-count floor skipped (fresh/empty schema expected)")

    print(f"\n{'PASS' if passed else 'FAIL'}: data-integrity check")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
