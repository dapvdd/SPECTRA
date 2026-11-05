# -*- coding: utf-8 -*-
"""Embed the 965 batch018 records into migrate_batch018.py as RECORDS payload.

Produces migrate_batch018_selfcontained.py — a single file carrying the
deterministic migration payload, ready to be piped into the container for
rehearsal (and later, only after approval, for production application).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "migrate_batch018.py"
RECORDS_JSON = HERE.parent / "batch017" / "batch018_valid_records.json"
OUT = HERE / "migrate_batch018_selfcontained.py"

records = json.load(open(RECORDS_JSON, encoding="utf-8"))
# Re-validate the payload shape deterministically
assert len(records) == 965, "expected 965 records, got %d" % len(records)
from collections import Counter
fields = Counter(r["field"] for r in records)
assert fields["interface"] == 938, fields
assert fields["memory_bus_width_bits"] == 27, fields
# every entry must have the required keys
required = {"hardware_id", "field", "source_value", "name"} - set()
for r in records:
    assert {"hardware_id", "field", "source_value"} <= set(r), r
# no duplicate (hardware_id, field) pairs
pairs = [(r["hardware_id"], r["field"]) for r in records]
assert len(set(pairs)) == 965, "duplicate (hardware_id, field) pairs"

body = SRC.read_text(encoding="utf-8")
payload_line = "RECORDS = []  # populated by generate step"
payload = "RECORDS = " + json.dumps(records, ensure_ascii=False)
assert body.count(payload_line) == 1, "unexpected template layout"
body = body.replace(payload_line, payload)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(body)

print("wrote:", OUT.name)
print("embedded:", len(records), "records",
      "(interface=%d, memory_bus_width_bits=%d)" % (fields["interface"],
                                                     fields["memory_bus_width_bits"]))
