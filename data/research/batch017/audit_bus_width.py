"""Check overlap between 28 empty-interface records and the 27
memory_bus_width_bits records; also inspect the 27 bus-width records."""
import json

dry = json.load(open(r"data\research\batch017\dry_run_results.json", encoding="utf-8"))
recs = dry["records"]

empty_iface = [r for r in recs if r["field"] == "interface" and
               (r["source_value"] in (None, "", "None", "nan") or str(r["source_value"]).strip() == "")]
bw = [r for r in recs if r["field"] == "memory_bus_width_bits"]

print(f"empty interface records: {len(empty_iface)}")
print(f"bus_width records: {len(bw)}")
empty_ids = {r["hardware_id"] for r in empty_iface}
bw_ids = {r["hardware_id"] for r in bw}
print(f"overlapping hardware_ids: {len(empty_ids & bw_ids)}")

print()
print("=== the 27 memory_bus_width_bits records ===")
for r in sorted(bw, key=lambda x: x["hardware_id"]):
    print(f"  id={r['hardware_id']:5} val={r['source_value']!r:6} ark={r['ark_id']!r:7} name={r['name']!r}")

# Confirm 966 + 27 = 993 and 966 unique interfaces
from collections import Counter
iface = [r for r in recs if r["field"] == "interface" and
         r["source_value"] not in (None, "", "None", "nan") and str(r["source_value"]).strip() != ""]
print()
print(f"non-empty interface records: {len(iface)}")
print(f"  966 + 27 = {966+27} = total {len(recs)} ?", len(iface) + len(bw) == len(recs))
ifaces = Counter(r["source_value"] for r in iface)
print(f"  distinct interface values: {len(ifaces)}")
print(f"  unique hardware_ids: {len(set(r['hardware_id'] for r in iface))}")
