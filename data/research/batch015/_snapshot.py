import json
import sqlite3

DB = r"C:\SPECTRA\data\spectra.db"
OUT = r"C:\SPECTRA\data\research\batch015\_db_snapshot.json"
con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
con.row_factory = sqlite3.Row


def one(sql, args=()):
    return con.execute(sql, args).fetchone()[0]


def rows(sql, args=()):
    return [dict(r) for r in con.execute(sql, args)]


snap = {}
snap["integrity_check"] = con.execute("PRAGMA integrity_check").fetchone()[0]
snap["quick_check"] = con.execute("PRAGMA quick_check").fetchone()[0]
snap["foreign_key_check"] = len(con.execute("PRAGMA foreign_key_check").fetchall())
snap["counts"] = {
    "hardware": one("SELECT COUNT(*) FROM hardware"),
    "cpu": one("SELECT COUNT(*) FROM hardware WHERE type='CPU'"),
    "gpu": one("SELECT COUNT(*) FROM hardware WHERE type='GPU'"),
    "cpu_specifications": one("SELECT COUNT(*) FROM cpu_specifications"),
    "gpu_specifications": one("SELECT COUNT(*) FROM gpu_specifications"),
    "benchmark_results": one("SELECT COUNT(*) FROM benchmark_results"),
    "sources": one("SELECT COUNT(*) FROM sources"),
    "external_identifiers": one("SELECT COUNT(*) FROM external_identifiers"),
    "field_provenance": one("SELECT COUNT(*) FROM field_provenance"),
    "field_provenance_spec": one("SELECT COUNT(*) FROM field_provenance WHERE benchmark_result_id IS NULL"),
    "field_provenance_benchmark": one("SELECT COUNT(*) FROM field_provenance WHERE benchmark_result_id IS NOT NULL"),
    "build_conversations": one("SELECT COUNT(*) FROM build_conversations"),
    "build_messages": one("SELECT COUNT(*) FROM build_messages"),
}
snap["tables"] = [r["name"] for r in rows(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
snap["field_provenance_columns"] = [r["name"] for r in rows("PRAGMA table_info(field_provenance)")]
snap["benchmark_results_columns"] = [r["name"] for r in rows("PRAGMA table_info(benchmark_results)")]
snap["sources"] = rows("SELECT * FROM sources ORDER BY id")
snap["sources_schema"] = [r["name"] for r in rows("PRAGMA table_info(sources)")]
snap["benchmarks_by_source"] = rows(
    "SELECT source_id, COUNT(*) n FROM benchmark_results GROUP BY source_id ORDER BY source_id")
snap["benchmarks_with_provenance"] = one(
    "SELECT COUNT(DISTINCT benchmark_result_id) FROM field_provenance WHERE benchmark_result_id IS NOT NULL")
snap["benchmark_null_source"] = one("SELECT COUNT(*) FROM benchmark_results WHERE source_id IS NULL")
snap["prov_by_status"] = rows(
    "SELECT evidence_status, COUNT(*) n FROM field_provenance GROUP BY evidence_status ORDER BY n DESC")
snap["prov_by_source"] = rows(
    "SELECT source_id, COUNT(*) n, COUNT(DISTINCT hardware_id) hw, COUNT(DISTINCT benchmark_result_id) bm "
    "FROM field_provenance GROUP BY source_id ORDER BY n DESC")
snap["prov_by_field_spec"] = rows(
    "SELECT field_name, COUNT(*) n FROM field_provenance WHERE benchmark_result_id IS NULL "
    "GROUP BY field_name ORDER BY n DESC")
snap["prov_by_field_benchmark"] = rows(
    "SELECT field_name, COUNT(*) n FROM field_provenance WHERE benchmark_result_id IS NOT NULL "
    "GROUP BY field_name ORDER BY n DESC")
snap["prov_batch"] = rows(
    "SELECT batch_no, COUNT(*) n FROM field_provenance GROUP BY batch_no ORDER BY batch_no")
snap["prov_license"] = rows(
    "SELECT COALESCE(license_name,'(null)') lic, COUNT(*) n FROM field_provenance "
    "GROUP BY license_name ORDER BY n DESC")
snap["prov_source_reference_null"] = one(
    "SELECT COUNT(*) FROM field_provenance WHERE source_reference IS NULL")
snap["prov_attribution_null"] = one(
    "SELECT COUNT(*) FROM field_provenance WHERE attribution IS NULL")
snap["cpu_with_spec_no_prov"] = one(
    "SELECT COUNT(*) FROM cpu_specifications cs WHERE NOT EXISTS "
    "(SELECT 1 FROM field_provenance fp WHERE fp.hardware_id=cs.hardware_id AND fp.benchmark_result_id IS NULL)")
snap["hardware_without_any_prov"] = one(
    "SELECT COUNT(*) FROM hardware h WHERE NOT EXISTS "
    "(SELECT 1 FROM field_provenance fp WHERE fp.hardware_id=h.id)")
snap["benchmark_sample"] = rows(
    "SELECT id, hardware_id, source_id, benchmark_name, score, unit, test_type "
    "FROM benchmark_results ORDER BY id LIMIT 8")
snap["benchmark_by_name"] = rows(
    "SELECT benchmark_name, test_type, unit, COUNT(*) n FROM benchmark_results "
    "GROUP BY benchmark_name, test_type, unit ORDER BY n DESC")
snap["benchmark_source_link"] = rows(
    "SELECT b.source_id, s.name source_name, COUNT(*) n FROM benchmark_results b "
    "LEFT JOIN sources s ON s.id=b.source_id GROUP BY b.source_id ORDER BY n DESC")
snap["prov_url_sample"] = rows(
    "SELECT id, source_id, table_name, field_name, evidence_status, license_name, "
    "confidence, source_reference, access_date, attribution IS NOT NULL has_attr, "
    "substr(source_url,1,60) url FROM field_provenance ORDER BY id LIMIT 12")

with open(OUT, "w", encoding="utf-8") as fh:
    import json as _j
    _j.dump(snap, fh, indent=2)
print("wrote", OUT)
print("integrity", snap["integrity_check"], "counts", snap["counts"])
print("sources", [(s["id"], s["name"]) for s in snap["sources"]])
print("prov_by_source", snap["prov_by_source"])
print("prov_by_status", snap["prov_by_status"])
print("prov_license", snap["prov_license"])
con.close()
