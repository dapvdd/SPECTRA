"""Build the machine-readable Batch 015 source & provenance audit.

Read-only. Reads the live database and writes ``_source_audit.json`` next to
this script. It reports what is actually recorded: the source registry (with
its licence metadata), per-source provenance usage, the licence-status
distinctions, and the honest coverage gaps (fields/records with no
provenance). No value is inferred and no permissive licence is assumed.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = Path(r"C:\SPECTRA\data\spectra.db")
OUT = HERE / "_source_audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    def one(sql, args=()):
        return con.execute(sql, args).fetchone()[0]

    def rows(sql, args=()):
        return [dict(r) for r in con.execute(sql, args)]

    source_rows = rows(
        """
        SELECT s.id, s.name, s.url, s.publisher, s.description, s.license_name,
               s.license_url, s.license_status, s.terms_notes, s.attribution,
               s.retrieved_on
        FROM sources s ORDER BY s.id
        """
    )

    usage = {
        row["source_id"]: row
        for row in rows(
            """
            SELECT source_id, COUNT(*) AS provenance_records,
                   COUNT(DISTINCT hardware_id) AS hardware_records,
                   COUNT(DISTINCT benchmark_result_id) AS benchmark_records
            FROM field_provenance GROUP BY source_id
            """
        )
    }

    status_counts = {}
    for row in rows(
        """
        SELECT source_id, evidence_status, COUNT(*) AS n
        FROM field_provenance GROUP BY source_id, evidence_status
        """
    ):
        status_counts.setdefault(row["source_id"], {})[
            row["evidence_status"]
        ] = row["n"]

    sources = []
    for source in source_rows:
        source_id = source["id"]
        usage_row = usage.get(source_id, {})
        sources.append(
            {
                **source,
                "usage": {
                    "provenance_records": int(
                        usage_row.get("provenance_records", 0)
                    ),
                    "hardware_records": int(
                        usage_row.get("hardware_records", 0)
                    ),
                    "benchmark_records": int(
                        usage_row.get("benchmark_records", 0)
                    ),
                },
                "evidence_status_counts": status_counts.get(source_id, {}),
            }
        )

    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "path_name": DB.name,
            "sha256": sha256(DB),
            "integrity_check": one("PRAGMA integrity_check"),
            "foreign_key_violations": len(
                con.execute("PRAGMA foreign_key_check").fetchall()
            ),
        },
        "totals": {
            "hardware": one("SELECT COUNT(*) FROM hardware"),
            "cpu_specifications": one("SELECT COUNT(*) FROM cpu_specifications"),
            "gpu_specifications": one("SELECT COUNT(*) FROM gpu_specifications"),
            "benchmark_results": one("SELECT COUNT(*) FROM benchmark_results"),
            "external_identifiers": one("SELECT COUNT(*) FROM external_identifiers"),
            "field_provenance": one("SELECT COUNT(*) FROM field_provenance"),
            "field_provenance_specification": one(
                "SELECT COUNT(*) FROM field_provenance"
                " WHERE benchmark_result_id IS NULL"
            ),
            "field_provenance_benchmark": one(
                "SELECT COUNT(*) FROM field_provenance"
                " WHERE benchmark_result_id IS NOT NULL"
            ),
            "sources": len(source_rows),
        },
        "license_distinctions": {
            "cc_by_4_0": one(
                "SELECT COUNT(*) FROM field_provenance WHERE license_name = 'CC BY 4.0'"
            ),
            "cc_by_sa_4_0": one(
                "SELECT COUNT(*) FROM field_provenance"
                " WHERE license_name = 'CC BY-SA 4.0'"
            ),
            "no_license_recorded": one(
                "SELECT COUNT(*) FROM field_provenance WHERE license_name IS NULL"
            ),
            "source_clear": one(
                "SELECT COUNT(*) FROM sources WHERE license_status = 'clear'"
            ),
            "source_unknown": one(
                "SELECT COUNT(*) FROM sources WHERE license_status = 'unknown'"
            ),
            "source_restricted": one(
                "SELECT COUNT(*) FROM sources WHERE license_status = 'restricted'"
            ),
            "source_unresolved": one(
                "SELECT COUNT(*) FROM sources WHERE license_status = 'unresolved'"
            ),
        },
        "provenance_coverage": {
            "records_with_attribution": one(
                "SELECT COUNT(*) FROM field_provenance WHERE attribution IS NOT NULL"
            ),
            "records_without_attribution": one(
                "SELECT COUNT(*) FROM field_provenance WHERE attribution IS NULL"
            ),
            "records_with_source_reference": one(
                "SELECT COUNT(*) FROM field_provenance WHERE source_reference IS NOT NULL"
            ),
            "records_without_source_reference": one(
                "SELECT COUNT(*) FROM field_provenance WHERE source_reference IS NULL"
            ),
            "records_without_license_name": one(
                "SELECT COUNT(*) FROM field_provenance WHERE license_name IS NULL"
            ),
            "benchmarks_total": one("SELECT COUNT(*) FROM benchmark_results"),
            "benchmarks_with_provenance": one(
                "SELECT COUNT(DISTINCT benchmark_result_id) FROM field_provenance "
                "WHERE benchmark_result_id IS NOT NULL"
            ),
            "benchmarks_without_provenance": one(
                "SELECT COUNT(*) FROM benchmark_results b WHERE NOT EXISTS ("
                "  SELECT 1 FROM field_provenance fp"
                "  WHERE fp.benchmark_result_id = b.id)"
            ),
        },
        "coverage_gaps": {
            "cpus_with_specs_without_spec_provenance": one(
                "SELECT COUNT(*) FROM cpu_specifications cs WHERE NOT EXISTS ("
                " SELECT 1 FROM field_provenance fp WHERE fp.hardware_id = cs.hardware_id"
                " AND fp.benchmark_result_id IS NULL)"
            ),
            "gpus_with_specs_without_spec_provenance": one(
                "SELECT COUNT(*) FROM gpu_specifications gs WHERE NOT EXISTS ("
                " SELECT 1 FROM field_provenance fp WHERE fp.hardware_id = gs.hardware_id"
                " AND fp.benchmark_result_id IS NULL)"
            ),
            "hardware_without_any_provenance": one(
                "SELECT COUNT(*) FROM hardware h WHERE NOT EXISTS ("
                " SELECT 1 FROM field_provenance fp WHERE fp.hardware_id = h.id)"
            ),
            "provenance_without_source_row": one(
                "SELECT COUNT(*) FROM field_provenance fp WHERE NOT EXISTS ("
                " SELECT 1 FROM sources s WHERE s.id = fp.source_id)"
            ),
        },
        "sources": sources,
    }

    con.close()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2, ensure_ascii=False)
    print(f"wrote {OUT}")
    print(json.dumps(audit["license_distinctions"], indent=2))
    print(json.dumps(audit["coverage_gaps"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
