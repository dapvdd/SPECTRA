"""Batch 017 dry-run: match GPU Ark rows to SPECTRA GPU identities.

Produces a coverage report showing how many SPEC gaps can be filled,
what conflicts exist, and what stays quarantined.

Matching strategy (conservative, deterministic):
  1. Normalized name match (vendor prefix stripped) — same as batch002.
  2. Boost clock corroboration: if SPECTRA already has boost_clock_mhz,
     GPU Ark's boost must be within BOOST_TOL MHz.
  3. NULL-only guard: never overwrite an existing value.
  4. Ambiguous matches (multiple candidates with different values) → quarantine.
  5. bus_interface used for PCIe interface; falls back to bus_width inference.
  6. memory_bus_width_bits: only updated if not already present.
"""

import collections
import csv
import datetime
import hashlib
import json
import re
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGING_DB = REPO / "data" / "spectra_staging.db"
ARK_CSV = REPO / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv"
META_JSON = REPO / "data" / "research" / "batch017" / "source_metadata.json"

sys_path = str(REPO)
import sys
sys.path.insert(0, sys_path)

# Import the same normalizer used historically by batch002.
from backend.app.importers.benchmark_normalizer import normalize_name

VENDOR_MAP = {"nvd": "NVIDIA", "amd": "AMD", "int": "Intel"}
CHIP_PREFIXES = ("nvidia ", "amd ", "ati ", "intel ")

BOOST_TOL_MHZ = 10.0

# GPU Ark column → SPECTRA gpu_specifications column
# None means: column already well-covered, fill only NULLs
FIELD_MAP = {
    "bus_interface":  {"col": "interface",          "nulls_ok": True, "corroborate": False},
    "boost_clock":    {"col": "boost_clock_mhz",    "nulls_ok": True, "corroborate": False},
    "tdp":            {"col": "tdp_w",               "nulls_ok": True, "corroborate": False},
    "length_mm":      {"col": "length_mm",           "nulls_ok": True, "corroborate": False},
    "ram":            {"col": "memory_gb",           "nulls_ok": True, "corroborate": False},
    "ram_type":       {"col": "memory_type",         "nulls_ok": True, "corroborate": False},
    "bus_width":      {"col": "memory_bus_width_bits","nulls_ok": True, "corroborate": False},
    "ram_bandwidth":  {"col": "vram_bandwidth_gbps", "nulls_ok": True, "corroborate": False},
    "base_clock":     {"col": "core_clock_mhz",      "nulls_ok": True, "corroborate": False},
}


def strip_chip_prefix(name):
    low = (name or "").lower()
    for p in CHIP_PREFIXES:
        if low.startswith(p):
            return name[len(p):].strip()
    return name


def ark_nname(name):
    return strip_chip_prefix(normalize_name(name) or "").strip()


def vendor_ok(ark_vendor, db_mfr):
    av = VENDOR_MAP.get((ark_vendor or "").strip(), (ark_vendor or "").strip())
    return av == db_mfr or {av, db_mfr} <= {"AMD", "ATI"}


def _float(s):
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        v = float(s)
        return None if v == 0 else v
    except ValueError:
        return None


def load_ark():
    rows = []
    with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            raw_ram = (row.get("ram") or "").strip()
            ram_gb = None
            if raw_ram:
                try:
                    val = float(raw_ram)
                    ram_gb = val / 1024.0 if val >= 256 else val  # MB→GB per dataset card
                except ValueError:
                    pass
            rows.append({
                "id":             row.get("id", "").strip(),
                "name":           row.get("name", "").strip(),
                "vendor":         (row.get("vendor") or "").strip(),
                "manufacturer":   (row.get("manufacturer") or "").strip(),
                "arch_name":      row.get("arch_name", "").strip(),
                "base_clock":     _float(row.get("base_clock")),
                "boost_clock":    _float(row.get("boost_clock")),
                "ram":            ram_gb,
                "ram_raw":        raw_ram,
                "ram_type":       (row.get("ram_type") or "").strip(),
                "bus_width":      _float(row.get("bus_width")),
                "bus_interface":  (row.get("bus_interface") or "").strip(),
                "ram_bandwidth": _float(row.get("ram_bandwidth")),
                "tdp":            _float(row.get("tdp")),
                "length_mm":      _float(row.get("length_mm")),
                "nname":          ark_nname(row.get("name")),
                "nv":             VENDOR_MAP.get((row.get("vendor") or "").strip(),
                                                 (row.get("vendor") or "").strip()),
            })
    return rows


def build_ark_index(ark_rows):
    idx = collections.defaultdict(list)
    for a in ark_rows:
        idx[a["nname"]].append(a)
    return idx


def _db(spec_row, col, db_row):
    """Return existing DB value for col, or None."""
    if col in spec_row and spec_row[col] is not None:
        return spec_row[col]
    return None


def run_dryrun():
    meta = json.loads(META_JSON.read_text())

    con = sqlite3.connect(f"file:{STAGING_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    # Load all GPU hardware + their spec rows
    gpu_rows = {}
    for r in con.execute(
        """SELECT h.id, h.name, h.manufacturer, h.segment,
                  g.memory_gb, g.memory_type, g.core_clock_mhz, g.boost_clock_mhz,
                  g.vram_bandwidth_gbps, g.tdp_w, g.interface, g.length_mm,
                  g.memory_bus_width_bits
           FROM hardware h JOIN gpu_specifications g ON g.hardware_id = h.id
           WHERE h.type='GPU'"""
    ):
        gpu_rows[r["id"]] = dict(r)

    # Load GPU Ark
    ark_rows = load_ark()
    ark_idx = build_ark_index(ark_rows)

    # Baseline coverage
    fields = ["boost_clock_mhz", "tdp_w", "interface", "length_mm",
              "memory_gb", "memory_type", "memory_bus_width_bits",
              "vram_bandwidth_gbps", "core_clock_mhz"]
    baseline = {}
    for f in fields:
        col = f"gpu_spec.{f}" if f in ("memory_gb", "memory_type") else f"gpu_spec.{f}"
        nulls = sum(1 for r in gpu_rows.values()
                     if r.get(f if "gpu_spec." not in f else None) is None)
        filled = len(gpu_rows) - nulls
        baseline[f] = {"filled": filled, "missing": nulls, "pct": round(100.0*filled/len(gpu_rows), 1)}
        # fix column names for gpu_spec inner join
        pass

    # Re-compute baseline cleanly
    gpu_total = len(gpu_rows)
    base = {}
    for f in fields:
        filled = sum(1 for r in gpu_rows.values() if r[f] is not None)
        base[f] = {"filled": filled, "missing": gpu_total - filled,
                   "pct": round(100.0 * filled / gpu_total, 1)}
    print("=== SPECTRA GPU baseline coverage ===")
    for f in fields:
        print(f"  {f:25} {base[f]['filled']:5} filled  {base[f]['missing']:4} missing  {base[f]['pct']:.1f}%")
    print(f"  total GPU rows: {gpu_total}")

    # Per-field result tracking
    results_by_field = {f: collections.defaultdict(int) for f in FIELD_MAP}
    records = []
    quarantined = []
    reason_counts = collections.Counter()

    for hwid, r in gpu_rows.items():
        norm = normalize_name(r["name"]) or ""
        candidates = [
            a for a in ark_idx.get(norm, [])
            if vendor_ok(a["nv"], r["manufacturer"])
        ]

        # For each field, determine if we can safely update
        for ark_col, info in FIELD_MAP.items():
            spec_col = info["col"]
            existing = r.get(spec_col)
            if existing is not None:
                results_by_field[ark_col]["already_filled"] += 1
                continue

            if not candidates:
                results_by_field[ark_col]["unmatched"] += 1
                reason_counts[f"{ark_col}:no_ark_match"] += 1
                continue

            # Check boost corroboration for clock fields
            db_boost = r.get("boost_clock_mhz")
            if ark_col in ("base_clock", "boost_clock") and db_boost is not None:
                # Only accept GPU Ark boost if it corroborates the stored boost
                ark_boosts = [a["boost_clock"] for a in candidates
                              if a["boost_clock"] is not None]
                corroborated = any(
                    abs(db_boost - b) <= BOOST_TOL_MHZ for b in ark_boosts
                ) if ark_boosts else True  # no ark boost → accept if name matches
                if not corroborated:
                    results_by_field[ark_col]["boost_conflict"] += 1
                    reason_counts[f"{ark_col}:boost_mismatch"] += 1
                    quarantined.append({
                        "hardware_id": hwid, "name": r["name"],
                        "mfr": r["manufacturer"], "field": spec_col,
                        "db_boost": db_boost, "ark_boosts": ark_boosts,
                        "reason": "boost_clock_mhz in DB does not match GPU Ark boost"
                    })
                    continue

            # Collect unique values from candidates
            vals = list(set(a[ark_col] for a in candidates if a[ark_col] is not None))
            if not vals:
                results_by_field[ark_col]["ark_null"] += 1
                reason_counts[f"{ark_col}:ark_value_null"] += 1
                continue

            if len(vals) > 1:
                results_by_field[ark_col]["ambiguous"] += 1
                reason_counts[f"{ark_col}:multiple_ark_values"] += 1
                quarantined.append({
                    "hardware_id": hwid, "name": r["name"],
                    "mfr": r["manufacturer"], "field": spec_col,
                    "ark_vals": vals, "ark_candidates": [a["name"] for a in candidates],
                    "reason": "multiple distinct GPU Ark values for same name"
                })
                continue

            val = vals[0]

            # Sanity ranges per field
            if ark_col == "boost_clock" and not (100 <= (val or 0) <= 4000):
                results_by_field[ark_col]["out_of_range"] += 1
                reason_counts[f"{ark_col}:out_of_range"] += 1
                continue

            if ark_col == "base_clock" and not (50 <= (val or 0) <= 4000):
                results_by_field[ark_col]["out_of_range"] += 1
                reason_counts[f"{ark_col}:out_of_range"] += 1
                continue

            if ark_col == "tdp" and not (5 <= (val or 0) <= 1000):
                results_by_field[ark_col]["out_of_range"] += 1
                reason_counts[f"{ark_col}:out_of_range"] += 1
                continue

            if ark_col == "length_mm" and not (30 <= (val or 0) <= 700):
                results_by_field[ark_col]["out_of_range"] += 1
                reason_counts[f"{ark_col}:out_of_range"] += 1
                continue

            if ark_col == "memory_gb" and not (0.25 <= (val or 0) <= 192):
                results_by_field[ark_col]["out_of_range"] += 1
                reason_counts[f"{ark_col}:out_of_range"] += 1
                continue

            # Safe update
            results_by_field[ark_col]["safe_update"] += 1
            a0 = next(a for a in candidates if a[ark_col] == val)
            records.append({
                "hardware_id": hwid,
                "name": r["name"],
                "mfr": r["manufacturer"],
                "field": spec_col,
                "source_value": val,
                "ark_id": a0["id"],
                "ark_name": a0["name"],
                "source_url": meta["url"],
            })

    con.close()

    # Report
    print()
    print("=== GPU Ark dry-run: per-field results ===")
    for ark_col, res in results_by_field.items():
        spec_col = FIELD_MAP[ark_col]["col"]
        print(f"  {ark_col} -> {spec_col}:")
        for k, v in sorted(res.items()):
            print(f"    {k:25} {v:5}")

    total_safe = sum(r["safe_update"] for r in results_by_field.values())
    print(f"\nTotal safe updates: {total_safe}")

    # Show coverage delta
    print()
    print("=== Coverage delta (after safe updates) ===")
    post_base = {f: dict(base[f]) for f in fields}
    for rec in records:
        col = rec["field"]
        if col in post_base:
            post_base[col]["filled"] += 1
            post_base[col]["missing"] -= 1
            post_base[col]["pct"] = round(100.0 * post_base[col]["filled"] / gpu_total, 1)
    for f in fields:
        delta = post_base[f]["filled"] - base[f]["filled"]
        print(f"  {f:25} {base[f]['filled']:5} -> {post_base[f]['filled']:5}  "
              f"({' +' if delta > 0 else ''}{delta:+d})  "
              f"{base[f]['pct']:.1f}% -> {post_base[f]['pct']:.1f}%")

    # Quarantine report
    print()
    print(f"=== Quarantined records: {len(quarantined)} ===")
    q_by_field = collections.Counter(q["field"] for q in quarantined)
    for f, n in q_by_field.most_common():
        print(f"  {f}: {n}")
    for q in quarantined[:10]:
        print(f"  quarantine: id={q['hardware_id']} name={q['name']} "
              f"field={q['field']} reason={q['reason']}")

    # Save results
    out = {
        "meta": meta,
        "baseline": base,
        "post_update": post_base,
        "total_safe_updates": total_safe,
        "records": records,
        "quarantined": quarantined,
        "per_field": {k: dict(v) for k, v in results_by_field.items()},
        "reason_counts": dict(reason_counts),
        "gpu_total": gpu_total,
        "ark_rows": len(ark_idx),
    }
    out_path = META_JSON.parent / "dry_run_results.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nDry-run results saved: {out_path}")
    return out


if __name__ == "__main__":
    import sys
    run_dryrun()
