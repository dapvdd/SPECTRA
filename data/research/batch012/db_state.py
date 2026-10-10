import sqlite3
import hashlib
import json

DB = r"C:\SPECTRA\data\spectra.db"

with open(DB, "rb") as f:
    data = f.read()
sha = hashlib.sha256(data).hexdigest()

con = sqlite3.connect(DB)
quick = con.execute("PRAGMA quick_check").fetchone()[0]
fk = con.execute("PRAGMA foreign_key_check").fetchall()
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

# Benchmark coverage per hardware type
bench_coverage = con.execute("""
    SELECT h.type,
           COUNT(DISTINCT h.id) AS total,
           COUNT(DISTINCT b.hardware_id) AS with_benchmarks
    FROM hardware h
    LEFT JOIN benchmark_results b ON b.hardware_id = h.id
    GROUP BY h.type
""").fetchall()

# Spec completeness per CPU
cpu_nulls = con.execute("""
    SELECT COUNT(*) AS total,
           SUM(CASE WHEN cores IS NULL THEN 1 ELSE 0 END) AS cores_null,
           SUM(CASE WHEN threads IS NULL THEN 1 ELSE 0 END) AS threads_null,
           SUM(CASE WHEN boost_clock_ghz IS NULL THEN 1 ELSE 0 END) AS boost_null,
           SUM(CASE WHEN tdp_w IS NULL THEN 1 ELSE 0 END) AS tdp_null
    FROM cpu_specifications
""").fetchone()

# Spec completeness per GPU
gpu_nulls = con.execute("""
    SELECT COUNT(*) AS total,
           SUM(CASE WHEN memory_gb IS NULL THEN 1 ELSE 0 END) AS memory_null,
           SUM(CASE WHEN boost_clock_mhz IS NULL THEN 1 ELSE 0 END) AS boost_null,
           SUM(CASE WHEN tdp_w IS NULL THEN 1 ELSE 0 END) AS tdp_null
    FROM gpu_specifications
""").fetchone()

# Benchmark rows per hardware (distribution)
bench_dist = con.execute("""
    SELECT cnt, COUNT(*) FROM (
        SELECT hardware_id, COUNT(*) AS cnt FROM benchmark_results GROUP BY hardware_id
    ) GROUP BY cnt ORDER BY cnt
""").fetchall()

out = {
    "sha256": sha,
    "quick_check": quick,
    "foreign_key_check_rows": len(fk),
    "table_counts": counts,
    "benchmark_coverage": [
        {"type": t, "total": tot, "with_benchmarks": wb}
        for t, tot, wb in bench_coverage
    ],
    "cpu_spec_nulls": {
        "total": cpu_nulls[0], "cores": cpu_nulls[1], "threads": cpu_nulls[2],
        "boost_clock": cpu_nulls[3], "tdp": cpu_nulls[4],
    },
    "gpu_spec_nulls": {
        "total": gpu_nulls[0], "memory_gb": gpu_nulls[1],
        "boost_clock": gpu_nulls[2], "tdp": gpu_nulls[3],
    },
    "benchmarks_per_hardware_distribution": [
        {"benchmark_count": c, "hardware_count": n} for c, n in bench_dist
    ],
}
print(json.dumps(out, indent=2))
