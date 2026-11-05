"""Clean authoritative count of the batch017 dry-run records."""
import json
from collections import Counter

dry = json.load(open(r"data\research\batch017\dry_run_results.json", encoding="utf-8"))
recs = dry["records"]

def is_empty(v):
    return v is None or str(v).strip() == "" or str(v).lower() in ("none", "nan")

print("TOTAL records:", len(recs))
cnt_field = Counter(r["field"] for r in recs)
print("by field:", dict(cnt_field))

iface = [r for r in recs if r["field"] == "interface"]
bw = [r for r in recs if r["field"] == "memory_bus_width_bits"]

iface_valid = [r for r in iface if not is_empty(r["source_value"])]
iface_empty = [r for r in iface if is_empty(r["source_value"])]
bw_valid = [r for r in bw if not is_empty(r["source_value"])]
bw_empty = [r for r in bw if is_empty(r["source_value"])]

print()
print("interface total:", len(iface), "| valid:", len(iface_valid), "| empty:", len(iface_empty))
print("bus_width total:", len(bw), "| valid:", len(bw_valid), "| empty:", len(bw_empty))
print()
print("CHECK: ", len(iface), "+", len(bw), "=", len(iface)+len(bw), "== total", len(recs),
      "->", len(iface)+len(bw) == len(recs))
print("CHECK valid:", len(iface_valid), "+", len(bw_valid), "=", len(iface_valid)+len(bw_valid))

print()
print("=== distinct non-empty interface values (value -> count) ===")
icount = Counter(r["source_value"] for r in iface_valid)
for v, n in sorted(icount.items()):
    print(f"  {v!r:28} {n:5}")
print("distinct non-empty interface values:", len(icount))

print()
print("=== bus width value distribution ===")
bcount = Counter(r["source_value"] for r in bw_valid)
for v, n in sorted(bcount.items()):
    print(f"  {v:10} {n:5}")
print("distinct bus width values:", len(bcount))

# unique hardware ids
all_ids = [r["hardware_id"] for r in recs]
print()
print("non-empty valid records unique hardware_ids:", len(set(r['hardware_id'] for r in iface_valid+bw_valid)))
print("total records unique hardware_ids:", len(set(all_ids)))
