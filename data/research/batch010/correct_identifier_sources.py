"""Correct external_identifiers source associations proven wrong in batch 010.

Every external identifier currently has source_id=1 (PassMark). The audit in
identifier_source_audit.py proves with value-level evidence that they originate
in the Intel ARK / AMD specification exports:

- all 2,675 intel_cpu_id values are present in intel-cpus.csv's CpuId column
  and absent from the PassMark catalog's URL id namespace;
- all 900 product_id_* values are present in amd-cpus.csv's Product ID
  columns;
- every identifier sits on a hardware entity whose manufacturer matches the
  identified namespace (Intel ids on Intel CPUs, product ids on AMD CPUs).

Safety:
- requires a verified pre-mutation backup (path passed in),
- guarded per-row UPDATE (WHERE source_id=1) inside one transaction,
- hard expected-count rollback (2,675 -> source 8, 900 -> source 9),
- no identifier value, hardware relationship or hardware entity is modified,
- the unique constraint is the final duplicate guard,
- re-running is a no-op (rows already corrected are skipped).

Usage (after backup + schema upgrade):

    python data/research/batch010/correct_identifier_sources.py \
        --backup data/backups/<pre-correction>.db
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.identifier_source import (  # noqa: E402
    AMD_CSV_SOURCE_NAME,
    INTEL_CSV_SOURCE_NAME,
)

BATCH_DIR = REPO_ROOT / "data" / "research" / "batch010"
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"
PATCH = BATCH_DIR / "id_audit_patch.csv"

EXPECTED_TARGETS = {
    INTEL_CSV_SOURCE_NAME: 2675,
    AMD_CSV_SOURCE_NAME: 900,
}


def verify_backup(path: Path, live: Path) -> str:
    def sha256(p: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with open(p, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()

    if not path.is_file():
        raise SystemExit(f"backup not found: {path}")
    backup_hash = sha256(path)
    connection = sqlite3.connect(path)
    quick = connection.execute("PRAGMA quick_check").fetchone()[0]
    connection.close()
    if quick != "ok":
        raise SystemExit(f"backup quick_check failed: {quick}")
    print(f"backup verified: {path.name} sha256={backup_hash} quick_check=ok")
    return backup_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, help="pre-mutation backup path")
    parser.add_argument("--database", default=None, help="database path")
    arguments = parser.parse_args()

    database = Path(arguments.database) if arguments.database else DEFAULT_DB
    verify_backup(Path(arguments.backup), database)

    with open(PATCH, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    expected = Counter(r["expected_source_name"] for r in rows)
    print(f"patch rows: {len(rows)}; expected by target: {dict(expected)}")
    if dict(expected) != EXPECTED_TARGETS:
        raise SystemExit(f"unexpected patch composition: {dict(expected)}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")

    # resolve registered source names to ids in THIS database (robust): the
    # batch 009 loader registered these names; ids are resolved, not assumed.
    source_ids = {
        r[1]: r[0]
        for r in connection.execute("SELECT id, name FROM sources")
    }
    for name in EXPECTED_TARGETS:
        if name not in source_ids:
            raise SystemExit(f"registered source missing: {name}")
    target_ids = {name: source_ids[name] for name in EXPECTED_TARGETS}
    print(f"resolved targets: {target_ids}")

    # every patch row must carry a recognized target source name
    expected_id_by_type = {}
    for row in rows:
        name = row["expected_source_name"]
        if name not in target_ids:
            raise SystemExit(f"unexpected target source in patch: {name}")
        expected_id_by_type.setdefault(row["identifier_type"], target_ids[name])

    before_by_source = {
        r[0]: r[1]
        for r in connection.execute(
            "SELECT source_id, COUNT(*) FROM external_identifiers"
            " GROUP BY source_id"
        )
    }
    print(f"before sources: {before_by_source}")

    updated = 0
    try:
        connection.execute("BEGIN")
        for row in rows:
            cursor = connection.execute(
                "UPDATE external_identifiers SET source_id = ?"
                " WHERE id = ? AND source_id = 1",
                (target_ids[row["expected_source_name"]], int(row["identifier_id"])),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"unexpected rowcount {cursor.rowcount} for identifier"
                    f" {row['identifier_id']}"
                )
            updated += 1

        if updated != len(rows):
            raise RuntimeError(f"expected {len(rows)} updates, applied {updated}")

        # guard: no duplicate identity across the whole table
        dupes = connection.execute(
            "SELECT COUNT(*) FROM (SELECT hardware_id, source_id,"
            " identifier_type, external_id, COUNT(*) c"
            " FROM external_identifiers GROUP BY 1, 2, 3, 4 HAVING c > 1)"
        ).fetchone()[0]
        if dupes:
            raise RuntimeError(f"duplicate identity rows detected: {dupes}")

        # guard: identifier values and hardware links untouched
        integrity = connection.execute("SELECT COUNT(*) FROM external_identifiers").fetchone()[0]
        if integrity != 3575:
            raise RuntimeError(f"row count changed: {integrity}")

        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        connection.close()
        raise

    after_by_source = {
        r[0]: r[1]
        for r in connection.execute(
            "SELECT source_id, COUNT(*) FROM external_identifiers"
            " GROUP BY source_id"
        )
    }
    connection.close()

    print(f"updated rows: {updated}")
    print(f"after sources: {after_by_source}")
    if after_by_source.get(1) is not None:
        raise SystemExit("source 1 still holds identifiers")
    print("identifier source correction applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())