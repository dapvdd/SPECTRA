"""Diagnose the two spot-check warnings: id=3370 interface mismatch,
and id=4990 memory_bus_width_bits conflict."""
import csv
import json
import sqlite3
from pathlib import Path

STAGING = "data/spectra_staging.db"
DRYRUN = "data/research/batch017/dry_run_results.json"
ARK_CSV = Path("data/research/batch017/gpuark-gpu-specs.csv")

dry = json.load(open(DRYRUN, encoding="utf-8"))

# Build ark id -> row lookup
ark_by_id = {}
with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
    for row in csv.DictReader(f):
        ark_by_id[row.get("id", "").strip()] = row

con = sqlite3.connect(STAGING)
con.row_factory = sqlite3.Row

for hwid, field, expected_ark_val in [
    (3370, "interface", "PCIe 3.0 x16"),
    (4990, "memory_bus_width_bits", 5120.0),
]:
    print(f"=== hardware_id={hwid}, field={field} ===")

    # Current DB value
    db_val = con.execute(
        f"SELECT {field} FROM gpu_specifications WHERE hardware_id=?", (hwid,)
    ).fetchone()
    hw = con.execute(
        "SELECT name, manufacturer FROM hardware WHERE id=?", (hwid,)
    ).fetchone()
    print(f"  DB: name={hw['name']!r} mfr={hw['manufacturer']!r}")
    print(f"  DB {field} = {db_val[0]!r}")

    # Find the dry-run record
    dr = next((r for r in dry["records"]
               if r["hardware_id"] == hwid and r["field"] == field), None)
    if dr:
        print(f"  Dry-run: source_value={dr['source_value']!r} ark_id={dr['ark_id']!r}")
        ark_row = ark_by_id.get(dr.get("ark_id", ""))
        if ark_row:
            print(f"  GPU Ark row: name={ark_row.get('name')!r} "
                  f"bus_interface={ark_row.get('bus_interface')!r} "
                  f"bus_width={ark_row.get('bus_width')!r}")
    else:
        print(f"  Dry-run: NOT FOUND (no record for this hwid/field)")
        # Search by name
        hw_name = hw["name"]
        hw_mfr = hw["manufacturer"]
        matches = [ark_by_id[k] for k, v in ark_by_id.items()
                   if (v.get("name") or "").lower() in hw_name.lower()
                   or hw_name.lower() in (v.get("name") or "").lower()]
        print(f"  GPU Ark partial name matches: {len(matches)}")
        for m in matches[:5]:
            print(f"    id={m.get('id')} name={m.get('name')!r} "
                  f"bus_interface={m.get('bus_interface')!r} "
                  f"bus_width={m.get('bus_width')!r}")

    print()

con.close()

# Also: find all records where the staging DB has a non-NULL interface that
# differs from GPU Ark's bus_interface. These are conflicts RESOLVED by
# keeping the existing value (NULL guard). Count and list a few.
print("=== ALL interface conflicts resolved by NULL guard ===")
dry_iface = [r for r in dry["records"] if r["field"] == "interface"
             and r["source_value"] not in (None, "", "None", "nan")]
con = sqlite3.connect(STAGING)
con.row_factory = sqlite3.Row
conflicts = []
for r in dry_iface:
    cur = con.execute(
        "SELECT interface FROM gpu_specifications WHERE hardware_id=?", (r["hardware_id"],)
    ).fetchone()
    existing = cur[0] if cur else None
    if existing is not None and existing != r["source_value"]:
        conflicts.append({
            "hwid": r["hardware_id"],
            "db_val": existing,
            "ark_val": r["source_value"],
            "ark_id": r.get("ark_id"),
            "name": r["name"],
        })
con.close()
print(f"Total interface conflicts: {len(conflicts)}")
for c in conflicts[:10]:
    print(f"  id={c['hwid']} DB={c['db_val']!r} Ark={c['ark_val']!r} name={c['name']!r}")
