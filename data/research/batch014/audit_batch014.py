"""Batch 014 independent audit.

Reads the live database and (optionally) the pre-apply backup and independently
verifies the Batch 014 insert patch:

1. database integrity and referential integrity;
2. every reviewed candidate exists exactly once with the expected fields;
*  a matching ``cpu_specifications`` row;
*  field-level provenance for every inserted specification value;
* no existing row was overwritten (shared ids are byte-for-byte unchanged
  across every hardware/spec column we control) and nothing was deleted;
* no duplicate CPU hardware records were introduced;
* the patch is idempotent (a dry-run re-apply would insert nothing).

Usage::

    python audit_batch014.py --db <current.db> --before <backup.db> [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3

BATCH_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = r"C:\SPECTRA\data\spectra.db"
CANDIDATES = os.path.join(BATCH_DIR, "_candidates.json")

SPEC_FIELDS = ["cores", "threads", "base_clock_ghz", "boost_clock_ghz",
               "tdp_w", "process_node_nm", "socket"]
HW_FIELDS = ["name", "manufacturer", "type", "release_date", "architecture"]


def connect_ro(path):
    p = path.replace("\\", "/")
    con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
    con.row_factory = sqlite3.Row
    return con


def load_candidates():
    with open(CANDIDATES, encoding="utf-8") as f:
        return json.load(f)["candidates"]


def rows_equal(a, b, fields):
    for f in fields:
        if a[f] != b[f]:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--before", default=None)
    ap.add_argument("--json", default=os.path.join(BATCH_DIR, "_audit_result.json"))
    args = ap.parse_args()

    candidates = load_candidates()
    after = connect_ro(args.db)
    failures = []
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    # 1. integrity
    integ = after.execute("PRAGMA integrity_check").fetchone()[0]
    check("integrity_check", integ == "ok", integ)
    fk = after.execute("PRAGMA foreign_key_check").fetchall()
    check("foreign_key_check", len(fk) == 0, "%d violations" % len(fk))

    # counts
    def count(con, table):
        return con.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]

    counts = {
        "hardware": count(after, "hardware"),
        "cpu": after.execute("SELECT COUNT(*) FROM hardware WHERE type='CPU'").fetchone()[0],
        "cpu_specifications": count(after, "cpu_specifications"),
        "field_provenance": count(after, "field_provenance"),
        "external_identifiers": count(after, "external_identifiers"),
        "benchmark_results": count(after, "benchmark_results"),
        "build_conversations": count(after, "build_conversations"),
    }

    # 2. every candidate present with matching spec + provenance
    found = 0
    spec_mismatch = []
    prov_missing = []
    hw_mismatch = []
    for c in candidates:
        row = after.execute(
            "SELECT * FROM hardware WHERE type='CPU' AND lower(name)=lower(?) AND manufacturer=?",
            (c["name"], c["manufacturer"]),
        ).fetchone()
        if row is None:
            hw_mismatch.append("%s: missing" % c["name"])
            continue
        found += 1
        if row["release_date"] != c["release_date"] or row["architecture"] != c["architecture"]:
            hw_mismatch.append("%s: hw fields differ" % c["name"])
        spec = after.execute("SELECT * FROM cpu_specifications WHERE hardware_id=?",
                             (row["id"],)).fetchone()
        if spec is None:
            spec_mismatch.append("%s: no spec row" % c["name"])
        else:
            for f in SPEC_FIELDS:
                if spec[f] != c.get(f):
                    spec_mismatch.append("%s.%s: %r != %r" % (c["name"], f, spec[f], c.get(f)))
        expected = [("hardware", "architecture", c["architecture"])]
        if c["release_date"]:
            expected.append(("hardware", "release_date", c["release_date"]))
        for f in SPEC_FIELDS:
            if c.get(f) is not None:
                expected.append(("cpu_specifications", f, c[f]))
        have = after.execute(
            "SELECT table_name, field_name FROM field_provenance "
            "WHERE hardware_id=? AND batch_no=14 AND evidence_status='verified'",
            (row["id"],),
        ).fetchall()
        have_set = {(h["table_name"], h["field_name"]) for h in have}
        for tn, fn, _v in expected:
            if (tn, fn) not in have_set:
                prov_missing.append("%s: %s.%s" % (c["name"], tn, fn))

    check("candidates_present", found == len(candidates) and not hw_mismatch,
          "%d/%d present; %s" % (found, len(candidates), "; ".join(hw_mismatch[:5])))
    check("specs_match", not spec_mismatch, "; ".join(spec_mismatch[:5]) or "all match")
    check("provenance_complete", not prov_missing, "; ".join(prov_missing[:5]) or "all present")

    # 3. no duplicate CPU names
    dups = after.execute(
        "SELECT lower(name) n, manufacturer m, COUNT(*) c FROM hardware "
        "WHERE type='CPU' GROUP BY lower(name), manufacturer HAVING c > 1").fetchall()
    check("no_duplicate_cpu_names", len(dups) == 0, "%d duplicate groups" % len(dups))

    # 4. before/after reconcile (if a backup is supplied)
    reconcile = {}
    if args.before:
        before = connect_ro(args.before)
        b_ids = {r["id"] for r in before.execute("SELECT id FROM hardware")}
        a_ids = {r["id"] for r in after.execute("SELECT id FROM hardware")}
        deleted = b_ids - a_ids
        added = a_ids - b_ids
        check("no_deletions", not deleted, "%d hardware ids removed" % len(deleted))
        check("added_count", len(added) == len(candidates),
              "%d added (expected %d)" % (len(added), len(candidates)))

        # no existing hardware row changed
        changed = []
        shared = b_ids & a_ids
        b_hw = {r["id"]: r for r in before.execute("SELECT * FROM hardware")}
        a_hw = {r["id"]: r for r in after.execute("SELECT * FROM hardware")}
        for i in shared:
            if not rows_equal(b_hw[i], a_hw[i], HW_FIELDS):
                changed.append(i)
        check("no_hardware_rows_modified", not changed, "%d modified" % len(changed))

        # no existing cpu_specifications row changed / removed
        b_spec = {r["hardware_id"]: r for r in before.execute("SELECT * FROM cpu_specifications")}
        a_spec = {r["hardware_id"]: r for r in after.execute("SELECT * FROM cpu_specifications")}
        spec_changed = [h for h in b_spec if h in a_spec and
                        not rows_equal(b_spec[h], a_spec[h], SPEC_FIELDS)]
        spec_removed = [h for h in b_spec if h not in a_spec]
        check("no_specs_modified", not spec_changed, "%d modified" % len(spec_changed))
        check("no_specs_removed", not spec_removed, "%d removed" % len(spec_removed))

        # provenance and other tables preserved
        check("no_provenance_lost",
              count(after, "field_provenance") >= count(before, "field_provenance"),
              "%d -> %d" % (count(before, "field_provenance"), count(after, "field_provenance")))
        check("benchmarks_preserved",
              count(after, "benchmark_results") == count(before, "benchmark_results"))
        check("external_ids_preserved",
              count(after, "external_identifiers") == count(before, "external_identifiers"))
        check("build_conversations_preserved",
              count(after, "build_conversations") == count(before, "build_conversations"))
        reconcile = {"before_ids": len(b_ids), "after_ids": len(a_ids),
                     "added": len(added), "deleted": len(deleted)}

    # 5. idempotency: a fresh apply run should plan zero inserts
    planned = 0
    for c in candidates:
        if after.execute(
                "SELECT 1 FROM hardware WHERE type='CPU' AND lower(name)=lower(?) AND manufacturer=?",
                (c["name"], c["manufacturer"])).fetchone() is None:
            planned += 1
    check("idempotent_rerun", planned == 0, "%d would be re-inserted" % planned)

    # provenance batch counts
    prov_batch = after.execute(
        "SELECT COUNT(*) FROM field_provenance WHERE batch_no=14").fetchone()[0]
    by_family = {}
    for c in candidates:
        by_family[c["table"]] = by_family.get(c["table"], 0) + 1

    result = {
        "db": args.db,
        "before": args.before,
        "counts": counts,
        "provenance_batch14": prov_batch,
        "candidates": len(candidates),
        "candidates_by_table": by_family,
        "reconcile": reconcile,
        "checks": checks,
        "failures": failures,
        "passed": not failures,
    }
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps({k: result[k] for k in
                      ["counts", "provenance_batch14", "candidates",
                       "reconcile", "failures", "passed"]}, indent=2))
    print("\nchecks:")
    for c in checks:
        print("  [%s] %s %s" % ("PASS" if c["ok"] else "FAIL", c["check"], c["detail"]))

    after.close()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
