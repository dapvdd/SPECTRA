"""Batch 014 guarded apply.

Inserts new CPU hardware records (Intel 14th-gen Core, Intel Core Ultra
Series 1/2, AMD Ryzen 8000/9000/Ryzen AI 300) plus their ``cpu_specifications``
row and field-level provenance from the reviewed candidate inventory produced
by ``build_candidates.py``.

Guarantees
----------
* Dry-run by default. Nothing is written unless ``--apply`` is passed.
* A recoverable, verified backup of the database is written before any write.
* All writes happen inside a single ``BEGIN IMMEDIATE`` transaction.
* Only INSERTs are performed. No existing row is ever updated or deleted, so
  no existing specification value can be overwritten.
* Matching is by exact canonical name + manufacturer + type. Any candidate
  whose canonical name already exists is skipped, which makes re-runs safe and
  idempotent (no duplicate hardware rows, no repeat updates).
* Field provenance inserts use ``INSERT OR IGNORE`` against the partial unique
  index, so re-running the same evidence never duplicates provenance rows.
* The number of inserted hardware rows is verified against ``--expect`` (when
  given) before the transaction is committed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone

BATCH_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = r"C:\SPECTRA\data\spectra.db"
BACKUP_DIR = r"C:\SPECTRA\data\backups"
CANDIDATES = os.path.join(BATCH_DIR, "_candidates.json")

SOURCE_ID = 5  # Wikipedia (English)
LICENSE_NAME = "CC BY-SA 4.0"
ATTRIBUTION = "Wikipedia contributors; CC BY-SA 4.0; share-alike applies to derived uses."
ACCESS_DATE = "2026-10-12"
BATCH_NO = 14

SPEC_FIELDS = ["cores", "threads", "base_clock_ghz", "boost_clock_ghz",
               "tdp_w", "process_node_nm", "socket"]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def provenance_value(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return "%.1f" % value
    return str(value)


def make_backup(db_path: str) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.basename(db_path)
    dest = os.path.join(BACKUP_DIR, "%s.batch014-%s.bak" % (base, stamp))
    shutil.copy2(db_path, dest)
    # verify the copy is a usable, intact database of the same logical size
    src = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    dst = sqlite3.connect("file:%s?mode=ro" % dest.replace("\\", "/"), uri=True)
    src_hw = src.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
    dst_hw = dst.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
    dst_ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    src.close()
    dst.close()
    if src_hw != dst_hw or dst_ok != "ok":
        raise SystemExit("backup verification failed: %s (hw %s vs %s, integrity %s)"
                         % (dest, src_hw, dst_hw, dst_ok))
    return dest


def load_candidates():
    with open(CANDIDATES, encoding="utf-8") as f:
        data = json.load(f)
    return data["candidates"]


def already_present(con, cand) -> int | None:
    row = con.execute(
        "SELECT id FROM hardware WHERE type='CPU' AND lower(name)=lower(?) AND manufacturer=?",
        (cand["name"], cand["manufacturer"]),
    ).fetchone()
    return row[0] if row else None


def insert_provenance(con, hardware_id, table_name, field_name, value,
                      cand, notes):
    con.execute(
        """INSERT OR IGNORE INTO field_provenance
           (hardware_id, source_id, table_name, field_name, evidenced_value,
            source_url, license_name, license_notes, attribution, access_date,
            confidence, evidence_status, source_reference, match_method,
            batch_no, notes, recorded_at, benchmark_result_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
        (hardware_id, SOURCE_ID, table_name, field_name, provenance_value(value),
         cand["source_url"], LICENSE_NAME, None, ATTRIBUTION, ACCESS_DATE,
         cand.get("confidence", "high"), "verified", cand["source_section"],
         "exact canonical-name insert (new record; no prior row)", BATCH_NO,
         notes, utcnow()),
    )


def apply(db_path: str, do_apply: bool, expect):
    candidates = load_candidates()
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")

    plan = []
    for cand in candidates:
        plan.append((cand, already_present(con, cand) is not None))

    to_insert = [c for c, present in plan if not present]
    present = [c for c, present in plan if present]

    print("candidates:            %d" % len(candidates))
    print("already present:       %d" % len(present))
    print("to insert:             %d" % len(to_insert))

    if expect is not None and len(to_insert) != expect:
        con.close()
        raise SystemExit("expected %d inserts but planned %d" % (expect, len(to_insert)))

    if not do_apply:
        print("\nDRY RUN: no database changes made. Re-run with --apply to commit.")
        con.close()
        return {"mode": "dry-run", "to_insert": len(to_insert),
                "already_present": len(present)}

    backup = make_backup(db_path)
    print("backup verified at:    %s" % backup)

    before = con.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]

    inserted = 0
    provenance_rows = 0
    try:
        con.execute("BEGIN IMMEDIATE")
        for cand in to_insert:
            if already_present(con, cand) is not None:
                continue
            cur = con.execute(
                """INSERT INTO hardware (name, manufacturer, type, release_date, architecture)
                   VALUES (?,?,?,?,?)""",
                (cand["name"], cand["manufacturer"], "CPU",
                 cand["release_date"], cand["architecture"]),
            )
            hid = cur.lastrowid
            con.execute(
                """INSERT INTO cpu_specifications
                   (hardware_id, cores, threads, base_clock_ghz, boost_clock_ghz,
                    tdp_w, process_node_nm, socket)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (hid, cand["cores"], cand["threads"], cand["base_clock_ghz"],
                 cand["boost_clock_ghz"], cand["tdp_w"], cand["process_node_nm"],
                 cand["socket"]),
            )
            note = "Per-model row in the Wikipedia table section '%s'." % cand["source_section"]
            insert_provenance(con, hid, "hardware", "architecture",
                              cand["architecture"], cand, note)
            if cand["release_date"]:
                insert_provenance(con, hid, "hardware", "release_date",
                                  cand["release_date"], cand, note)
            for f in SPEC_FIELDS:
                if cand.get(f) is not None:
                    insert_provenance(con, hid, "cpu_specifications", f,
                                      cand[f], cand, note)
            inserted += 1
            provenance_rows += 1 + (1 if cand["release_date"] else 0) + \
                sum(1 for f in SPEC_FIELDS if cand.get(f) is not None)

        after = con.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
        if after - before != inserted:
            raise SystemExit("in-transaction verification failed: inserted %d but delta %d"
                             % (inserted, after - before))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    con.close()
    print("\ncommitted:             %d hardware + %d spec + %d provenance rows"
          % (inserted, inserted, provenance_rows))
    return {"mode": "apply", "inserted": inserted, "provenance": provenance_rows,
            "backup": backup, "before": before, "after": after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually write to the database (default: dry run)")
    ap.add_argument("--db", default=DEFAULT_DB,
                    help="path to the SQLite database")
    ap.add_argument("--expect", type=int, default=None,
                    help="expected number of inserts; abort if it differs")
    args = ap.parse_args()

    result = apply(db_path=args.db, do_apply=args.apply, expect=args.expect)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
