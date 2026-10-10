import sqlite3, json
c = sqlite3.connect(r"C:\SPECTRA\data\spectra.db")
print("leftover field_provenance_new:", c.execute("SELECT name FROM sqlite_master WHERE name='field_provenance_new'").fetchall())
print("field_provenance total:", c.execute("SELECT COUNT(*) FROM field_provenance").fetchone()[0])
print("benchmark provenance:", c.execute("SELECT COUNT(*) FROM field_provenance WHERE table_name='benchmark_results'").fetchone()[0])
print("spec provenance:", c.execute("SELECT COUNT(*) FROM field_provenance WHERE table_name!='benchmark_results'").fetchone()[0])
print("external_identifiers by source:", c.execute("SELECT source_id, COUNT(*) FROM external_identifiers GROUP BY source_id").fetchall())
print("sources:", c.execute("SELECT id, name FROM sources ORDER BY id").fetchall())
print("benchmark_results by name:", c.execute("SELECT benchmark_name, test_type, COUNT(*) FROM benchmark_results GROUP BY 1,2").fetchall())
print("quick_check:", c.execute("PRAGMA quick_check").fetchone())
print("fk_check:", c.execute("PRAGMA foreign_key_check").fetchall())
print("\nSample benchmark provenance:")
for r in c.execute("SELECT p.id, p.hardware_id, p.benchmark_result_id, p.field_name, p.source_id, p.evidence_status, p.confidence, p.source_reference, p.match_method, p.batch_no FROM field_provenance p WHERE p.table_name='benchmark_results' LIMIT 5"):
    print("  ", tuple(r))