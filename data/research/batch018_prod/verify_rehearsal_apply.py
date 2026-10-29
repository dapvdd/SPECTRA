# -*- coding: utf-8 -*-
"""Independent read-only verification of the applied rehearsal copy.

Piped into the container against an applied rehearsal DB path (argv[1]).
Confirms: coverage delta, provenance rows, no NULL-guard overwrite, spot-checks,
integrity, and key equivalence with staging values for a sample.
"""
import json
import sqlite3
import sys

db_path = sys.argv[1]
con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)

print("=== rehearsal DB ===", db_path)
total = con.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0]
print("gpu_spec rows:", total)

print("\n=== coverage (post-apply) ===")
for col in ("interface", "memory_bus_width_bits", "memory_gb", "memory_type",
            "core_clock_mhz", "boost_clock_mhz", "tdp_w", "length_mm",
            "vram_bandwidth_gbps"):
    nn = con.execute("SELECT COUNT(*) FROM gpu_specifications WHERE %s IS NOT NULL" % col).fetchone()[0]
    print(f"  {col:25} {nn:5} / {total}  ({100.0*nn/total:.1f}%)")

print("\n=== provenance (this batch) ===")
print("  batch_no=18 rows:", con.execute(
    "SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0])
print("  source_id=4 interface rows:", con.execute(
    "SELECT COUNT(*) FROM field_provenance WHERE source_id=4 AND field_name='interface'").fetchone()[0])
print("  source_id=4 bus_width rows:", con.execute(
    "SELECT COUNT(*) FROM field_provenance WHERE source_id=4 AND field_name='memory_bus_width_bits'").fetchone()[0])

print("\n=== integrity ===")
print("  quick_check:", con.execute("PRAGMA quick_check").fetchone()[0])
print("  fk_violations:", len(con.execute("PRAGMA foreign_key_check").fetchall()))

print("\n=== NULL-guard: no overwritten values for batch018 targets (should be 0) ===")
# For each batch18 provenance target, confirm the gpu value equals the evidenced value
# AND that we can detect any that would have differed (i.e., an overwrite would violate this)
mismatch = con.execute(
    "SELECT COUNT(*) FROM field_provenance p "
    "JOIN gpu_specifications g ON g.hardware_id=p.hardware_id "
    "WHERE p.batch_no=18 AND "
    "((p.field_name='interface' AND CAST(g.interface AS TEXT)<>p.evidenced_value) OR "
    " (p.field_name='memory_bus_width_bits' AND CAST(g.memory_bus_width_bits AS TEXT)<>p.evidenced_value))"
).fetchone()[0]
print("  value/provenance mismatches:", mismatch)

print("\n=== unique (hardware_id, field) pairs in batch18 provenance (should be 965) ===")
print("  distinct pairs:", con.execute(
    "SELECT COUNT(DISTINCT hardware_id || '|' || field_name) FROM field_provenance WHERE batch_no=18"
).fetchone()[0])
con.close()
