"""Classify all records in dry-run with empty/None source_value."""
import json
from collections import Counter

dry = json.load(open(r"data\research\batch017\dry_run_results.json", encoding="utf-8"))
recs = dry["records"]
total = len(recs)
print("total records:", total)

bad = []
for r in recs:
    sv = r.get("source_value")
    if sv is None or str(sv).strip() == "" or str(sv).lower() in ("none", "nan"):
        bad.append(r)

print("empty/None source_value:", len(bad))
print()
cnt = Counter((r["field"], str(r.get("source_value"))[:25]) for r in bad)
for (f, sv), n in cnt.most_common():
    print(f"  field={f!r:35} value={sv!r:25} count={n}")
print()
print("=== individual invalid records ===")
for r in bad:
    print(f"  hardware_id={r['hardware_id']}  field={r['field']!r}  "
          f"value={r.get('source_value')!r}  ark_id={r.get('ark_id')!r}")
    print(f"     name={r['name']!r}")
