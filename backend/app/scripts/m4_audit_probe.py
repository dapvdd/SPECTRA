"""M4 Task 0/1 audit probe: catalog + benchmark coverage of the isolated dev DB."""
import sqlite3

conn = sqlite3.connect("data/dev/spectra_dev.db")
c = conn.cursor()

print("hardware by type:", c.execute("SELECT type, COUNT(*) FROM hardware GROUP BY type").fetchall())
print("benchmark test_types:", c.execute("SELECT test_type, unit, COUNT(*) FROM benchmark_results GROUP BY test_type, unit").fetchall())
print("CPUs with benchmarks:", c.execute("SELECT COUNT(DISTINCT hardware_id) FROM benchmark_results").fetchone())
for f in ["cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w", "socket", "process_node_nm"]:
    print("  cpu", f, c.execute(f"SELECT COUNT(*) FROM cpu_specifications WHERE {f} IS NOT NULL").fetchone()[0])
print("GPU spec rows:", c.execute("SELECT COUNT(*) FROM gpu_specifications").fetchone()[0])
print("field_provenance:", c.execute("SELECT evidence_status, COUNT(*) FROM field_provenance GROUP BY evidence_status").fetchall())
print("record_status:", c.execute("SELECT record_status, COUNT(*) FROM hardware GROUP BY record_status").fetchall())
print("segment:", c.execute("SELECT segment, COUNT(*) FROM hardware GROUP BY segment").fetchall())
print("release_date:", c.execute("SELECT COUNT(*) FROM hardware WHERE release_date IS NOT NULL").fetchone()[0])
print("architecture:", c.execute("SELECT COUNT(*) FROM hardware WHERE architecture IS NOT NULL").fetchone()[0])
print("benchmark names:", c.execute("SELECT benchmark_name, COUNT(*) FROM benchmark_results GROUP BY benchmark_name").fetchall())
print("benchmark recorded_at:", c.execute("SELECT COUNT(*), MIN(recorded_at), MAX(recorded_at) FROM benchmark_results").fetchall())
print("source:", c.execute("SELECT id, name, url FROM sources").fetchall())
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("tables:", tables)
# price-like columns anywhere
for t in tables:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
    hits = [col for col in cols if "price" in col.lower() or "cost" in col.lower() or "msrp" in col.lower()]
    if hits:
        print("PRICE-LIKE:", t, hits)
# sample multi-core scores distribution
rows = c.execute("SELECT score FROM benchmark_results WHERE test_type='multi-core' ORDER BY score").fetchall()
print("multi-core scores:", [r[0] for r in rows])
rows = c.execute("SELECT score FROM benchmark_results WHERE test_type='single-core' ORDER BY score").fetchall()
print("single-core scores:", [r[0] for r in rows])
# do the 12 benchmarks belong to verified CPUs?
print("benchmark sample:", c.execute("SELECT b.hardware_id, h.name, b.benchmark_name, b.score, b.test_type FROM benchmark_results b JOIN hardware h ON h.id=b.hardware_id LIMIT 14").fetchall())
