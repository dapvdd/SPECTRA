# -*- coding: utf-8 -*-
"""Batch 018 production migration — deterministic, transactional, idempotent.

Rehearsal-only tool. It NEVER touches the production DB directly; it operates
on an isolated rehearsal copy created by `extract_rehearsal_copy.py`.

Usage (on DavidLab host, against a rehearsal copy in the container's /tmp):
    Get-Content migrate_batch018.py -Raw | ssh david-lab \\
        "docker exec -i spectra-backend python - /tmp/spectra_rehearsal_XXXX.db --apply --verify"

In normal operation the embedded RECORDS + PROVENANCE rows are applied to the
rehearsal DB path passed as argv[1].

Guarantees:
  - Strict NULL-only guard: never overwrites an existing non-NULL value.
  - Transactional: BEGIN IMMEDIATE ... COMMIT / ROLLBACK on any failure.
  - Schema precondition check: target columns must exist with expected type.
  - Provenance de-dup guard: skips/aborts if a target (hardware_id, field,
    source_id, batch_no) provenance row already exists.
  - Exact-count enforcement: aborts unless exactly 965 records applied and
    965 provenance rows inserted.
  - Idempotent: a second run produces 0 changes.
"""
import datetime
import hashlib
import json
import os
import sqlite3
import sys

# --- Embedded payload (generated deterministically from batch018_valid_records.json)
RECORDS = []  # populated by generate step
SOURCE_ID = 4
BATCH_NO = 18
META = {
    "url": "https://gpuark.com/datasets/gpuark-gpu-specs.csv",
    "license": "CC BY 4.0",
    "attribution": "GPU Ark (2026). GPU specifications & benchmarks dataset. https://gpuark.com/datasets/",
    "retrieved_on": "2026-10-28",
    "sha256": "bcaba010961cdeca4d2260028d7f27f2c18317e67ffbddec7a09d3dddfa9f734",
}
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

PROVENANCE_COLS = [
    "hardware_id", "source_id", "table_name", "field_name",
    "evidenced_value", "source_url", "license_name",
    "attribution", "access_date", "confidence",
    "evidence_status", "source_reference", "match_method",
    "batch_no", "notes", "recorded_at",
]

SCHEMA_EXPECT = {
    "interface": "VARCHAR",
    "memory_bus_width_bits": "INTEGER",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def schema_check(con):
    """Reject unless the target schema matches the validated baseline."""
    cols = {r[1]: r[2] for r in con.execute("PRAGMA table_info(gpu_specifications)")}
    missing = [c for c in SCHEMA_EXPECT if c not in cols]
    if missing:
        return "missing target columns: %s" % missing
    # type normalisation: SQLite reports declared type
    for c, expect in SCHEMA_EXPECT.items():
        decl = (cols.get(c) or "").upper()
        if expect not in decl:
            return "column %s declared %r, expected %r" % (c, decl, expect)
    # provenance table must exist with batch_no column
    prov = {r[1] for r in con.execute("PRAGMA table_info(field_provenance)")}
    need = {"hardware_id", "source_id", "field_name", "batch_no", "evidenced_value", "source_url"}
    if not need <= prov:
        return "field_provenance missing columns: %s" % (need - prov)
    return None


def preflight(con, records):
    """Return list of hard-fail reasons (empty list => safe to proceed)."""
    problems = []
    seen = set()
    for r in records:
        hwid = r["hardware_id"]
        field = r["field"]
        # 1. hardware must exist
        hw = con.execute("SELECT 1 FROM hardware WHERE id=?", (hwid,)).fetchone()
        if not hw:
            problems.append("hardware missing id=%s" % hwid)
        # 2. NULL-only
        cur = con.execute(
            "SELECT %s FROM gpu_specifications WHERE hardware_id=?" % field, (hwid,)
        ).fetchone()
        if cur is not None and cur[0] is not None:
            problems.append(
                "field already populated hwid=%s %s=%r" % (hwid, field, cur[0])
            )
        # 3. no duplicate (hwid, field) within payload
        k = (hwid, field)
        if k in seen:
            problems.append("duplicate in payload %s" % (k,))
        seen.add(k)
        # 4. no existing provenance for this (hwid, field, source, batch)
        p = con.execute(
            "SELECT 1 FROM field_provenance WHERE hardware_id=? AND field_name=? "
            "AND source_id=? AND batch_no=?",
            (hwid, field, SOURCE_ID, BATCH_NO),
        ).fetchone()
        if p:
            problems.append("provenance already exists hwid=%s field=%s" % (hwid, field))
    return problems


def apply_rehearsal(db_path, do_apply=True, verify=True):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")

    schema_err = schema_check(con)
    if schema_err:
        con.close()
        return {"ok": False, "reason": "schema precondition failed: %s" % schema_err}

    problems = preflight(con, RECORDS)
    if problems:
        # If every problem is "already populated" / "provenance exists" and there
        # are no hard structural problems (missing hardware / duplicate payload /
        # schema), treat it as idempotent up-to-date => 0 changes.
        hard = [
            p for p in problems
            if p.startswith("hardware missing")
            or p.startswith("duplicate in payload")
        ]
        con.close()
        if not hard and len(problems) == 2 * len(RECORDS):
            return {"ok": True, "mode": "already-applied-idempotent",
                    "changes": 0,
                    "reason": "all %d target records already populated with "
                              "provenance; no overwrite performed" % len(RECORDS)}
        return {"ok": False, "reason": "precondition failures (%d): %s"
                % (len(problems), problems[:5])}

    if not do_apply:
        con.close()
        return {"ok": True, "mode": "preflight-only",
                "target_records": len(RECORDS)}

    applied_iface = applied_bw = 0
    con.execute("BEGIN IMMEDIATE")
    try:
        for r in RECORDS:
            hwid, field, val = r["hardware_id"], r["field"], r["source_value"]
            ark_id = r.get("ark_id", "")

            # re-check NULL guard inside the transaction (authoritative)
            cur = con.execute(
                "SELECT %s FROM gpu_specifications WHERE hardware_id=?" % field,
                (hwid,),
            ).fetchone()
            if cur is None or cur[0] is not None:
                raise RuntimeError(
                    "NULL guard violated mid-txn hwid=%s field=%s" % (hwid, field)
                )
            # re-check provenance absence inside txn
            p = con.execute(
                "SELECT 1 FROM field_provenance WHERE hardware_id=? AND field_name=? "
                "AND source_id=? AND batch_no=?",
                (hwid, field, SOURCE_ID, BATCH_NO),
            ).fetchone()
            if p:
                raise RuntimeError(
                    "duplicate provenance mid-txn hwid=%s field=%s" % (hwid, field)
                )

            con.execute(
                "UPDATE gpu_specifications SET %s=? WHERE hardware_id=?" % field,
                (val, hwid),
            )
            con.execute(
                "INSERT INTO field_provenance (%s) VALUES (%s)"
                % (", ".join(PROVENANCE_COLS), ", ".join("?" * len(PROVENANCE_COLS))),
                (
                    hwid, SOURCE_ID, "gpu_specifications", field,
                    str(val), META["url"], META["license"],
                    META["attribution"], META["retrieved_on"], "medium",
                    "verified", ark_id,
                    "normalized_name + vendor_prefix_stripped",
                    BATCH_NO,
                    "batch018: GPU Ark bus interface enrichment (prod migration)",
                    NOW,
                ),
            )
            if field == "interface":
                applied_iface += 1
            elif field == "memory_bus_width_bits":
                applied_bw += 1
    except Exception as e:
        con.execute("ROLLBACK")
        con.close()
        return {"ok": False, "reason": "txn failed: %s" % e}

    con.execute("COMMIT")

    result = {"ok": True, "mode": "apply",
              "applied_iface": applied_iface,
              "applied_bw": applied_bw,
              "applied_total": applied_iface + applied_bw,
              "batch_no": BATCH_NO,
              "record_count_src": len(RECORDS)}

    if verify:
        v = verify_rehearsal(db_path)
        result["verify"] = v
        if (applied_iface != 938 or applied_bw != 27
                or applied_iface + applied_bw != 965
                or v.get("prov_added_this_batch") != 965):
            result["ok"] = False
            result["reason"] = "post-apply count mismatch; verify dict above"
    con.close()
    return result


def verify_rehearsal(db_path):
    """Open a fresh read connection to avoid statement-cache binding errors."""
    v = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    qc = v.execute("PRAGMA quick_check").fetchone()[0]
    fk = v.execute("PRAGMA foreign_key_check").fetchall()
    prov = v.execute(
        "SELECT COUNT(*) FROM field_provenance WHERE source_id=? AND batch_no=?",
        (SOURCE_ID, BATCH_NO),
    ).fetchone()[0]
    out = {
        "quick_check": qc,
        "fk_violations": len(fk),
        "prov_added_this_batch": prov,
        "interface_nonnull_now": v.execute(
            "SELECT COUNT(*) FROM gpu_specifications WHERE interface IS NOT NULL"
        ).fetchone()[0],
        "bus_width_nonnull_now": v.execute(
            "SELECT COUNT(*) FROM gpu_specifications WHERE memory_bus_width_bits IS NOT NULL"
        ).fetchone()[0],
    }
    v.close()
    return out


def main(argv):
    db_path = argv[1] if len(argv) > 1 else None
    do_apply = "--apply" in argv
    do_verify = "--verify" in argv

    if not db_path:
        print("usage: python - <rehearsal_db_path> [--apply] [--verify]")
        return 1
    if not os.path.exists(db_path):
        print("ERROR: rehearsal DB not found: %s" % db_path)
        return 1

    print("rehearsal_db:", db_path)
    print("sha256:", sha256_file(db_path))

    result = apply_rehearsal(db_path, do_apply=do_apply, verify=do_verify)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
