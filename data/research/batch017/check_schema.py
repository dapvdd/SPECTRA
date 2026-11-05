"""Check field_provenance schema and existing provenance conventions."""
import sqlite3

c = sqlite3.connect("data/spectra_staging.db")
cols = [r[1] for r in c.execute("PRAGMA table_info(field_provenance)")]
print("field_provenance columns:", cols)

# Sample existing rows for interface and bus_width
print("\n--- sample provenance rows ---")
for r in c.execute("""
    SELECT hardware_id, field_name, evidenced_value, source_id, confidence,
           evidence_status, match_method, source_reference, license_name, access_date
    FROM field_provenance
    WHERE field_name IN ('interface','memory_bus_width_bits')
    LIMIT 5
"""):
    print(dict(zip(
        ["hardware_id","field_name","evidenced_value","source_id","confidence",
         "evidence_status","match_method","source_reference","license_name","access_date"], r)))

# Existing batch numbers used
print("\n--- distinct batch_no ---")
for r in c.execute("SELECT DISTINCT batch_no FROM field_provenance ORDER BY batch_no").fetchall():
    print(" ", r[0])

# sources table
print("\n--- source #4 reference ---")
print(c.execute("SELECT id, name, url FROM sources WHERE id=4").fetchone())

c.close()
