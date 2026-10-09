"""
SPECTRA Batch 003 - CPU metadata expansion (architecture / release date / AMD process node).

Source: Wikipedia microarchitecture articles (CC BY-SA 4.0).
  - Batch 001 local table extracts: data/research/batch001/sources/*.tables.txt
  - Batch 003 local table extracts: data/research/batch003/sources/*.tables.txt
    (fetched during this batch; provenance in sources/provenance.json)

Per-article URL is recorded per value. Architecture is taken from the source
article's subject (the platform codename convention established by Batch 001),
which is deterministic: a CPU model listed in the "Kaby Lake" article is a Kaby
Lake CPU. A model appearing in more than one article, or matching more than one
hardware row, is excluded as ambiguous/colliding.

Not imported (documented in 04_mapping_and_exclusions.md):
  - boost clock / TDP: the source tables' merged P/E & GPU columns make
    per-model extraction unreliable (validation vs existing DB values showed a
    high disagreement rate), so no value is imported.
  - Intel process node: already populated; not a source-supported per-model gap.
  - AMD process node: imported only where a source-confirmed architecture maps
    to a single documented node (family-level fact).

Modes: generate | apply | verify
"""

import collections
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
BATCH = os.path.join(REPO, "data", "research", "batch003")
DB = os.path.join(REPO, "data", "spectra.db")
BACKUP_DIR = os.path.join(REPO, "data", "backups")
SRC1 = os.path.join(REPO, "data", "research", "batch001", "sources")
SRC2 = os.path.join(BATCH, "sources")

EVIDENCE_CSV = os.path.join(BATCH, "03_evidence_table.csv")
PATCH_JSON = os.path.join(BATCH, "05_database_patch.json")
STATS_JSON = os.path.join(BATCH, "batch003_stats.json")
APPLY_JSON = os.path.join(BATCH, "apply_results.json")
AUDIT_JSON = os.path.join(BATCH, "audit_results.json")

WIKI = "https://en.wikipedia.org/wiki/"

# stem -> (architecture, source_dir, article_url)
SOURCES = {
    # Batch 001 local extracts
    "alder_lake": ("Alder Lake", 1, WIKI + "Alder_Lake"),
    "raptor_lake": ("Raptor Lake", 1, WIKI + "Raptor_Lake"),
    "rocket_lake": ("Rocket Lake", 1, WIKI + "Rocket_Lake"),
    "wiki_Coffee_Lake": ("Coffee Lake", 1, WIKI + "Coffee_Lake"),
    "wiki_Comet_Lake": ("Comet Lake", 1, WIKI + "Comet_Lake"),
    "wiki_Haswell__microarchitecture_": ("Haswell", 1, WIKI + "Haswell_(microarchitecture)"),
    "wiki_Ivy_Bridge__microarchitecture_": ("Ivy Bridge", 1, WIKI + "Ivy_Bridge_(microarchitecture)"),
    "wiki_Kaby_Lake": ("Kaby Lake", 1, WIKI + "Kaby_Lake"),
    "wiki_Sandy_Bridge__microarchitecture_": ("Sandy Bridge", 1, WIKI + "Sandy_Bridge_(microarchitecture)"),
    "wiki_Skylake__microarchitecture_": ("Skylake", 1, WIKI + "Skylake_(microarchitecture)"),
    "wiki_Zen_2": ("Zen 2", 1, WIKI + "Zen_2"),
    "wiki_Zen_2B": ("Zen+", 1, WIKI + "Zen%2B"),
    "wiki_Zen_3": ("Zen 3", 1, WIKI + "Zen_3"),
    "wiki_Zen_4": ("Zen 4", 1, WIKI + "Zen_4"),
    "wiki_Zen__microarchitecture_": ("Zen", 1, WIKI + "Zen_(microarchitecture)"),
    # Batch 003 fetched extracts
    "Broadwell_microarchitecture": ("Broadwell", 2, WIKI + "Broadwell_(microarchitecture)"),
    "Ice_Lake_microprocessor": ("Ice Lake", 2, WIKI + "Ice_Lake_(microprocessor)"),
    "Tiger_Lake": ("Tiger Lake", 2, WIKI + "Tiger_Lake"),
    "Nehalem_microarchitecture": ("Nehalem", 2, WIKI + "Nehalem_(microarchitecture)"),
    "Westmere_microarchitecture": ("Westmere", 2, WIKI + "Westmere_(microarchitecture)"),
    "Cannon_Lake_microprocessor": ("Cannon Lake", 2, WIKI + "Cannon_Lake_(microprocessor)"),
    "Whiskey_Lake": ("Whiskey Lake", 2, WIKI + "Whiskey_Lake"),
}

# documented AMD family process node (chiplet/CCD/primary), per Batch 001 convention
AMD_NODE = {"Zen": 14.0, "Zen+": 12.0, "Zen 2": 7.0, "Zen 3": 7.0, "Zen 4": 5.0}

LEAD = ("intel", "amd", "ati")
EVIDENCE_COLUMNS = [
    "hardware_id", "hardware_name", "manufacturer", "field",
    "source_value", "target_value", "source_name", "source_url",
    "source_reference", "confidence", "match_method", "status", "caveat",
]
TABLES = ("hardware", "cpu_specifications", "gpu_specifications", "benchmark_results",
          "external_identifiers", "sources", "build_conversations", "build_messages")
FIELD_TABLE = {"architecture": "hardware", "release_date": "hardware",
               "process_node_nm": "cpu_specifications"}


def normalize_key(s):
    s = (s or "").lower()
    s = re.sub(r"@.*$", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("processor", "")
    s = re.sub(r"[^a-z0-9]", "", s)
    for p in LEAD:
        if s.startswith(p):
            return s[len(p):]
    return s


def parse_release(v):
    if v is None:
        return None
    v = re.sub(r"\s*;\s*\d+.*$", "", v.strip())
    v = re.sub(r"\s*\[\d+\]\s*", " ", v)
    v = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", v)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        try:
            return datetime.date(*map(int, m.groups())).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", v)
    if m:
        try:
            return datetime.datetime.strptime(
                f"{m.group(1)[:3].title()} {m.group(2)} {m.group(3)}", "%b %d %Y").date().isoformat()
        except ValueError:
            return None
    return None


def parse_file(path, arch):
    text = open(path, encoding="utf-8").read().splitlines()
    tables, cur = [], None
    for line in text:
        if line.startswith("### TABLE"):
            cur = []
            tables.append(cur)
        elif cur is not None:
            cur.append(line)
    out = []
    for ti, tbl in enumerate(tables):
        rows = [[c.strip() for c in l.split("|")] for l in tbl if l.strip()]
        hi = None
        for i, r in enumerate(rows):
            low = [c.lower() for c in r]
            if "model" in low or any(c in ("processor branding and model", "branding and model") for c in low):
                hi = i
                break
        if hi is None:
            continue
        header = [c.lower() for c in rows[hi]]
        ncols = len(header)
        model_idx = next((i for i, c in enumerate(header) if c == "model"), None)
        combined_idx = None
        if model_idx is None:
            combined_idx = next((i for i, c in enumerate(header)
                                 if c in ("processor branding and model", "branding and model")), None)
        if model_idx is None and combined_idx is None:
            continue
        brand_idx = next((i for i, c in enumerate(header)
                          if c in ("processor branding", "branding and model")), None)
        rel_idx = next((i for i, c in enumerate(header) if "release" in c), None)
        carries = ""
        for r in rows[hi + 1:]:
            if len(r) < ncols:
                continue
            if combined_idx is not None:
                full = r[combined_idx]
            else:
                brand = r[brand_idx] if brand_idx is not None and brand_idx < len(r) else ""
                if brand:
                    carries = brand
                else:
                    brand = carries
                full = (brand + " " + r[model_idx]).strip()
            if not re.search(r"\d", full):
                continue
            low = full.lower()
            if low.startswith("model") or "section" in low:
                continue
            out.append({"full": full, "key": normalize_key(full),
                        "release": r[rel_idx] if rel_idx is not None and rel_idx < len(r) else None,
                        "reference": f"{os.path.basename(path)}::TABLE {ti}"})
    return out


def load_source_rows():
    rows = []
    for stem, (arch, srcdir, url) in SOURCES.items():
        d = SRC1 if srcdir == 1 else SRC2
        path = os.path.join(d, stem + ".tables.txt")
        if not os.path.exists(path):
            continue
        for r in parse_file(path, arch):
            r["arch"] = arch
            r["url"] = url
            rows.append(r)
    return rows


def load_db_cpus(readonly=True, db_path=None):
    path = db_path or DB
    con = sqlite3.connect(f"file:{path}?mode=ro" if readonly else path, uri=readonly)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("""
        SELECT h.id AS hardware_id, h.name AS hardware_name, h.manufacturer,
               h.architecture, h.release_date, c.process_node_nm
        FROM hardware h JOIN cpu_specifications c ON c.hardware_id = h.id
        WHERE h.type='CPU'""")]
    con.close()
    return rows


def plan(db_path=None):
    src = load_source_rows()
    key2arch = collections.defaultdict(set)
    key2rel = collections.defaultdict(set)
    key2ref = collections.defaultdict(set)
    key2url = {}
    for r in src:
        if not r["key"]:
            continue
        key2arch[r["key"]].add(r["arch"])
        key2ref[r["key"]].add(r["reference"])
        key2url.setdefault(r["key"], r["url"])
        pr = parse_release(r["release"])
        if pr:
            key2rel[r["key"]].add(pr)

    db = load_db_cpus(db_path=db_path)
    db_by_key = collections.defaultdict(list)
    for d in db:
        db_by_key[normalize_key(d["hardware_name"])].append(d)

    evidence = []
    stats = collections.Counter()
    stats["gpus_total"] = 0
    stats["cpus_total"] = len(db)
    stats["cpus_missing_architecture"] = sum(1 for d in db if not d["architecture"])
    stats["cpus_missing_release_date"] = sum(1 for d in db if not d["release_date"])
    stats["cpus_missing_process_node"] = sum(1 for d in db if d["process_node_nm"] is None)
    for k, archs in key2arch.items():
        rows = db_by_key.get(k)
        if not rows:
            continue
        if len(archs) > 1:
            stats["excluded_multi_arch_keys"] += 1
            continue
        arch = next(iter(archs))
        if len(rows) > 1:
            stats["excluded_collisions"] += 1
            for d in rows:
                evidence.append({
                    "hardware_id": d["hardware_id"], "hardware_name": d["hardware_name"],
                    "manufacturer": d["manufacturer"], "field": "architecture",
                    "source_value": arch, "target_value": "", "source_name": "Wikipedia (CC BY-SA)",
                    "source_url": key2url.get(k, ""), "source_reference": ";".join(sorted(key2ref[k])),
                    "confidence": "rejected", "match_method": "exact normalized name",
                    "status": "excluded", "caveat": "one source key matches multiple hardware rows (collision)",
                })
            continue
        d = rows[0]
        refs = ";".join(sorted(key2ref[k]))
        if not d["architecture"]:
            evidence.append({
                "hardware_id": d["hardware_id"], "hardware_name": d["hardware_name"],
                "manufacturer": d["manufacturer"], "field": "architecture",
                "source_value": arch, "target_value": arch, "source_name": "Wikipedia (CC BY-SA)",
                "source_url": key2url.get(k, ""), "source_reference": refs,
                "confidence": "high", "match_method": "exact normalized CPU name -> source microarchitecture article",
                "status": "proposed", "caveat": "",
            })
            stats["arch_proposed"] += 1
        rels = key2rel.get(k, set())
        if not d["release_date"] and len(rels) == 1:
            evidence.append({
                "hardware_id": d["hardware_id"], "hardware_name": d["hardware_name"],
                "manufacturer": d["manufacturer"], "field": "release_date",
                "source_value": next(iter(rels)), "target_value": next(iter(rels)),
                "source_name": "Wikipedia (CC BY-SA)", "source_url": key2url.get(k, ""),
                "source_reference": refs, "confidence": "high",
                "match_method": "exact normalized CPU name -> full release date in source table",
                "status": "proposed", "caveat": "full date only; quarter/year-only evidence ignored",
            })
            stats["release_proposed"] += 1
        if d["manufacturer"] == "AMD" and d["process_node_nm"] is None and arch in AMD_NODE:
            evidence.append({
                "hardware_id": d["hardware_id"], "hardware_name": d["hardware_name"],
                "manufacturer": d["manufacturer"], "field": "process_node_nm",
                "source_value": arch, "target_value": AMD_NODE[arch],
                "source_name": "Wikipedia (CC BY-SA)", "source_url": key2url.get(k, ""),
                "source_reference": refs, "confidence": "medium",
                "match_method": "source-confirmed architecture -> documented family node",
                "status": "proposed", "caveat": "family-level node (chiplet/CCD), Batch 001 convention",
            })
            stats["node_proposed"] += 1

    stats["source_rows"] = len(src)
    stats["source_distinct_keys"] = len(key2arch)
    stats["evidence_rows"] = len(evidence)
    stats["total_proposed"] = stats["arch_proposed"] + stats["release_proposed"] + stats["node_proposed"]
    return evidence, stats


def write_artifacts(evidence, stats):
    os.makedirs(BATCH, exist_ok=True)
    with open(EVIDENCE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EVIDENCE_COLUMNS)
        w.writeheader()
        for e in evidence:
            w.writerow({k: e.get(k, "") for k in EVIDENCE_COLUMNS})

    updates = []
    for e in evidence:
        if e["status"] != "proposed":
            continue
        updates.append({
            "table": FIELD_TABLE[e["field"]], "hardware_id": e["hardware_id"],
            "column": e["field"], "new_value": e["target_value"],
            "guard": f"{e['field']} IS NULL",
            "source": e["source_name"], "source_url": e["source_url"],
            "source_reference": e["source_reference"], "confidence": e["confidence"],
            "match_method": e["match_method"],
        })
    with open(PATCH_JSON, "w", encoding="utf-8") as f:
        json.dump({"batch": "batch003", "applied": False, "stats": stats, "updates": updates,
                   "excluded": [e for e in evidence if e["status"] != "proposed"]},
                  f, indent=2, ensure_ascii=False)
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    return updates


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def field_coverage(con):
    out = {}
    out["architecture_nonnull"] = con.execute("SELECT COUNT(*) FROM hardware WHERE type='CPU' AND architecture IS NOT NULL").fetchone()[0]
    out["release_date_nonnull"] = con.execute("SELECT COUNT(*) FROM hardware WHERE type='CPU' AND release_date IS NOT NULL").fetchone()[0]
    out["process_node_nm_nonnull"] = con.execute("SELECT COUNT(*) FROM cpu_specifications WHERE process_node_nm IS NOT NULL").fetchone()[0]
    out["boost_clock_ghz_nonnull"] = con.execute("SELECT COUNT(*) FROM cpu_specifications WHERE boost_clock_ghz IS NOT NULL").fetchone()[0]
    out["tdp_w_nonnull"] = con.execute("SELECT COUNT(*) FROM cpu_specifications WHERE tdp_w IS NOT NULL").fetchone()[0]
    out["cpus_total"] = con.execute("SELECT COUNT(*) FROM hardware WHERE type='CPU'").fetchone()[0]
    return out


def table_counts(con):
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


def gpu_benchmark_count(con):
    return con.execute(
        "SELECT COUNT(*) FROM benchmark_results b JOIN hardware h ON h.id=b.hardware_id WHERE h.type='GPU'"
    ).fetchone()[0]


IDCOL = {"hardware": "id", "cpu_specifications": "hardware_id"}


def baseline(con):
    return {
        "db": DB, "sha256": sha256(DB), "size_bytes": os.path.getsize(DB),
        "quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
        "counts": table_counts(con), "coverage": field_coverage(con),
        "gpu_benchmark_rows": gpu_benchmark_count(con),
    }


def make_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = os.path.join(BACKUP_DIR, f"spectra-pre-batch003-cpumeta-{ts}.db")
    shutil.copy2(DB, dst)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(DB + suffix):
            shutil.copy2(DB + suffix, dst + suffix)
    return dst, ts


def mode_apply():
    evidence, stats = plan()
    write_artifacts(evidence, stats)
    updates = [e for e in evidence if e["status"] == "proposed"]

    pre_sha = sha256(DB)
    con = sqlite3.connect(DB, isolation_level=None)
    con.row_factory = sqlite3.Row
    base = baseline(con)
    backup, ts = make_backup()
    backup_sha = sha256(backup)
    if backup_sha != pre_sha:
        con.close()
        raise RuntimeError("backup hash mismatch - aborting")

    applied = []
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("BEGIN IMMEDIATE")
    try:
        for e in updates:
            table = FIELD_TABLE[e["field"]]
            idcol = IDCOL[table]
            col = e["field"]
            row = con.execute(f"SELECT {col} AS v FROM {table} WHERE {idcol}=?", (e["hardware_id"],)).fetchone()
            if row is None:
                raise RuntimeError(f"missing row {table}:{e['hardware_id']}")
            if row["v"] is not None:
                raise RuntimeError(f"{table}.{col} not NULL for {e['hardware_id']} - aborting")
            cur = con.execute(
                f"UPDATE {table} SET {col}=? WHERE {idcol}=? AND {col} IS NULL",
                (e["target_value"], e["hardware_id"]))
            if cur.rowcount != 1:
                raise RuntimeError(f"guard affected {cur.rowcount} rows for {table}:{e['hardware_id']}.{col}")
            applied.append({"table": table, "hardware_id": e["hardware_id"], "column": col,
                            "new_value": e["target_value"], "source_reference": e["source_reference"]})
        if len(applied) != len(updates):
            raise RuntimeError("applied count mismatch")
    except Exception:
        con.execute("ROLLBACK")
        con.close()
        raise
    con.execute("COMMIT")

    post = {"quick_check": con.execute("PRAGMA quick_check").fetchone()[0],
            "counts": table_counts(con), "coverage": field_coverage(con),
            "gpu_benchmark_rows": gpu_benchmark_count(con)}
    mism = 0
    for e in updates:
        table = FIELD_TABLE[e["field"]]
        got = con.execute(f"SELECT {e['field']} FROM {table} WHERE {IDCOL[table]}=?",
                          (e["hardware_id"],)).fetchone()[0]
        if str(got) != str(e["target_value"]):
            mism += 1
    post["value_mismatches"] = mism
    con.close()
    post_sha = sha256(DB)
    result = {"batch": "batch003", "applied": len(applied), "stats": stats,
              "backup": backup, "backup_timestamp": ts, "pre_sha256": pre_sha,
              "backup_sha256": backup_sha, "baseline": base, "post_apply": post,
              "post_sha256": post_sha, "applied_updates": applied}
    with open(APPLY_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"APPLIED {len(applied)}")
    print(f"pre_sha256 : {pre_sha}")
    print(f"backup     : {backup}")
    print(f"post_sha256: {post_sha}")
    print(f"coverage before: {base['coverage']}")
    print(f"coverage after : {post['coverage']}")
    print(f"quick_check: {post['quick_check']} | value_mismatches: {mism}")
    return result


def _load_rows(con, schema, table):
    prefix = f"{schema}." if schema else ""
    cols = [r[1] for r in con.execute(f"PRAGMA {prefix}table_info({table})")]
    rows = {}
    for r in con.execute(f"SELECT * FROM {prefix}{table}"):
        rows[r["id"]] = {c: r[c] for c in cols}
    return cols, rows


def mode_verify():
    with open(APPLY_JSON, encoding="utf-8") as f:
        result = json.load(f)
    backup = result["backup"]
    evidence, stats = plan(db_path=backup)  # recompute against pre-apply backup
    proposed = [e for e in evidence if e["status"] == "proposed"]
    proposed_by = {(e["field"], e["hardware_id"]): e for e in proposed}

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute(f"ATTACH DATABASE 'file:{backup}?mode=ro' AS pre")
    report = {"checks": {}, "verdict": "PASS"}

    def ok(c, d): report["checks"][c] = {"ok": True, "detail": d}
    def fail(c, d): report["checks"][c] = {"ok": False, "detail": d}; report["verdict"] = "FAIL"

    qc = con.execute("PRAGMA quick_check").fetchone()[0]
    (ok if qc == "ok" else fail)("quick_check", qc)

    bsha = sha256(backup)
    (ok if bsha == result["backup_sha256"] else fail)("backup_hash",
        {"backup": backup, "sha256": bsha})

    # applied values match evidence
    bad = []
    for e in proposed:
        table = FIELD_TABLE[e["field"]]
        got = con.execute(f"SELECT {e['field']} FROM {table} WHERE {IDCOL[table]}=?",
                          (e["hardware_id"],)).fetchone()[0]
        if got is None or str(got) != str(e["target_value"]):
            bad.append((e["field"], e["hardware_id"], got, e["target_value"]))
    (ok if not bad else fail)("applied_values_match_evidence",
        f"{len(proposed)} proposed; {len(bad)} mismatches")

    # cell-level diff
    changed = []
    pre_hw = {}
    for t in TABLES:
        cols, cur_rows = _load_rows(con, None, t)
        _, pre_rows = _load_rows(con, "pre", t)
        if t == "hardware":
            pre_hw = {rid: r.get("type") for rid, r in pre_rows.items()}
        if set(cur_rows) != set(pre_rows):
            fail("row_identity_stable", f"{t} id sets differ")
        for rid in set(cur_rows) & set(pre_rows):
            for c in cols:
                a, b = pre_rows[rid].get(c), cur_rows[rid].get(c)
                if a != b:
                    changed.append((t, rid, c, a, b))
    # map hardware pk -> (type) to resolve cpu_spec hardware_id
    allowed, unexpected = 0, []
    for (t, rid, c, a, b) in changed:
        matched = False
        if t == "hardware":
            key = ("architecture" if c == "architecture" else "release_date", rid)
            e = proposed_by.get(key)
            if e and a is None and str(b) == str(e["target_value"]):
                allowed += 1; matched = True
        elif t == "cpu_specifications" and c == "process_node_nm":
            # rid is cpu_specifications.id; find hardware_id from pre row
            hw = con.execute("SELECT hardware_id FROM pre.cpu_specifications WHERE id=?", (rid,)).fetchone()
            if hw:
                e = proposed_by.get(("process_node_nm", hw[0]))
                if e and a is None and str(b) == str(e["target_value"]):
                    allowed += 1; matched = True
        if not matched:
            unexpected.append((t, rid, c, a, b))
    (ok if not unexpected else fail)("only_intended_cells_changed",
        {"changed_cells": len(changed), "allowed": allowed, "unexpected": unexpected[:20]})

    pairs = [(e["field"], e["hardware_id"]) for e in proposed]
    (ok if len(pairs) == len(set(pairs)) else fail)("no_duplicate_field_target", len(pairs))

    post_counts = table_counts(con)
    pre_counts = {t: con.execute(f"SELECT COUNT(*) FROM pre.{t}").fetchone()[0] for t in TABLES}
    (ok if post_counts == pre_counts else fail)("row_counts_unchanged",
        {"before": pre_counts, "after": post_counts})

    cov_after = field_coverage(con)
    cov_before = {
        "architecture_nonnull": con.execute("SELECT COUNT(*) FROM pre.hardware WHERE type='CPU' AND architecture IS NOT NULL").fetchone()[0],
        "release_date_nonnull": con.execute("SELECT COUNT(*) FROM pre.hardware WHERE type='CPU' AND release_date IS NOT NULL").fetchone()[0],
        "process_node_nm_nonnull": con.execute("SELECT COUNT(*) FROM pre.cpu_specifications WHERE process_node_nm IS NOT NULL").fetchone()[0],
    }
    (ok if cov_after["architecture_nonnull"] == cov_before["architecture_nonnull"] + stats["arch_proposed"]
        and cov_after["release_date_nonnull"] == cov_before["release_date_nonnull"] + stats["release_proposed"]
        and cov_after["process_node_nm_nonnull"] == cov_before["process_node_nm_nonnull"] + stats["node_proposed"]
     else fail)("coverage_delta", {"before": cov_before, "after": cov_after})

    bench_after = con.execute("SELECT COUNT(*) FROM benchmark_results").fetchone()[0]
    bench_before = con.execute("SELECT COUNT(*) FROM pre.benchmark_results").fetchone()[0]
    gpu_b = gpu_benchmark_count(con)
    gaming = con.execute("SELECT COUNT(*) FROM benchmark_results WHERE lower(benchmark_name) LIKE '%gaming%' OR lower(test_type) LIKE '%gaming%'").fetchone()[0]
    (ok if bench_after == bench_before and gpu_b == 0 and gaming == 0 else fail)(
        "benchmarks_untouched", {"before": bench_before, "after": bench_after, "gpu": gpu_b, "gaming": gaming})

    con.close()
    report.update({"backup": backup, "backup_sha256": bsha, "post_sha256": sha256(DB),
                   "coverage_before": cov_before, "coverage_after": cov_after, "stats": stats})
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if mode == "generate":
        ev, st = plan()
        write_artifacts(ev, st)
        print(json.dumps(st, indent=2))
    elif mode == "apply":
        mode_apply()
    elif mode == "verify":
        mode_verify()
    else:
        sys.exit("usage: enrich_batch003.py [generate|apply|verify]")
