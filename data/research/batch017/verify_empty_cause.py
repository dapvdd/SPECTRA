"""Verify the 28 empty-interface records directly against the GPU Ark CSV:
is bus_interface empty in the source (genuine missing value), or was it a
parsing bug (e.g. value got dropped)? Cross-check other columns for these rows."""
import csv
import json
from pathlib import Path

ARK_CSV = Path("data/research/batch017/gpuark-gpu-specs.csv")
dry = json.load(open("data/research/batch017/dry_run_results.json", encoding="utf-8"))

# Build ark_id -> row lookup
ark = {}
header = None
with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
    reader = csv.DictReader(f)
    header = reader.fieldnames
    for row in reader:
        ark[row.get("id", "").strip()] = row

print("Cols of interest present in CSV:", [c for c in
      ("id", "name", "bus_interface", "vendor", "manufacturer", "arch_name",
       "ram", "ram_type", "bus_width", "tdp", "base_clock", "boost_clock")
      if c in header] or "NONE FOUND")
print()

bad = []
for r in dry["records"]:
    sv = r.get("source_value")
    if sv is None or str(sv).strip() == "" or str(sv).lower() in ("none", "nan"):
        bad.append(r)

print(f"=== checking {len(bad)} empty-interface records against CSV ===")
missing_in_csv = 0
empty_in_csv = 0
for r in bad:
    aid = r["ark_id"]
    row = ark.get(aid)
    if row is None:
        missing_in_csv += 1
        print(f"  ark_id={aid} NOT FOUND in CSV (name={r['name']!r})")
        continue
    bi = (row.get("bus_interface") or "").strip()
    if bi == "":
        empty_in_csv += 1
    nm = repr(row.get("name", ""))
    print(f"  ark_id={aid:6} name={nm:45} "
          f"bus_interface={bi!r} vendor={row.get('vendor',''):4} "
          f"arch={(row.get('arch_name','') or ''):20} ram={(row.get('ram','') or ''):8} "
          f"bus_width={row.get('bus_width','')!r}")

print()
print(f"  of {len(bad)}: missing_in_csv={missing_in_csv} empty_in_csv={empty_in_csv}")

# Also: are these rows reachable by name matching only, or do they all have empty
# bus_interface in ark?
print()
print("=== sanity: count ark rows total vs ark rows with empty bus_interface ===")
empty_total = sum(1 for row in ark.values() if (row.get("bus_interface") or "").strip() == "")
print(f"  ark rows total: {len(ark)}")
print(f"  ark rows with empty bus_interface: {empty_total}")
pci = sum(1 for row in ark.values() if "PCIe" in (row.get("bus_interface") or ""))
print(f"  ark rows whose bus_interface contains PCIe: {pci}")
