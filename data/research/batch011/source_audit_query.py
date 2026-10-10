import sqlite3
c = sqlite3.connect(r"C:\SPECTRA\data\spectra.db")
c.row_factory = sqlite3.Row

print("=== sources ===")
for r in c.execute("SELECT id, name, url FROM sources ORDER BY id"):
    print(dict(r))

print("\n=== references to each source ===")
for r in c.execute("""
    SELECT s.id, s.name,
      (SELECT COUNT(*) FROM external_identifiers e WHERE e.source_id=s.id) AS ext_ids,
      (SELECT COUNT(*) FROM field_provenance p WHERE p.source_id=s.id) AS provenance,
      (SELECT COUNT(*) FROM benchmark_results b WHERE b.source_id=s.id) AS benchmarks
    FROM sources s ORDER BY s.id"""):
    print(tuple(r))

print("\n=== source 1 field_provenance detail ===")
for r in c.execute("SELECT table_name, field_name, COUNT(*) c FROM field_provenance WHERE source_id=1 GROUP BY table_name, field_name ORDER BY table_name, field_name"):
    print("  ", tuple(r))

print("\n=== source 1 provenance: distinct tables ===")
for r in c.execute("SELECT DISTINCT table_name FROM field_provenance WHERE source_id=1"):
    print("  ", r[0])

print("\n=== tables that have a source_id column ===")
cols = {}
for t in ["external_identifiers", "benchmark_results", "field_provenance", "sources"]:
    present = [row[1] for row in c.execute(f"PRAGMA table_info({t})")]
    cols[t] = "source_id" if "source_id" in present else "-"
print(cols)

print("\n=== orphan checks ===")
print("ext_ids orphan source:", c.execute("SELECT COUNT(*) FROM external_identifiers e LEFT JOIN sources s ON s.id=e.source_id WHERE s.id IS NULL").fetchone()[0])
print("bench orphan source:", c.execute("SELECT COUNT(*) FROM benchmark_results b LEFT JOIN sources s ON s.id=b.source_id WHERE b.source_id IS NOT NULL AND s.id IS NULL").fetchone()[0])
print("prov orphan source:", c.execute("SELECT COUNT(*) FROM field_provenance p LEFT JOIN sources s ON s.id=p.source_id WHERE s.id IS NULL").fetchone()[0])