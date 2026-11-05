"""Stage 7 — data-integrity drill against the dev copy.

Rehearses the production integrity contract (quick_check, FK check, minimum
row counts) against the isolated dev database copy — the same checks that
gate production promotion — and returns a deterministic verdict dict.

Contract:
- ``integrity_verdict(db_path) -> dict`` with ``quick_check``,
  ``foreign_key_check_violations``, ``row_counts``, ``min_met``,
  ``schema_present`` and an overall ``verdict`` (``PASS`` | ``FAIL``).
- ``curated_counts(db_path)`` counts the mission-relevant tables on any path
  (used to prove the dev copy matches the Stage 0 baseline).
- Read-only: never writes to the checked database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.scripts.check_data_integrity import (
    _MIN_ROW_COUNTS,
    check_database,
)

# Mission-relevant tables whose counts the drill surface explicitly.
_CURATED_TABLES = (
    "hardware",
    "cpu_specifications",
    "gpu_specifications",
    "benchmark_results",
    "sources",
    "field_provenance",
    "external_identifiers",
)


def _schema_tables(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def curated_counts(db_path: str) -> dict:
    """Row counts for the curated mission tables on ``db_path`` (read-only)."""
    conn = sqlite3.connect(db_path)
    counts: dict = {}
    try:
        for table in _CURATED_TABLES:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                n = None
            counts[table] = n
    finally:
        conn.close()
    return counts


def integrity_verdict(db_path: str) -> dict:
    """Run the integrity contract on ``db_path``; return a deterministic verdict.

    Uses the same primitives as ``check_data_integrity.check_database`` plus a
    schema-presence check. Never writes to the database. If ``db_path`` does not
    exist, raises ``FileNotFoundError`` — the drill must refuse a missing path
    instead of letting SQLite create an empty file.
    """
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    check = check_database(path)

    tables = _schema_tables(db_path)
    schema_present = {
        "tables": tables,
        "expected": sorted(_MIN_ROW_COUNTS),
        "complete": all(t in tables for t in _MIN_ROW_COUNTS),
    }

    min_met: dict = {}
    for table, minimum in _MIN_ROW_COUNTS.items():
        n = check["row_counts"].get(table, 0)
        min_met[table] = bool(n >= minimum)

    quick_ok = check["quick_check"] == "ok"
    fk_ok = check["foreign_key_check_violations"] == 0
    all_min = all(min_met.values())

    verdict = "PASS" if (quick_ok and fk_ok and all_min) else "FAIL"

    return {
        "target": db_path,
        "quick_check": check["quick_check"],
        "foreign_key_check_violations": check["foreign_key_check_violations"],
        "row_counts": check["row_counts"],
        "row_counts_minimum": dict(_MIN_ROW_COUNTS),
        "min_met": min_met,
        "schema_present": schema_present,
        "curated_counts": curated_counts(db_path),
        "verdict": verdict,
    }


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=str(Path(__file__).resolve().parents[3] / "data" / "dev" / "spectra_dev.db"),
        help="Dev DB path to drill (default: data/dev/spectra_dev.db).",
    )
    args = parser.parse_args()

    result = integrity_verdict(args.database)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())