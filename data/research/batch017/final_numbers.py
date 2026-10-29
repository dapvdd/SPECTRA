"""Final verified batch018 numbers for reporting (read-only)."""
import sqlite3

c = sqlite3.connect("data/spectra_staging.db")
c.row_factory = sqlite3.Row

print("=== batch018 provenance (source_id=4, batch_no=18) ===")
rows = c.execute(
    "SELECT field_name, COUNT(*) n FROM field_provenance "
    "WHERE source_id=4 AND batch_no=18 GROUP BY field_name ORDER BY n DESC"
).fetchall()
for r in rows:
    print(f"  {r['field_name']:25} {r['n']}")

print()
print("=== final GPU coverage (post-batch018 staging) ===")
total = c.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0]
for col in ["interface", "memory_bus_width_bits", "memory_gb", "memory_type",
            "core_clock_mhz", "boost_clock_mhz", "tdp_w", "length_mm",
            "vram_bandwidth_gbps"]:
    nonnull = c.execute(f"SELECT COUNT(*) FROM gpu_specifications WHERE {col} IS NOT NULL").fetchone()[0]
    print(f"  {col:25} {nonnull} / {total}  ({100.0*nonnull/total:.1f}%)")

print()
print("=== source #4 row ===")
s = c.execute("SELECT id, name, license_status, retrieved_on FROM sources WHERE id=4").fetchone()
print(" ", dict(s) if s else None)

print()
print("=== provenance totals ===")
print("  total provenance:", c.execute("SELECT COUNT(*) FROM field_provenance").fetchone()[0])
print("  source_id=4 rows:", c.execute("SELECT COUNT(*) FROM field_provenance WHERE source_id=4").fetchone()[0])

print()
print("=== integrity ===")
print("  quick_check:", c.execute("PRAGMA quick_check").fetchone()[0])
print("  FK violations:", len(c.execute("PRAGMA foreign_key_check").fetchall()))

c.close()
