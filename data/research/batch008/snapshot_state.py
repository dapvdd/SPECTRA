"""Snapshot database state for the Batch 008 independent audit.

Writes a JSON state file capturing the database SHA-256, integrity result,
table row counts, and every non-null hardware/specification value. Used
before and after the provenance migration so the independent audit can
prove the only changes are additive (new table, new source rows, no value
ever changed).

Usage:
    python data/research/batch008/snapshot_state.py --out <path.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"

TABLE_COUNTS = [
    "hardware",
    "cpu_specifications",
    "gpu_specifications",
    "benchmark_results",
    "external_identifiers",
    "sources",
    "field_provenance",
    "build_conversations",
    "build_messages",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_spec_values(con: sqlite3.Connection, table: str) -> dict:
    columns = [
        row[1] for row in con.execute(f"PRAGMA table_info({table})")
        if row[1] not in ("id", "hardware_id")
    ]
    return {
        column: [
            con.execute(
                f'select "{column}" from "{table}" where "{column}" is not null'
            ).fetchall()
        ][0]
        for column in columns
    }


def snapshot(database: Path, out_path: Path) -> dict:
    con = sqlite3.connect(database)
    state = {
        "database": str(database),
        "sha256": sha256(database),
        "quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
        "tables": {
            name: con.execute(f'select count(*) from "{name}"').fetchone()[0]
            for name in TABLE_COUNTS
            if con.execute(
                "select name from sqlite_master"
                " where type='table' and name=?",
                (name,),
            ).fetchone() is not None
        },
        "spec_values": {table: snapshot_spec_values(con, table)
                        for table in ("hardware", "cpu_specifications",
                                      "gpu_specifications")},
    }
    con.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state, indent=2, default=str),
                        encoding="utf-8")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--database", default=None, help="database path")
    arguments = parser.parse_args()
    database = Path(arguments.database) if arguments.database else DEFAULT_DB
    state = snapshot(database, Path(arguments.out))
    print(f"snapshot written: {arguments.out}")
    print(f"  sha256: {state['sha256']}")
    print(f"  quick_check: {state['quick_check']}")
    print(f"  tables: {state['tables']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())