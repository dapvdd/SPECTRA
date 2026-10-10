"""Snapshot database state for the Batch 009 independent audit.

Writes a JSON state file capturing the database SHA-256, integrity results,
table row counts, and a full row dump of every data table. Used before and
after the provenance load so the independent audit can prove that the only
changes are additive and within scope.

Usage:
    python data/research/batch009/snapshot_state.py --out <path.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"

TABLES = [
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


def full_table(con: sqlite3.Connection, name: str) -> tuple:
    rows = con.execute(f'select * from "{name}"').fetchall()
    headers = [desc[0] for desc in con.execute(f'select * from "{name}"').description]
    return headers, rows


def snapshot(database: Path, out_path: Path) -> dict:
    con = sqlite3.connect(database)
    state = {
        "database": str(database),
        "sha256": sha256(database),
        "quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
        "foreign_key_check": con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall(),
        "tables": {
            name: con.execute(f'select count(*) from "{name}"').fetchone()[0]
            for name in TABLES
            if con.execute(
                "select name from sqlite_master"
                " where type='table' and name=?",
                (name,),
            ).fetchone() is not None
        },
        "full_dumps": {
            name: [list(row) for row in full_table(con, name)[1]]
            for name in TABLES
            if con.execute(
                "select name from sqlite_master"
                " where type='table' and name=?",
                (name,),
            ).fetchone() is not None
        },
    }
    con.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(state, indent=2, default=str), encoding="utf-8"
    )
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