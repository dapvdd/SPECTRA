"""Validate dry-run JSON: no empty/NaN source values before build apply."""
import json
from pathlib import Path

p = Path("data/research/batch017/dry_run_results.json")
dry = json.loads(p.read_text())

recs = dry["records"]
print(f"total records: {len(recs)}")
fields = {}
for r in recs:
    fields[r["field"]] = fields.get(r["field"], 0) + 1
print("by field:", fields)

# Check for empty/None/NaN source_value
bad = [r for r in recs
       if r["source_value"] in (None, "", "None", "nan", "NaN") or str(r["source_value"]).strip() == ""]
print(f"\nrecords with empty/None source_value: {len(bad)}")
for r in bad[:10]:
    print("  ", r["name"], "->", repr(r["source_value"]), r["field"])

# Check values exceed column length (interface is VARCHAR(50))
long_iface = [r for r in recs if r["field"] == "interface" and len(str(r["source_value"])) > 50]
print(f"\ninterface values >50 chars: {len(long_iface)}")

# Unique hardware_id per field (no dup plans)
import collections
for f, n in fields.items():
    ids = [r["hardware_id"] for r in recs if r["field"] == f]
    print(f"  {f}: {len(ids)} records, {len(set(ids))} unique hardware_ids")

# source values as a sample
print("\nsample interface values:")
for r in [x for x in recs if x["field"] == "interface"][:8]:
    print("  ", repr(r["source_value"]))
