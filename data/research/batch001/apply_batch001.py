"""
SPECTRA Batch 001 - validation and apply tool.

Phases:
  1-2: validate every proposed update against the schema, evidence table and
       documented risk policy (hard failures exclude an update from apply).
  3:   record baseline (hash, counts, NULL counts), create a timestamped backup.
  4:   apply in ONE guarded transaction (WHERE hardware_id=? AND col IS NULL),
       full rollback on any unexpected result or exception.
  5:   post-apply integrity + coverage verification.

Usage:
  python apply_batch001.py validate     # read-only; writes validation_summary.json
  python apply_batch001.py apply        # baseline+backup+apply+verify (idempotent guard)
"""
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BATCH = os.path.join(REPO, "data", "research", "batch001")
DB = os.path.join(REPO, "data", "spectra.db")
EVIDENCE_CSV = os.path.join(BATCH, "04_evidence_table.csv")
PATCH_JSON = os.path.join(BATCH, "05_database_patch.json")
SUMMARY_JSON = os.path.join(BATCH, "apply_results.json")

TABLES = ("hardware", "cpu_specifications", "gpu_specifications")
ALLOWED_COLUMNS = {
    "hardware": ("release_date", "architecture"),
    "cpu_specifications": ("base_clock_ghz", "tdp_w", "process_node_nm", "cores",
                            "threads", "boost_clock_ghz", "socket"),
    "gpu_specifications": ("memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
                            "vram_bandwidth_gbps", "tdp_w", "interface", "length_mm"),
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def schema_columns(conn):
    cols = {}
    for t in TABLES:
        cols[t] = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
    return cols


def load_inputs():
    with open(PATCH_JSON, encoding="utf-8") as f:
        patch = json.load(f)
    evidence = list(csv.DictReader(open(EVIDENCE_CSV, encoding="utf-8")))
    return patch, evidence


def validate(conn):
    """Returns (ok_list, excluded_list, problems)."""
    patch, evidence = load_inputs()
    problems = []
    excluded = []
    ok = []
    cols = schema_columns(conn)

    hw = {}
    for r in conn.execute("select id,name,manufacturer,type from hardware"):
        hw[r["id"]] = r
    hw_ids = set(hw)

    # 8/9. duplicate & conflict detection on patch + evidence
    def upd_key(u):
        return (u["table"], u["hardware_id"], u["column"])

    patch_by_key = {}
    for u in patch["updates"]:
        k = upd_key(u)
        if k in patch_by_key:
            problems.append(f"patch duplicate key {k}")
        patch_by_key[k] = u
    if len(patch_by_key) != len(patch["updates"]):
        problems.append("patch has duplicate (table,hardware_id,column) updates")

    ev_by_key = {}
    for e in evidence:
        k = (e["table"], int(e["hardware_id"]), e["field"])
        if k in ev_by_key:
            problems.append(f"evidence duplicate key {k}")
        ev_by_key[k] = e

    # cross-check patch vs evidence: keys, values, confidence
    if set(patch_by_key) != set(ev_by_key):
        problems.append("patch/evidence key sets differ: only-patch=" +
                        str(set(patch_by_key) - set(ev_by_key)) + " only-evidence=" +
                        str(set(ev_by_key) - set(patch_by_key)))
    for k, u in patch_by_key.items():
        e = ev_by_key.get(k)
        if e is None:
            continue
        if str(u["new_value"]) != str(e["researched_value"]):
            problems.append(f"patch/evidence value differs {k}: {u['new_value']} vs {e['researched_value']}")
        if u["confidence"] != e["confidence"]:
            problems.append(f"patch/evidence confidence differs {k}")
        if u["source_url"].strip() != e["source_url"].strip():
            problems.append(f"patch/evidence source_url differs {k}")
        if u["source"].strip() != e["source_name"].strip():
            problems.append(f"patch/evidence source_name differs {k}")

    # 10. deliberately-excluded list must not be applied
    excluded_set = {(e["hardware_id"], e["field"]) for e in patch["deliberately_excluded"]}
    for u in patch["updates"]:
        if (u["hardware_id"], u["column"]) in excluded_set:
            problems.append(f"excluded item present in updates: {u['hardware_id']}.{u['column']}")

    # 11. no gaming benchmarks / no benchmark_results touches
    if "benchmark_results" in patch or "benchmark" in str([u["table"] for u in patch["updates"]]).lower():
        problems.append("patch must not touch benchmark tables")
    if any("gaming" in str(u.get("notes", "")).lower() for u in patch["updates"]):
        problems.append("patch contains gaming references")

    # current values per field for NULL checks
    cur = {}
    for t in TABLES:
        idcol = "hardware_id" if t != "hardware" else "id"
        for r in conn.execute(f"select {idcol} as hw_id, * from {t}"):
            cur[(t, r["hw_id"])] = dict(r)

    for u in patch["updates"]:
        t, i, col = u["table"], u["hardware_id"], u["column"]
        reasons = []
        ok_row = True

        # 1. hardware_id exists + identity
        if i not in hw_ids:
            reasons.append("hardware_id not in hardware table")
        e = ev_by_key.get((t, i, col))
        if e:
            if hw.get(i) and (hw[i]["name"] != e["hardware_name"] or hw[i]["type"] != e["hardware_type"]):
                reasons.append("identity mismatch vs evidence (name/type)")
        # 3. column exists in schema + correct table context
        if col not in cols.get(t, set()):
            reasons.append(f"column '{col}' not in schema of {t}")
        if t not in TABLES:
            reasons.append(f"illegal table {t}")
        # 12. no inserts/deletes implied
        if t not in ("hardware", "cpu_specifications", "gpu_specifications"):
            reasons.append("patch would touch unexpected table")
        # guards must be exactly "<column> IS NULL"
        if (u.get("guard") or "") != f"{col} IS NULL":
            reasons.append(f"guard string malformed: {u.get('guard')!r}")

        # 6. source url present
        if not (isinstance(u.get("source_url"), str) and URL_RE.match(u["source_url"].strip())):
            reasons.append("missing/invalid source_url")
        if not (isinstance(u.get("source"), str) and u["source"].strip()):
            reasons.append("missing source name")

        # 7. confidence valid
        if u.get("confidence") not in ("high", "medium"):
            reasons.append(f"invalid confidence {u.get('confidence')!r}")

        # 5. current value must be NULL
        cur_row = cur.get((t, i)) or {}
        cv = cur_row.get(col)
        if cv is not None and str(cv).strip() != "":
            reasons.append(f"current value not NULL: {cv!r}")
            ok_row = False  # never touch a non-NULL value

        # 4. type/format validation per column
        v = u["new_value"]
        if col == "release_date":
            if not (isinstance(v, str) and DATE_RE.match(v)):
                reasons.append("release_date not ISO date")
            else:
                try:
                    d = datetime.date.fromisoformat(v)
                    if not (datetime.date(2011, 1, 1) <= d <= datetime.date(2026, 12, 31)):
                        reasons.append("release_date out of plausible range")
                except ValueError:
                    reasons.append("release_date invalid")
        elif col == "architecture":
            if not (isinstance(v, str) and 2 <= len(v.strip()) <= 100):
                reasons.append("architecture invalid length")
        elif col == "process_node_nm":
            if v not in (5, 6, 7, 10, 12, 14, 16, 22, 24, 28, 32):
                reasons.append(f"process_node_nm implausible {v!r}")
        elif col == "base_clock_ghz":
            if not (isinstance(v, (int, float)) and 0.5 <= float(v) <= 7.0):
                reasons.append(f"base_clock_ghz implausible {v!r}")
        elif col == "tdp_w":
            if not (isinstance(v, (int, float)) and 1.0 <= float(v) <= 600.0):
                reasons.append(f"tdp_w implausible {v!r}")
        elif col == "core_clock_mhz":
            if not (isinstance(v, (int, float)) and 0 < float(v) < 6000):
                reasons.append(f"core_clock_mhz implausible {v!r}")

        if reasons:
            ok_row = False

        # semantic cross checks (only when current row is otherwise valid)
        spec_row = cur.get(("cpu_specifications", i)) or {}
        gpu_row = cur.get(("gpu_specifications", i)) or {}
        if t == "cpu_specifications" and col == "base_clock_ghz":
            boost = spec_row.get("boost_clock_ghz")
            if boost is not None and float(v) >= float(boost):
                reasons.append(f"base {v} >= existing boost {boost}")
                ok_row = False
        if t == "gpu_specifications" and col == "core_clock_mhz":
            boost = gpu_row.get("boost_clock_mhz")
            if boost is not None and float(v) >= float(boost):
                reasons.append(f"core clock {v} >= existing boost {boost}")
                ok_row = False
        if t == "cpu_specifications" and col == "process_node_nm":
            hw_row = hw.get(i)
            if hw_row and hw_row["manufacturer"] == "AMD" and v not in (5, 7, 12, 14):
                reasons.append(f"unexpected AMD node {v}")

        if ok_row:
            ok.append(u)
        else:
            excluded.append({"hardware_id": i, "table": t, "column": col,
                             "new_value": v, "reasons": reasons})

    return ok, excluded, problems


def baseline(conn):
    info = {
        "db": DB,
        "sha256": sha256(DB),
        "size_bytes": os.path.getsize(DB),
        "quick_check": conn.execute("PRAGMA quick_check").fetchone()[0],
        "counts": {
            "hardware": conn.execute("select count(*) from hardware").fetchone()[0],
            "cpu": conn.execute("select count(*) from hardware where type='CPU'").fetchone()[0],
            "gpu": conn.execute("select count(*) from hardware where type='GPU'").fetchone()[0],
            "cpu_specs": conn.execute("select count(*) from cpu_specifications").fetchone()[0],
            "gpu_specs": conn.execute("select count(*) from gpu_specifications").fetchone()[0],
            "benchmark_results": conn.execute("select count(*) from benchmark_results").fetchone()[0],
        },
        "null_counts_before": {},
    }
    for t, col in [("hardware", "release_date"), ("hardware", "architecture"),
                   ("cpu_specifications", "base_clock_ghz"), ("cpu_specifications", "tdp_w"),
                   ("cpu_specifications", "process_node_nm"), ("gpu_specifications", "core_clock_mhz")]:
        n = conn.execute(f"select count(*) from {t} where {col} is null").fetchone()[0]
        info["null_counts_before"][f"{t}.{col}"] = n
    return info


def make_backup():
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = os.path.join(REPO, "data", f"spectra.db.bak-{ts}")
    shutil.copy2(DB, dst)
    for suffix in ("-wal", "-shm"):
        p = DB + suffix
        if os.path.exists(p):
            shutil.copy2(p, dst + suffix)
    return dst, ts


added = {
    "hardware": "id",
    "cpu_specifications": "hardware_id",
    "gpu_specifications": "hardware_id",
}


def hw_where(t):
    return added[t]


def apply_updates(conn, updates):
        """Single transaction; hard-fail on any anomaly (caller commits/rolls back)."""
        count = 0
        applied = []
        for u in updates:
            t, i, col, v = u["table"], u["hardware_id"], u["column"], u["new_value"]
            idcol = hw_where(t)
            before = conn.execute(
                f"select {col} as c from {t} where {idcol}=?", (i,)).fetchone()
            if before is None:
                raise RuntimeError(f"row missing for {t}:{i} - aborting")
            if before["c"] is not None:
                raise RuntimeError(f"column {t}.{col} for {i} not NULL - aborting")
            cur = conn.execute(
                f"update {t} set {col} = ? where {idcol} = ? and {col} is null",
                (v, i))
            if cur.rowcount != 1:
                raise RuntimeError(f"guard update affected {cur.rowcount} rows for {t}:{i}.{col}")
            applied.append({"table": t, "hardware_id": i, "column": col, "value": v})
            count += 1
        return applied, count


def values_equal(a, b):
    """Numeric-tolerant equality (schema columns are REAL; JSON may hold ints)."""
    try:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(float(a) - float(b)) < 1e-6
        return str(a) == str(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def post_check(conn, applied, baseline_info):
    res = {
        "quick_check": conn.execute("PRAGMA quick_check").fetchone()[0],
        "counts": {
            "hardware": conn.execute("select count(*) from hardware").fetchone()[0],
            "cpu": conn.execute("select count(*) from hardware where type='CPU'").fetchone()[0],
            "gpu": conn.execute("select count(*) from hardware where type='GPU'").fetchone()[0],
            "cpu_specs": conn.execute("select count(*) from cpu_specifications").fetchone()[0],
            "gpu_specs": conn.execute("select count(*) from gpu_specifications").fetchone()[0],
            "benchmark_results": conn.execute("select count(*) from benchmark_results").fetchone()[0],
        },
        "null_counts_after": {},
        "value_spot_checks": {"checked": 0, "mismatch": 0},
    }
    for t, col in [("hardware", "release_date"), ("hardware", "architecture"),
                   ("cpu_specifications", "base_clock_ghz"), ("cpu_specifications", "tdp_w"),
                   ("cpu_specifications", "process_node_nm"), ("gpu_specifications", "core_clock_mhz")]:
        res["null_counts_after"][f"{t}.{col}"] = conn.execute(
            f"select count(*) from {t} where {col} is null").fetchone()[0]
    for u in applied:
        got = conn.execute(f"select {u['column']} as c from {u['table']} where {hw_where(u['table'])}=?",
                           (u["hardware_id"],)).fetchone()["c"]
        res["value_spot_checks"]["checked"] += 1
        if not values_equal(got, u["value"]):
            res["value_spot_checks"]["mismatch"] += 1
    return res


def run_validate():
    patch, evidence = load_inputs()
    problems_all = []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        ok, excluded, problems = validate(conn)
        problems_all = problems
    summary = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "proposed": len(patch["updates"]),
        "validated": len(ok),
        "excluded": excluded,
        "problems": problems_all,
        "gaming_import_present": False,
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"proposed={len(patch['updates'])} validated={len(ok)} excluded={len(excluded)}")
    for e in excluded:
        print("  EXCLUDED", e["hardware_id"], e["column"], e["reasons"])
    if problems_all:
        print("PROBLEMS:")
        for p in problems_all:
            print("  -", p)
    return ok, excluded, problems_all


def run_apply():
    patch, evidence = load_inputs()
    ok, excluded, problems = run_validate()
    if problems:
        sys.exit(f"validation problems found; refusing to apply:\n" + "\n".join(problems))
    if excluded:
        print(f"{len(excluded)} updates excluded; applying {len(ok)} of {len(patch['updates'])}")

    with sqlite3.connect(DB, isolation_level=None) as conn:
        conn.row_factory = sqlite3.Row
        base = baseline(conn)
        backup, ts = make_backup()
        base["backup_path"] = backup
        base["backup_timestamp"] = ts
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            applied, count = apply_updates(conn, ok)
        except Exception:
            conn.execute("ROLLBACK")
            raise
        if count != len(ok):
            conn.execute("ROLLBACK")
            raise RuntimeError("applied count mismatch - no commit performed")
        conn.execute("COMMIT")
        post = post_check(conn, applied, base)

    # reopen read-only for a clean final check after the write transaction closed
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        fast = {
            "quick_check": conn.execute("PRAGMA quick_check").fetchone()[0],
            "sha256": sha256(DB),
            "size_bytes": os.path.getsize(DB),
            "counts": {
                "hardware": conn.execute("select count(*) from hardware").fetchone()[0],
                "cpu": conn.execute("select count(*) from hardware where type='CPU'").fetchone()[0],
                "gpu": conn.execute("select count(*) from hardware where type='GPU'").fetchone()[0],
                "cpu_specs": conn.execute("select count(*) from cpu_specifications").fetchone()[0],
                "gpu_specs": conn.execute("select count(*) from gpu_specifications").fetchone()[0],
                "benchmark_results": conn.execute("select count(*) from benchmark_results").fetchone()[0],
            },
        }

    result = {
        "applied": count,
        "skipped_expected": 0,   # guard would skip already-populated; validation asserted none
        "excluded": excluded,
        "backup": backup,
        "baseline": base,
        "post_apply": post,
        "final": fast,
        "final_sha256": sha256(DB),
    }
    out = os.path.join(BATCH, "apply_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"APPLIED {count} updates. backup={backup}")
    print("final sha256:", result["final_sha256"])
    print("post quick_check:", post["quick_check"], "| value mismatches:", post["value_spot_checks"]["mismatch"])
    return result


def run_verify():
    """Recompute post-apply checks against the live DB and refresh apply_results.json."""
    patch, _evidence = load_inputs()
    path = os.path.join(BATCH, "apply_results.json")
    with open(path, encoding="utf-8") as f:
        result = json.load(f)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        applied = [{"table": u["table"], "hardware_id": u["hardware_id"],
                    "column": u["column"], "value": u["new_value"]} for u in patch["updates"]]
        result["post_apply"] = post_check(conn, applied, result["baseline"])
        result["final"] = {
            "quick_check": conn.execute("PRAGMA quick_check").fetchone()[0],
            "sha256": sha256(DB),
            "size_bytes": os.path.getsize(DB),
            "counts": {
                "hardware": conn.execute("select count(*) from hardware").fetchone()[0],
                "cpu": conn.execute("select count(*) from hardware where type='CPU'").fetchone()[0],
                "gpu": conn.execute("select count(*) from hardware where type='GPU'").fetchone()[0],
                "cpu_specs": conn.execute("select count(*) from cpu_specifications").fetchone()[0],
                "gpu_specs": conn.execute("select count(*) from gpu_specifications").fetchone()[0],
                "benchmark_results": conn.execute("select count(*) from benchmark_results").fetchone()[0],
            },
        }
        result["final_sha256"] = sha256(DB)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("verify ok:", result["post_apply"]["quick_check"],
          "| value mismatches:", result["post_apply"]["value_spot_checks"]["mismatch"])
    return result


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if mode == "validate":
        run_validate()
    elif mode == "apply":
        run_apply()
    elif mode == "verify":
        run_verify()
    else:
        sys.exit("usage: apply_batch001.py [validate|apply|verify]")