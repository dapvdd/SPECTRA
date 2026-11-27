"""Profile candidate source DBs (read-only) to pick the M4 dev baseline."""
import sqlite3, os

for label, path in [
    ("M3.2 dev", r"C:\Users\user\spectra-m32\data\dev\spectra_dev.db"),
    ("M3.3 prod-like", r"C:\Users\user\spectra-m32\data\spectra.db"),
]:
    if not os.path.exists(path):
        print(label, "MISSING")
        continue
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c = conn.cursor()
    print("=" * 20, label, "=" * 20)
    print("types:", c.execute("SELECT type, COUNT(*) FROM hardware GROUP BY type").fetchall())
    print("benchmarks:", c.execute("SELECT benchmark_name, test_type, COUNT(*), COUNT(DISTINCT hardware_id) FROM benchmark_results GROUP BY benchmark_name, test_type").fetchall())
    print("cpu spec coverage:", {f: c.execute(f"SELECT COUNT(*) FROM cpu_specifications WHERE {f} IS NOT NULL").fetchone()[0] for f in ["cores","threads","base_clock_ghz","boost_clock_ghz","tdp_w","socket","process_node_nm"]})
    print("gpu spec coverage:", {f: c.execute(f"SELECT COUNT(*) FROM gpu_specifications WHERE {f} IS NOT NULL").fetchone()[0] for f in ["memory_gb","memory_type","core_clock_mhz","boost_clock_mhz","vram_bandwidth_gbps","memory_bus_width_bits","tdp_w","interface","length_mm"]})
    for t in ["ram_specifications","storage_specifications","motherboard_specifications","psu_specifications"]:
        print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    print("provenance:", c.execute("SELECT evidence_status, COUNT(*) FROM field_provenance GROUP BY evidence_status").fetchall())
    print("record_status:", c.execute("SELECT record_status, COUNT(*) FROM hardware GROUP BY record_status").fetchall())
    print("segment:", c.execute("SELECT segment, COUNT(*) FROM hardware GROUP BY segment").fetchall())
    print("release_date:", c.execute("SELECT COUNT(*) FROM hardware WHERE release_date IS NOT NULL").fetchone()[0], "architecture:", c.execute("SELECT COUNT(*) FROM hardware WHERE architecture IS NOT NULL").fetchone()[0])
    # price-like columns
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
        hits = [col for col in cols if any(k in col.lower() for k in ("price","cost","msrp"))]
        if hits:
            print("PRICE-LIKE:", t, hits)
    conn.close()
