"""Independent Batch 015 audit.

Compares the live database against the pre-change backup and verifies that the
batch changed *only* the ``sources`` registry: no hardware, specification,
benchmark, external-identifier, provenance or build row differs; no source was
deleted or renamed; foreign keys and integrity are intact; and the new
read-only endpoints exist while the pre-existing benchmark endpoint keeps its
response contract.

Writes ``_audit_result.json`` and exits non-zero if any check fails.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_LIVE = Path(r"C:\SPECTRA\data\spectra.db")
DEFAULT_BACKUP = Path(
    r"C:\SPECTRA\data\backups\spectra.db.batch015-20261012T062934Z.bak"
)
OUT = HERE / "_audit_result.json"

# Tables that must be byte-for-byte identical in content before and after.
UNCHANGED_TABLES = [
    "hardware",
    "cpu_specifications",
    "gpu_specifications",
    "benchmark_results",
    "external_identifiers",
    "field_provenance",
    "build_conversations",
    "build_messages",
]

NEW_SOURCE_COLUMNS = [
    "publisher",
    "description",
    "license_name",
    "license_url",
    "license_status",
    "terms_notes",
    "attribution",
    "retrieved_on",
]

VALID_LICENSE_STATUSES = {"clear", "unknown", "restricted", "unresolved"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({table})")]


def table_rows(con, table: str) -> list[tuple]:
    return [tuple(row) for row in con.execute(f"SELECT * FROM {table}")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_LIVE))
    parser.add_argument("--backup", default=str(DEFAULT_BACKUP))
    args = parser.parse_args()

    live_path = Path(args.database)
    backup_path = Path(args.backup)

    live = connect(live_path)
    backup = connect(backup_path)

    checks = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    # 1. Unchanged table content.
    for table in UNCHANGED_TABLES:
        before = table_rows(backup, table)
        after = table_rows(live, table)
        check(
            f"{table}_unchanged",
            before == after,
            f"before={len(before)} after={len(after)}",
        )

    # 2. Source identity (id, name, url) preserved; no delete/rename/remap.
    before_sources = [
        (row["id"], row["name"], row["url"])
        for row in backup.execute("SELECT id, name, url FROM sources ORDER BY id")
    ]
    after_sources = [
        (row["id"], row["name"], row["url"])
        for row in live.execute("SELECT id, name, url FROM sources ORDER BY id")
    ]
    check(
        "sources_identity_preserved",
        before_sources == after_sources,
        f"rows={len(after_sources)}",
    )

    # 3. Additive schema only: the unchanged tables keep identical columns.
    for table in UNCHANGED_TABLES:
        check(
            f"{table}_columns_unchanged",
            columns(backup, table) == columns(live, table),
            "",
        )

    # 3b. sources gained exactly the new nullable metadata columns.
    live_source_columns = columns(live, "sources")
    check(
        "sources_new_columns_added",
        all(col in columns(live, "sources") for col in NEW_SOURCE_COLUMNS),
        ",".join(NEW_SOURCE_COLUMNS),
    )
    added = [
        col
        for col in columns(live, "sources")
        if col not in columns(backup, "sources")
    ]
    check(
        "only_expected_columns_added",
        set(added) == set(NEW_SOURCE_COLUMNS),
        f"added={sorted(added)}",
    )

    # 3b-ii. Every added column is nullable (purely additive).
    not_null = [
        row[1]
        for row in live.execute("PRAGMA table_info(sources)")
        if row[1] in NEW_SOURCE_COLUMNS and row[3] == 1
    ]
    check("added_columns_are_nullable", not_null == [], f"not_null={not_null}")

    # 4. Integrity and foreign keys.
    check(
        "integrity_check_ok",
        live.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
    )
    fk_violations = live.execute("PRAGMA foreign_key_check").fetchall()
    check("no_foreign_key_violations", len(fk_violations) == 0,
          f"count={len(fk_violations)}")

    # 5. Source metadata is populated and uses the declared vocabulary.
    statuses = {
        row["id"]: row["license_status"]
        for row in live.execute("SELECT id, license_status FROM sources")
    }
    check(
        "all_sources_have_license_status",
        all(value is not None for value in statuses.values()),
        f"statuses={statuses}",
    )
    check(
        "license_status_vocabulary_valid",
        all(value in VALID_LICENSE_STATUSES for value in statuses.values()),
        f"statuses={statuses}",
    )
    check(
        "license_status_distinctions_present",
        set(statuses.values()) == VALID_LICENSE_STATUSES,
        f"present={sorted(set(statuses.values()))}",
    )

    # 6. Provenance rows still reference valid sources and hardware.
    orphan_sources = live.execute(
        "SELECT COUNT(*) FROM field_provenance fp WHERE NOT EXISTS "
        "(SELECT 1 FROM sources s WHERE s.id = fp.source_id)"
    ).fetchone()[0]
    check("provenance_sources_valid", orphan_sources == 0,
          f"orphans={orphan_sources}")

    # 7. Provenance count parity with the pre-change backup.
    before_prov = backup.execute(
        "SELECT COUNT(*) FROM field_provenance"
    ).fetchone()[0]
    after_prov = live.execute(
        "SELECT COUNT(*) FROM field_provenance"
    ).fetchone()[0]
    check("provenance_count_unchanged", before_prov == after_prov,
          f"before={before_prov} after={after_prov}")

    # 8. Read-only API surface: new routes present, benchmark response contract
    #    unchanged (fields exactly as before this batch).
    try:
        import backend.app.main as main_module  # noqa: F401
        from backend.app.schemas.benchmark import BenchmarkResultResponse

        paths = {route.path for route in main_module.app.routes}
        expected_paths = {
            "/sources",
            "/sources/{source_id}",
            "/hardware/{hardware_id}/provenance",
            "/benchmarks/{benchmark_result_id}/provenance",
        }
        check(
            "new_routes_registered",
            expected_paths <= paths,
            f"missing={sorted(expected_paths - paths)}",
        )
        benchmark_fields = set(BenchmarkResultResponse.model_fields)
        check(
            "benchmark_response_contract_unchanged",
            benchmark_fields
            == {
                "id",
                "hardware_id",
                "benchmark_name",
                "score",
                "unit",
                "test_type",
                "source",
                "recorded_at",
            },
            f"fields={sorted(benchmark_fields)}",
        )
    except Exception as error:  # pragma: no cover - defensive
        check("api_surface_inspected", False, f"{type(error).__name__}: {error}")

    live.close()
    backup.close()

    passed = all(item["passed"] for item in checks)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "sha256": sha256(live_path),
            "name": live_path.name,
        },
        "backup": {
            "sha256": sha256(backup_path),
            "name": backup_path.name,
        },
        "passed": passed,
        "checks": checks,
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(f"wrote {OUT}")
    for item in checks:
        print(("PASS" if item["passed"] else "FAIL"), item["name"],
              item["detail"])
    print("OVERALL:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
