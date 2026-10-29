"""Batch 017 idempotency + coverage verification."""
import json
import sqlite3
from collections import Counter

STAGING = "data/spectra_staging.db"
DRYRUN = "data/research/batch017/dry_run_results.json"
META = "data/research/batch017/source_metadata.json"

# --- 1. Idempotency: re-running the matcher on the STAGED DB
#     should produce 0 new non-empty records (all classifiable ones already filled)
print("=== IDEMPOTENCY CHECK ===")
dry = json.load(open(DRYRUN))
original_valid = [r for r in dry["records"]
                  if r.get("source_value") not in (None, "", "None", "nan", "NaN")
                  and str(r.get("source_value", "")).strip() != ""]
original_hwid_field = {(r["hardware_id"], r["field"]) for r in original_valid}

con = sqlite3.connect(f"file:{STAGING}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

# After apply, interface and memory_bus_width_bits should be non-NULL for these records
still_null = []
for hwid, field in original_hwid_field:
    cur = con.execute(f"SELECT {field} FROM gpu_specifications WHERE hardware_id=?", (hwid,)).fetchone()
    if cur is None or cur[0] is None:
        still_null.append((hwid, field))

print(f"original valid records: {len(original_valid)}")
print(f"records still NULL after apply: {len(still_null)}")
if still_null:
    print("  STILL NULL:")
    for hwid, field in still_null[:10]:
        print(f"    hardware_id={hwid} field={field}")
print("idempotent:", len(still_null) == 0)

# --- 2. Re-run matcher on post-apply DB: should produce 0 new non-empty records
import sys
sys.path.insert(0, ".")
from backend.app.importers.benchmark_normalizer import normalize_name
import csv
from pathlib import Path

ARK_CSV = Path("data/research/batch017/gpuark-gpu-specs.csv")
records_new = []
with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
    ark_all = {row["id"].strip(): row for row in csv.DictReader(f)}

from collections import defaultdict
ark_idx = defaultdict(list)
for row in ark_all.values():
    from backend.app.importers.benchmark_normalizer import normalize_name as nn
    CHIP_PREFIXES = ("nvidia ", "amd ", "ati ", "intel ")
    def strip_chip_prefix(name):
        low = (name or "").lower()
        for p in CHIP_PREFIXES:
            if low.startswith(p):
                return name[len(p):].strip()
        return name
    nname = strip_chip_prefix(nn(row.get("name") or "") or "").strip()
    if nname:
        ark_idx[nname].append(row)

def _float(s):
    if not s:
        return None
    try:
        v = float(s.strip())
        return None if v == 0 else v
    except:
        return None

reclassified = 0
for r in con.execute(
    "SELECT id, name, manufacturer FROM hardware WHERE type='GPU'"
).fetchall():
    norm = normalize_name(r["name"]) or ""
    for ark_row in ark_idx.get(norm, []):
        # vendor match
        ark_vendor = (ark_row.get("vendor") or "").strip()
        VENDOR_MAP = {"nvd": "NVIDIA", "amd": "AMD", "int": "Intel"}
        av = VENDOR_MAP.get(ark_vendor, ark_vendor)
        if not (av == r["manufacturer"] or {av, r["manufacturer"]} <= {"AMD", "ATI"}):
            continue
        bi = (ark_row.get("bus_interface") or "").strip()
        bw = _float(ark_row.get("bus_width"))
        # Check if there is an unfilled record in post-apply DB
        if bi:
            cur = con.execute(
                "SELECT interface FROM gpu_specifications WHERE hardware_id=?", (r["id"],)
            ).fetchone()
            if cur and cur[0] is None:
                reclassified += 1
        if bw:
            cur = con.execute(
                "SELECT memory_bus_width_bits FROM gpu_specifications WHERE hardware_id=?", (r["id"],)
            ).fetchone()
            if cur and cur[0] is None:
                reclassified += 1

print()
print(f"additional classifiable-but-NULL records in post-apply DB: {reclassified}")
print("fully idempotent:", reclassified == 0)
con.close()

# --- 3. Coverage delta
print()
print("=== COVERAGE DELTA ===")
con = sqlite3.connect(STAGING)
con.row_factory = sqlite3.Row
gpu_total = con.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0]
fields = ["interface", "memory_bus_width_bits", "boost_clock_mhz",
          "tdp_w", "length_mm", "memory_gb", "memory_type",
          "vram_bandwidth_gbps", "core_clock_mhz"]
print(f"GPU total: {gpu_total}")
print()
print(f"{'Field':30} {'Before':>8} {'After':>8} {'Delta':>7} {'Before%':>9} {'After%':>8}")
print("-" * 75)
# Baseline from dry-run
baseline = dry["baseline"]
for f in fields:
    bef_filled = baseline.get(f, {}).get("filled", "?")
    bef_pct = baseline.get(f, {}).get("pct", "?")
    aft = con.execute(
        f"SELECT COUNT(*) FROM gpu_specifications WHERE {f} IS NOT NULL"
    ).fetchone()[0]
    aft_pct = round(100.0 * aft / gpu_total, 1)
    delta = aft - (bef_filled if bef_filled != "?" else 0)
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"{f:30} {bef_filled:>8} {aft:>8} {delta_str:>7} {bef_pct:>8.1f}% {aft_pct:>7.1f}%")
con.close()

# --- 4. Provenance count
print()
print("=== PROVENANCE ===")
con = sqlite3.connect(STAGING)
src4 = con.execute("SELECT COUNT(*) FROM field_provenance WHERE source_id=4").fetchone()[0]
total = con.execute("SELECT COUNT(*) FROM field_provenance").fetchone()[0]
batch18 = con.execute("SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0]
print(f"Provenance rows from source_id=4 (GPU Ark): {src4}")
print(f"Provenance rows from batch_no=18: {batch18}")
print(f"Total provenance rows: {total}")
con.close()

# --- 5. Integrity check
print()
print("=== INTEGRITY ===")
con = sqlite3.connect(STAGING)
qc = con.execute("PRAGMA quick_check").fetchone()[0]
fk = con.execute("PRAGMA foreign_key_check").fetchall()
print(f"integrity_check: {qc}")
print(f"foreign_key_violations: {len(fk)}")
# Sample spot-checks
spot = [
    (3370, "interface", "PCIe 3.0 x16"),
    (3524, "interface", None),  # excluded - should be NULL
    (4990, "memory_bus_width_bits", 5120.0),
]
print("spot-checks:")
for hwid, field, expected in spot:
    cur = con.execute(f"SELECT {field} FROM gpu_specifications WHERE hardware_id=?", (hwid,)).fetchone()
    val = cur[0] if cur else None
    ok = "PASS" if val == expected else "WARN"
    print(f"  [{ok}] id={hwid} {field} expected={expected!r} actual={val!r}")
con.close()
