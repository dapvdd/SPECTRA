"""Read-only inspection of the live SPECTRA production DB (DavidLab).

Safely inspect whether batch 017/018 changes are present, WITHOUT writing.
This script is meant to be piped into `docker exec -i spectra-backend python -`.
"""
import sqlite3

DB = "/app/data/spectra.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def q(sql, *args):
    return con.execute(sql, args).fetchall()

print("=== hardware table ===")
cols = [r[1] for r in con.execute("PRAGMA table_info(hardware)")]
print("hardware columns:", cols)
print("has segment column:", "segment" in cols)
print("total hardware:", con.execute("SELECT COUNT(*) FROM hardware").fetchone()[0])

if "segment" in cols:
    print("\n=== segment distribution ===")
    for r in q("SELECT COALESCE(segment,'NULL') seg, COUNT(*) n FROM hardware GROUP BY segment ORDER BY n DESC"):
        print(f"  {r['seg'] if r['seg'] else 'NULL'}: {r['n']}")

print("\n=== provenance: batch 17/18 and source 10 ===")
print(" batch17 rows:", con.execute("SELECT COUNT(*) FROM field_provenance WHERE batch_no=17").fetchone()[0])
print(" batch18 rows:", con.execute("SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0])
print(" source10 exists:", con.execute("SELECT COUNT(*) FROM sources WHERE id=10").fetchone()[0])
print("\n=== sources table ===")
for r in q("SELECT id, name, license_status FROM sources ORDER BY id"):
    print(f"  {r['id']}: {r['name']} [{r['license_status']}]")

print("\n=== GPU coverage ===")
gt = con.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0]
print(" gpu_spec rows:", gt)
for col in ("interface", "memory_bus_width_bits", "memory_gb", "memory_type",
            "core_clock_mhz", "boost_clock_mhz", "tdp_w", "length_mm",
            "vram_bandwidth_gbps"):
    nn = con.execute(f"SELECT COUNT(*) FROM gpu_specifications WHERE {col} IS NOT NULL").fetchone()[0]
    print(f"  {col:25} {nn:5} / {gt}  ({100.0*nn/gt:.1f}%)")

print("\n=== quick_check ===")
print(con.execute("PRAGMA quick_check").fetchone()[0])

con.close()
