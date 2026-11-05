"""Read-only: confirm production gpu_specifications + field_provenance schema
and check NULL guards for the 965 batch018 records (read only)."""
import sqlite3

con = sqlite3.connect("/app/data/spectra.db")
con.row_factory = sqlite3.Row

print("=== gpu_specifications columns ===")
for r in con.execute("PRAGMA table_info(gpu_specifications)"):
    print(f"  {r['name']} {r['type']} notnull={r['notnull']}")

print("\n=== field_provenance columns ===")
for r in con.execute("PRAGMA table_info(field_provenance)"):
    print(f"  {r['name']} {r['type']} notnull={r['notnull']}")

# Does the DB have any rows at all for bus_width (recent addition)?
print("\n=== memory_bus_width_bits present? ===")
gt = con.execute("SELECT COUNT(*) FROM gpu_specifications WHERE memory_bus_width_bits IS NOT NULL").fetchone()[0]
print(" non-null:", gt)

con.close()
