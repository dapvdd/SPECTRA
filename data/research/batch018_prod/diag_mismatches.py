# -*- coding: utf-8 -*-
"""Diagnose the 27 'mismatches' reported — verify they are float-coercion
artifacts (value 5120.0 in DB vs '5120' in provenance) and not real overwrites.
"""
import sqlite3
import sys

db_path = sys.argv[1]
con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
con.row_factory = sqlite3.Row

rows = con.execute(
    "SELECT p.hardware_id hwid, p.field_name field, p.evidenced_value ev, "
    "       g.interface iface, g.memory_bus_width_bits bw "
    "FROM field_provenance p JOIN gpu_specifications g ON g.hardware_id=p.hardware_id "
    "WHERE p.batch_no=18"
).fetchall()

def num_eq(a, b):
    """Compare a DB value with an evidenced string, numerically tolerant."""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)

true_bad = []
coerce_ok = 0
for r in rows:
    if r["field"] == "interface":
        ok = str(r["iface"]) == r["ev"]
    else:
        ok = num_eq(r["bw"], r["ev"])
    if not ok:
        true_bad.append((r["hwid"], r["field"], r["iface"], r["bw"], r["ev"]))
    else:
        # only count float-coercion cases for bus_width as the artifact type
        if r["field"] == "memory_bus_width_bits" and str(r["bw"]) != r["ev"]:
            coerce_ok += 1

print("total batch18 provenance rows:", len(rows))
print("true value/provenance mismatches (real problems):", len(true_bad))
for bad in true_bad[:30]:
    print("  BAD:", bad)
print("float-coercion artifacts (numerically equal, string-different) among bus_width:", coerce_ok)

# Show a few bus_width numeric-equality confirmations
print("\n=== sample numeric-equality confirmations (bus_width) ===")
shown = 0
for r in rows:
    if r["field"] == "memory_bus_width_bits" and shown < 8:
        n_ok = num_eq(r["bw"], r["ev"])
        print(f"  hwid={r['hwid']} db={r['bw']!r} ev='{r['ev']}' numeric_equal={n_ok}")
        shown += 1
con.close()
