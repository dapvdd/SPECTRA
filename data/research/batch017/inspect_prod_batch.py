# -*- coding: utf-8 -*-
"""Read-only: check production batch_no usage + source #4 metadata readiness."""
import sqlite3

con = sqlite3.connect("/app/data/spectra.db")
con.row_factory = sqlite3.Row

print("=== batch_no values already used in production provenance ===")
for r in con.execute("SELECT DISTINCT batch_no FROM field_provenance ORDER BY batch_no"):
    print("  batch_no =", r["batch_no"])

print("\n=== source #4 (GPU Ark) record ===")
s = con.execute("SELECT id, name, license_name, license_status, retrieved_on FROM sources WHERE id=4").fetchone()
print(" ", dict(s) if s else "NOT FOUND")

print("\n=== does source #4 have retrieved_on set? ===")
print("  retrieved_on:", s["retrieved_on"] if s else None)

print("\n=== existing provenance for interface (source_id=4) count ===")
print("  interface provenance rows:", con.execute(
    "SELECT COUNT(*) FROM field_provenance WHERE field_name='interface' AND source_id=4"
).fetchone()[0])
print("  bus_width provenance rows:", con.execute(
    "SELECT COUNT(*) FROM field_provenance WHERE field_name='memory_bus_width_bits' AND source_id=4"
).fetchone()[0])

print("\n=== exact counts of records lacking provenance for the 938+27 targets ===")
print("  interface values w/o provenance:", con.execute(
    "SELECT COUNT(*) FROM gpu_specifications g LEFT JOIN field_provenance p "
    "ON p.hardware_id=g.hardware_id AND p.field_name='interface' AND p.source_id=4 "
    "WHERE p.id IS NULL AND g.interface IS NULL"
).fetchone()[0])
con.close()
