"""
SPECTRA Batch 002 - recover missing GPU `gpu_specifications.core_clock_mhz`
from the already-present, documented GPU Ark dataset (CC BY 4.0).

Source (local, git-ignored): data/raw/gpuark-gpu-specs.csv
  - documented in data/raw/README.md (dataset card, license: cc-by-4.0)
  - live attribution: https://gpuark.com/datasets/  ("CC BY 4.0")

The TechPowerUp snapshot (data/raw/gpu_1986-2026.csv) is deliberately NOT used:
its robots.txt permits only personal, non-commercial use and forbids data
mining / creating datasets of its content without prior written permission.

Matching is exact and deterministic:
  normalized(name in DB)  ==  normalized(name in GPU Ark, chip-vendor prefix
                                           stripped)
  AND chip-vendor compatibility (nvd->NVIDIA, amd->AMD, int->Intel; AMD<->ATI)
  AND exactly one distinct base_clock value among candidates
  AND base_clock within the existing validator range [100, 4000] MHz
  AND the independent boost_clock_mhz already stored in the DB corroborates
      GPU Ark's boost_clock (|delta| <= 10 MHz, source GHz-rounding tolerance).
No fuzzy matching. No interpolation. NULL-only, guarded, atomic updates.

Modes:
  generate  read-only; writes 02_mapping_results.csv + 04_database_patch.json
  apply     backup + one guarded transaction + post checks
  verify    independent recomputation from DB + source + backup
"""

import collections
import csv
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BATCH = os.path.join(REPO, "data", "research", "batch002")
DB = os.path.join(REPO, "data", "spectra.db")
BACKUP_DIR = os.path.join(REPO, "data", "backups")
ARK_CSV = os.path.join(REPO, "data", "raw", "gpuark-gpu-specs.csv")

MAPPING_CSV = os.path.join(BATCH, "02_mapping_results.csv")
PATCH_JSON = os.path.join(BATCH, "04_database_patch.json")
STATS_JSON = os.path.join(BATCH, "batch002_stats.json")
APPLY_RESULTS_JSON = os.path.join(BATCH, "apply_results.json")

sys.path.insert(0, REPO)
from backend.app.importers.benchmark_normalizer import normalize_name  # noqa: E402

SOURCE_NAME = "GPU Ark GPU specifications & benchmarks dataset"
SOURCE_URL = "https://gpuark.com/datasets/"
SOURCE_LICENSE = "CC BY 4.0"
SOURCE_CITATION = (
    "GPU Ark (2026). GPU specifications & benchmarks dataset. "
    "https://gpuark.com/datasets/"
)
SOURCE_FILE = "data/raw/gpuark-gpu-specs.csv"

TARGET_TABLE = "gpu_specifications"
TARGET_COLUMN = "core_clock_mhz"
MIN_MHZ = 100.0
MAX_MHZ = 4000.0
BOOST_TOL_MHZ = 10.0

VENDOR_MAP = {"nvd": "NVIDIA", "amd": "AMD", "int": "Intel"}
CHIP_PREFIXES = ("nvidia ", "amd ", "ati ", "intel ")

MAPPING_COLUMNS = [
    "hardware_id",
    "hardware_name",
    "manufacturer",
    "source_name",
    "source_record_id",
    "source_gpu_name",
    "source_field",
    "source_value",
    "source_unit",
    "target_table",
    "target_column",
    "target_value",
    "target_unit",
    "match_method",
    "source_url",
    "confidence",
    "status",
    "exclusion_reason",
]

TABLES = (
    "hardware",
    "cpu_specifications",
    "gpu_specifications",
    "benchmark_results",
    "external_identifiers",
    "sources",
    "build_conversations",
    "build_messages",
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_chip_prefix(norm):
    low = norm.lower()
    for prefix in CHIP_PREFIXES:
        if low.startswith(prefix):
            return norm[len(prefix):].strip()
    return norm


def ark_normalized_name(name):
    return strip_chip_prefix(normalize_name(name or "") or "").strip()


def vendor_ok(ark_vendor, db_manufacturer):
    if ark_vendor == db_manufacturer:
        return True
    return {ark_vendor, db_manufacturer} <= {"AMD", "ATI"}


def load_db_gpu_rows(readonly=True, db_path=None):
    path = db_path or DB
    uri = f"file:{path}?mode=ro" if readonly else path
    con = sqlite3.connect(uri, uri=readonly)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        """
        SELECT h.id AS hardware_id, h.name AS hardware_name,
               h.manufacturer AS manufacturer, g.core_clock_mhz AS core_clock_mhz,
               g.boost_clock_mhz AS boost_clock_mhz
        FROM hardware h
        JOIN gpu_specifications g ON g.hardware_id = h.id
        WHERE h.type = 'GPU'
        """
    )]
    con.close()
    return rows


def load_ark_rows():
    rows = []
    with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            base_raw = (row.get("base_clock") or "").strip()
            if not base_raw:
                continue
            try:
                base = float(base_raw)
            except ValueError:
                continue
            boost_raw = (row.get("boost_clock") or "").strip()
            try:
                boost = float(boost_raw) if boost_raw else None
            except ValueError:
                boost = None
            rows.append({
                "id": row.get("id"),
                "name": row.get("name"),
                "vendor": (row.get("vendor") or "").strip(),
                "manufacturer": row.get("manufacturer"),
                "base": base,
                "boost": boost,
                "nname": ark_normalized_name(row.get("name")),
                "nv": VENDOR_MAP.get((row.get("vendor") or "").strip(),
                                     (row.get("vendor") or "").strip()),
            })
    return rows


def build_index(ark_rows):
    idx = collections.defaultdict(list)
    for a in ark_rows:
        idx[a["nname"]].append(a)
    return idx


def plan(db_path=None):
    """Deterministic, read-only matching plan. Returns (records, stats)."""
    db_rows = [r for r in load_db_gpu_rows(db_path=db_path) if r["core_clock_mhz"] is None]
    ark_rows = load_ark_rows()
    idx = build_index(ark_rows)

    records = []
    counts = collections.Counter()
    reasons = collections.Counter()

    for r in db_rows:
        norm = normalize_name(r["hardware_name"])
        candidates = [a for a in idx.get(norm, []) if vendor_ok(a["nv"], r["manufacturer"])]
        rec = {
            "hardware_id": r["hardware_id"],
            "hardware_name": r["hardware_name"],
            "manufacturer": r["manufacturer"],
            "source_name": SOURCE_NAME,
            "source_record_id": "",
            "source_gpu_name": "",
            "source_field": "base_clock",
            "source_value": "",
            "source_unit": "MHz",
            "target_table": TARGET_TABLE,
            "target_column": TARGET_COLUMN,
            "target_value": "",
            "target_unit": "MHz",
            "match_method": "exact normalized name + chip-vendor + unique base_clock",
            "source_url": SOURCE_URL,
            "confidence": "",
            "status": "",
            "exclusion_reason": "",
        }
        counts["audited"] += 1

        if not candidates:
            rec["status"] = "unmatched"
            rec["confidence"] = "rejected"
            rec["exclusion_reason"] = "no GPU Ark row with the same normalized name and chip vendor"
            reasons["unmatched"] += 1
            records.append(rec)
            continue

        distinct_bases = set(a["base"] for a in candidates)
        if len(distinct_bases) != 1:
            rec["status"] = "ambiguous"
            rec["confidence"] = "rejected"
            rec["source_record_id"] = ";".join(str(a["id"]) for a in candidates)
            rec["source_gpu_name"] = "; ".join(a["name"] for a in candidates)
            rec["source_value"] = ";".join(str(v) for v in sorted(distinct_bases))
            rec["exclusion_reason"] = "multiple distinct base_clock values for the same normalized name"
            reasons["ambiguous_base"] += 1
            records.append(rec)
            continue

        base = next(iter(distinct_bases))
        a0 = candidates[0]
        rec["source_record_id"] = str(a0["id"])
        rec["source_gpu_name"] = a0["name"]
        rec["source_value"] = base

        if not (MIN_MHZ <= base <= MAX_MHZ):
            rec["status"] = "invalid"
            rec["confidence"] = "rejected"
            rec["exclusion_reason"] = f"base_clock {base} outside validator range [{MIN_MHZ:.0f},{MAX_MHZ:.0f}]"
            reasons["invalid"] += 1
            records.append(rec)
            continue

        db_boost = r["boost_clock_mhz"]
        ark_boosts = [a["boost"] for a in candidates if a["boost"] is not None]
        if not ark_boosts:
            rec["status"] = "ambiguous"
            rec["confidence"] = "rejected"
            rec["exclusion_reason"] = "GPU Ark has no boost_clock to corroborate product identity"
            reasons["no_boost_evidence"] += 1
            records.append(rec)
            continue

        corroborated = any(abs(db_boost - b) <= BOOST_TOL_MHZ for b in ark_boosts)
        if not corroborated:
            rec["status"] = "ambiguous"
            rec["confidence"] = "rejected"
            rec["exclusion_reason"] = (
                "stored boost_clock_mhz does not match GPU Ark boost_clock "
                f"(db={db_boost}, ark={sorted(ark_boosts)}); possible board/mobile variant"
            )
            reasons["boost_mismatch"] += 1
            records.append(rec)
            continue

        if base > db_boost:
            rec["status"] = "invalid"
            rec["confidence"] = "rejected"
            rec["exclusion_reason"] = f"base_clock {base} > existing boost_clock_mhz {db_boost}"
            reasons["base_gt_boost"] += 1
            records.append(rec)
            continue

        rec["target_value"] = base
        rec["confidence"] = "high"
        rec["status"] = "safe_update"
        reasons["safe_update"] += 1
        records.append(rec)

    stats = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": {
            "name": SOURCE_NAME,
            "file": SOURCE_FILE,
            "url": SOURCE_URL,
            "license": SOURCE_LICENSE,
            "citation": SOURCE_CITATION,
            "ark_rows_with_base_clock": len(ark_rows),
        },
        "gpu_rows_total": len(load_db_gpu_rows()),
        "gpu_rows_audited": counts["audited"],
        "missing_core_clock": counts["audited"],
        "source_rows_available": len(ark_rows),
        "exact_normalized_matches": reasons["safe_update"] + reasons["boost_mismatch"] + reasons["base_gt_boost"],
        "safe_null_only_updates": reasons["safe_update"],
        "ambiguous_matches": reasons["ambiguous_base"] + reasons["boost_mismatch"] + reasons["no_boost_evidence"],
        "unmatched_rows": reasons["unmatched"],
        "invalid_values": reasons["invalid"] + reasons["base_gt_boost"],
        "breakdown": dict(reasons),
    }
    return records, stats


def write_artifacts(records, stats):
    os.makedirs(BATCH, exist_ok=True)
    with open(MAPPING_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MAPPING_COLUMNS)
        w.writeheader()
        for rec in records:
            w.writerow({k: rec.get(k, "") for k in MAPPING_COLUMNS})

    updates = []
    excluded = []
    unmatched = []
    for rec in records:
        if rec["status"] == "safe_update":
            updates.append({
                "table": TARGET_TABLE,
                "hardware_id": rec["hardware_id"],
                "column": TARGET_COLUMN,
                "new_value": rec["target_value"],
                "guard": f"{TARGET_COLUMN} IS NULL",
                "source": SOURCE_NAME,
                "source_record_id": rec["source_record_id"],
                "source_field": rec["source_field"],
                "source_value": rec["source_value"],
                "source_unit": rec["source_unit"],
                "source_url": SOURCE_URL,
                "confidence": rec["confidence"],
                "match_method": rec["match_method"],
            })
        elif rec["status"] == "unmatched":
            unmatched.append({"hardware_id": rec["hardware_id"],
                              "hardware_name": rec["hardware_name"],
                              "reason": rec["exclusion_reason"]})
        else:
            excluded.append({"hardware_id": rec["hardware_id"],
                             "hardware_name": rec["hardware_name"],
                             "status": rec["status"],
                             "reason": rec["exclusion_reason"]})

    with open(PATCH_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "batch": "batch002",
            "applied": False,
            "target_table": TARGET_TABLE,
            "target_column": TARGET_COLUMN,
            "source": stats["source"],
            "stats": stats,
            "updates": updates,
            "excluded": excluded,
            "unmatched": unmatched,
        }, f, indent=2, ensure_ascii=False)

    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    return updates, excluded, unmatched


def mode_generate():
    records, stats = plan()
    updates, excluded, unmatched = write_artifacts(records, stats)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"\nupdates={len(updates)} excluded={len(excluded)} unmatched={len(unmatched)}")
    return stats


def table_counts(con):
    counts = {}
    for t in TABLES:
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    counts["hardware_cpu"] = con.execute("SELECT COUNT(*) FROM hardware WHERE type='CPU'").fetchone()[0]
    counts["hardware_gpu"] = con.execute("SELECT COUNT(*) FROM hardware WHERE type='GPU'").fetchone()[0]
    return counts


def coverage(con):
    total = con.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0]
    nonnull = con.execute("SELECT COUNT(*) FROM gpu_specifications WHERE core_clock_mhz IS NOT NULL").fetchone()[0]
    nulls = con.execute("SELECT COUNT(*) FROM gpu_specifications WHERE core_clock_mhz IS NULL").fetchone()[0]
    return {"gpu_specs": total, "core_clock_nonnull": nonnull, "core_clock_null": nulls,
            "coverage_pct": round(100.0 * nonnull / total, 2)}


def gpu_benchmark_count(con):
    return con.execute(
        "SELECT COUNT(*) FROM benchmark_results b JOIN hardware h ON h.id=b.hardware_id WHERE h.type='GPU'"
    ).fetchone()[0]


def baseline(con):
    return {
        "db": DB,
        "sha256": sha256(DB),
        "size_bytes": os.path.getsize(DB),
        "quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
        "counts": table_counts(con),
        "coverage": coverage(con),
        "gpu_benchmark_rows": gpu_benchmark_count(con),
    }


def make_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = os.path.join(BACKUP_DIR, f"spectra-pre-batch002-coreclock-{ts}.db")
    shutil.copy2(DB, dst)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(DB + suffix):
            shutil.copy2(DB + suffix, dst + suffix)
    return dst, ts


def mode_apply():
    records, stats = plan()
    write_artifacts(records, stats)
    updates = [r for r in records if r["status"] == "safe_update"]

    pre_sha = sha256(DB)
    con = sqlite3.connect(DB, isolation_level=None)
    con.row_factory = sqlite3.Row
    base = baseline(con)
    backup, ts = make_backup()
    backup_sha = sha256(backup)
    if backup_sha != pre_sha:
        con.close()
        raise RuntimeError("backup hash does not match pre-apply database - aborting")

    applied = []
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("BEGIN IMMEDIATE")
    try:
        for r in updates:
            before = con.execute(
                "SELECT core_clock_mhz FROM gpu_specifications WHERE hardware_id=?",
                (r["hardware_id"],)).fetchone()
            if before is None:
                raise RuntimeError(f"no gpu_specifications row for hardware_id {r['hardware_id']}")
            if before["core_clock_mhz"] is not None:
                raise RuntimeError(f"core_clock_mhz not NULL for {r['hardware_id']} - aborting")
            cur = con.execute(
                "UPDATE gpu_specifications SET core_clock_mhz=? "
                "WHERE hardware_id=? AND core_clock_mhz IS NULL",
                (r["target_value"], r["hardware_id"]))
            if cur.rowcount != 1:
                raise RuntimeError(f"guard update affected {cur.rowcount} rows for {r['hardware_id']}")
            applied.append({
                "table": TARGET_TABLE, "hardware_id": r["hardware_id"],
                "column": TARGET_COLUMN, "new_value": r["target_value"],
                "source_record_id": r["source_record_id"],
            })
        if len(applied) != len(updates):
            raise RuntimeError("applied count mismatch - no commit")
    except Exception:
        con.execute("ROLLBACK")
        con.close()
        raise
    con.execute("COMMIT")

    post = {
        "quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
        "counts": table_counts(con),
        "coverage": coverage(con),
        "gpu_benchmark_rows": gpu_benchmark_count(con),
    }
    # verify every applied value equals the source value
    mismatches = 0
    for r in updates:
        got = con.execute("SELECT core_clock_mhz FROM gpu_specifications WHERE hardware_id=?",
                          (r["hardware_id"],)).fetchone()[0]
        if abs(float(got) - float(r["target_value"])) > 1e-6:
            mismatches += 1
    post["value_mismatches"] = mismatches
    con.close()

    post_sha = sha256(DB)
    result = {
        "batch": "batch002",
        "mode": "apply",
        "applied": len(applied),
        "source": stats["source"],
        "stats": stats,
        "backup": backup,
        "backup_timestamp": ts,
        "pre_sha256": pre_sha,
        "backup_sha256": backup_sha,
        "baseline": base,
        "post_apply": post,
        "post_sha256": post_sha,
        "applied_updates": applied,
    }
    with open(APPLY_RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"APPLIED {len(applied)} updates")
    print(f"pre_sha256 : {pre_sha}")
    print(f"backup     : {backup}")
    print(f"post_sha256: {post_sha}")
    print(f"coverage   : {base['coverage']} -> {post['coverage']}")
    print(f"quick_check: {post['quick_check']} | value_mismatches: {mismatches}")
    return result


def _load_rows(con, schema, table):
    prefix = f"{schema}." if schema else ""
    cols = [r[1] for r in con.execute(f"PRAGMA {prefix}table_info({table})")]
    pk = "id"
    rows = {}
    for r in con.execute(f"SELECT * FROM {prefix}{table}"):
        rows[r[pk]] = {c: r[c] for c in cols}
    return cols, rows


def mode_verify():
    with open(APPLY_RESULTS_JSON, encoding="utf-8") as f:
        result = json.load(f)
    backup = result["backup"]
    records, stats = plan(db_path=backup)  # independent recomputation from source + pre-apply backup
    safe = {r["hardware_id"]: r for r in records if r["status"] == "safe_update"}

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute(f"ATTACH DATABASE 'file:{backup}?mode=ro' AS pre")

    report = {"checks": {}, "verdict": "PASS"}

    def fail(check, detail):
        report["checks"][check] = {"ok": False, "detail": detail}
        report["verdict"] = "FAIL"

    def ok(check, detail):
        report["checks"][check] = {"ok": True, "detail": detail}

    # 1. quick_check
    qc = con.execute("PRAGMA quick_check").fetchone()[0]
    (ok if qc == "ok" else fail)("quick_check", qc)

    # 2. hashes
    pre_backup_sha = sha256(backup)
    post_sha = sha256(DB)
    (ok if pre_backup_sha == result["backup_sha256"] else fail)(
        "backup_hash", {"backup": backup, "sha256": pre_backup_sha})

    # 3. every applied value matches its source record + NULL guard held
    applied_ok = True
    value_mismatch = []
    for hid, rec in safe.items():
        got = con.execute("SELECT core_clock_mhz FROM gpu_specifications WHERE hardware_id=?",
                          (hid,)).fetchone()[0]
        if got is None or abs(float(got) - float(rec["target_value"])) > 1e-6:
            applied_ok = False
            value_mismatch.append((hid, got, rec["target_value"]))
    (ok if applied_ok else fail)("applied_values_match_source",
        f"{len(safe)} safe updates; {len(value_mismatch)} mismatches")

    # 4. no populated value overwritten: cell-level diff backup vs current
    changed = []
    pre_rows_hwid = {}
    for t in TABLES:
        cols, cur_rows = _load_rows(con, None, t)
        _, pre_rows = _load_rows(con, "pre", t)
        if t == TARGET_TABLE:
            pre_rows_hwid = {rid: r.get("hardware_id") for rid, r in pre_rows.items()}
        if set(cur_rows) != set(pre_rows):
            fail("row_identity_stable", f"{t}: id sets differ")
        for rid in set(cur_rows) & set(pre_rows):
            for c in cols:
                a, b = pre_rows[rid].get(c), cur_rows[rid].get(c)
                if a != b:
                    changed.append((t, rid, c, a, b))
    allowed = []
    unexpected = []
    for (t, rid, c, a, b) in changed:
        if t == TARGET_TABLE and c == TARGET_COLUMN and a is None:
            hwid = pre_rows_hwid.get(rid)
            if hwid in safe and abs(float(b) - float(safe[hwid]["target_value"])) <= 1e-6:
                allowed.append((t, rid, c, a, b))
                continue
        unexpected.append((t, rid, c, a, b))
    (ok if not unexpected else fail)("only_intended_cells_changed",
        {"changed_cells": len(changed), "allowed": len(allowed),
         "unexpected": unexpected[:20]})

    # 5. no duplicate target updates
    ids = [r["hardware_id"] for r in records if r["status"] == "safe_update"]
    (ok if len(ids) == len(set(ids)) else fail)("no_duplicate_updates", len(ids))

    # 6. row counts unchanged
    post_counts = table_counts(con)
    pre_counts = {t: con.execute(f"SELECT COUNT(*) FROM pre.{t}").fetchone()[0] for t in TABLES}
    pre_counts["hardware_cpu"] = con.execute("SELECT COUNT(*) FROM pre.hardware WHERE type='CPU'").fetchone()[0]
    pre_counts["hardware_gpu"] = con.execute("SELECT COUNT(*) FROM pre.hardware WHERE type='GPU'").fetchone()[0]
    (ok if post_counts == pre_counts else fail)(
        "row_counts_unchanged", {"before": pre_counts, "after": post_counts})

    # 7. coverage before/after
    cov_after = coverage(con)
    total = cov_after["gpu_specs"]
    nn_before = con.execute("SELECT COUNT(*) FROM pre.gpu_specifications WHERE core_clock_mhz IS NOT NULL").fetchone()[0]
    cov_before = {"core_clock_nonnull": nn_before, "core_clock_null": total - nn_before,
                  "coverage_pct": round(100.0 * nn_before / total, 2)}
    (ok if cov_after["core_clock_nonnull"] == nn_before + len(allowed) else fail)(
        "coverage_delta", {"before": cov_before, "after": cov_after, "applied": len(allowed)})

    # 8. benchmark rows unchanged; GPU benchmark count zero
    bench_after = con.execute("SELECT COUNT(*) FROM benchmark_results").fetchone()[0]
    bench_before = con.execute("SELECT COUNT(*) FROM pre.benchmark_results").fetchone()[0]
    gpu_bench = gpu_benchmark_count(con)
    gaming = con.execute(
        "SELECT COUNT(*) FROM benchmark_results WHERE lower(benchmark_name) LIKE '%gaming%' "
        "OR lower(test_type) LIKE '%gaming%'").fetchone()[0]
    (ok if bench_after == bench_before and gpu_bench == 0 and gaming == 0 else fail)(
        "benchmarks_untouched_and_no_gpu_gaming",
        {"benchmark_rows_before": bench_before, "benchmark_rows_after": bench_after,
         "gpu_benchmark_rows": gpu_bench, "gaming_rows": gaming})

    con.close()
    report["backup"] = backup
    report["backup_sha256"] = pre_backup_sha
    report["post_sha256"] = post_sha
    report["stats"] = stats
    report["coverage_before"] = cov_before
    report["coverage_after"] = cov_after
    report["applied"] = len(allowed)
    with open(os.path.join(BATCH, "audit_results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if mode == "generate":
        mode_generate()
    elif mode == "apply":
        mode_apply()
    elif mode == "verify":
        mode_verify()
    else:
        sys.exit("usage: enrich_batch002.py [generate|apply|verify]")
