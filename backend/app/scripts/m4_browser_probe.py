"""Browser-acceptance probe: verify the snapshot DB is usable read-only."""
import sqlite3

c = sqlite3.connect("data/dev/m4_snapshot.db")
print("hw:", c.execute("SELECT COUNT(*) FROM hardware").fetchone()[0])
print("bench:", c.execute("SELECT COUNT(*) FROM benchmark_results").fetchone()[0])
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("has schema_migrations:", "schema_migrations" in tables)
if "schema_migrations" in tables:
    print("mig count:", c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0])
row = c.execute(
    "SELECT id, name FROM hardware WHERE type='CPU' ORDER BY id LIMIT 3"
).fetchall()
print("sample CPUs:", row)
