"""Verify GPU Ark bus_interface richness + sample the 966 interface matches
to confirm they are real PCIe strings (not noise)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.app.importers.benchmark_normalizer import normalize_name

ARK_CSV = Path(__file__).resolve().parents[3] / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv"
DRYRUN = Path(__file__).resolve().parents[3] / "data" / "research" / "batch017" / "dry_run_results.json"

# 1. What distinct bus_interface values exist?
interfaces = {}
with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
    for row in csv.DictReader(f):
        bi = (row.get("bus_interface") or "").strip()
        if bi:
            interfaces[bi] = interfaces.get(bi, 0) + 1

print("=== distinct bus_interface values in GPU Ark ===")
for k, v in sorted(interfaces.items(), key=lambda x: -x[1]):
    print(f"  {k:30} {v:6}")

# 2. Sample the interface matches recorded in the dry-run
dry = json.loads(DRYRUN.read_text())
recs = [r for r in dry["records"] if r["field"] == "interface"]
print(f"\n=== sample interface updates ({len(recs)} total) ===")
for r in recs[:15]:
    print(f"  {r['name'][:50]:52} -> {r['source_value']}")
print("\n=== non-PCIe interface values (quarantine check) ===")
nonpcie = [r for r in recs if "PCIE" not in str(r["source_value"]).upper() and "PCI" not in str(r["source_value"]).upper()]
print(f"  non-PCIe count: {len(nonpcie)}")
for r in nonpcie[:15]:
    print(f"  {r['name'][:50]:52} -> {r['source_value']}")

# 3. Check that the updated interface set is consistent for same-name rows
import collections
by_name = collections.defaultdict(set)
for r in recs:
    by_name[r["name"]].add(str(r["source_value"]))
multi = {k: v for k, v in by_name.items() if len(v) > 1}
print(f"\n=== same DB name -> multiple distinct interfaces (should be few) ===")
print(f"  count: {len(multi)}")
for k, v in list(multi.items())[:10]:
    print(f"  {k}: {v}")
