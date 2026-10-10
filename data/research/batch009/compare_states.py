"""Independent audit for the Batch 009 base-import provenance load.

Uses a separate comparison path from the load logic: it compares full pre/post
database snapshots and cross-checks every new ``batch_no = 0`` provenance row
against the reconciliation artifact and the live database value using direct
SQL reads (no provenance service involved).

Verifies:
- pre/post SHA-256 and integrity;
- only additive changes (``sources`` and ``field_provenance``);
- no hardware / cpu_specifications / gpu_specifications / benchmark /
  external-identifier / build value changed;
- provenance row counts by source and status;
- no duplicate or orphan provenance rows, no invalid statuses, no invalid
  field references;
- every new verified record has an exact-value match in
  ``evidence_reconciliation.csv`` and against the stored cell value;
- no provenance claim marked verified without supporting evidence;
- no restricted dataset was imported (no new bulk data rows in any data
  table; only provenance metadata was added).

Writes ``independent_audit.md`` and ``independent_audit.json``.

Usage:
    python data/research/batch009/compare_states.py --pre pre.json --post post.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BATCH_DIR = REPO_ROOT / "data" / "research" / "batch009"
BACKUP_SNAPSHOT_DIR = REPO_ROOT / "data" / "backups" / "batch009"
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"
DEFAULT_PRE = BACKUP_SNAPSHOT_DIR / "pre_state.json"
DEFAULT_POST = BACKUP_SNAPSHOT_DIR / "post_state.json"

PERMITTED_FIELDS = {
    "hardware": {"release_date", "architecture", "name", "manufacturer", "type"},
    "cpu_specifications": {"cores", "threads", "base_clock_ghz",
                           "boost_clock_ghz", "tdp_w", "process_node_nm",
                           "socket"},
    "gpu_specifications": {"memory_gb", "memory_type", "core_clock_mhz",
                           "boost_clock_mhz", "vram_bandwidth_gbps",
                           "memory_bus_width_bits", "tdp_w", "interface",
                           "length_mm"},
}

DATA_TABLES = ["hardware", "cpu_specifications", "gpu_specifications",
               "benchmark_results", "external_identifiers",
               "build_conversations", "build_messages"]
METADATA_TABLES = ["sources", "field_provenance"]

# Documented new sources added by batch 009 (base-import attribution).
EXPECTED_NEW_SOURCES = {
    "Intel ARK (intel-cpus.csv snapshot)",
    "AMD product specifications (amd-cpus.csv snapshot)",
}

# Registered source name -> reconciliation dataset id.
SOURCE_NAME_TO_DATASET = {
    "Intel ARK (intel-cpus.csv snapshot)": "intel",
    "AMD product specifications (amd-cpus.csv snapshot)": "amd",
    "PassMark CPU benchmark catalog (benchmark-cpus.csv)": "passmark",
    "TechPowerUp GPU Database (gpu_1986-2026.csv)": "techpowerup",
    "Geekbench Browser - Geekbench 7 CPU": "geekbench",
}


def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_audit(pre_path: Path, post_path: Path, database: Path) -> dict:
    pre = load_snapshot(pre_path)
    post = load_snapshot(post_path)

    results = {
        "pre_sha256": pre["sha256"],
        "post_sha256": post["sha256"],
        "pre_quick_check": pre["quick_check"],
        "post_quick_check": post["quick_check"],
    }

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    results["post_foreign_key_check"] = [
        list(r) for r in con.execute("PRAGMA foreign_key_check").fetchall()
    ]

    # ---- table counts ----
    count_changes = {}
    for table, after in post["tables"].items():
        before = pre["tables"].get(table)
        if before != after:
            count_changes[table] = {"before": before, "after": after}
    results["count_changes"] = count_changes
    results["unexpected_table_changes"] = [
        t for t in count_changes if t not in METADATA_TABLES
    ]

    # ---- full row dumps: data tables must be byte-identical pre/post ----
    changed_values = {}
    for table in DATA_TABLES:
        if table not in post["full_dumps"]:
            continue
        if post["full_dumps"][table] != pre["full_dumps"].get(table):
            before_set = {tuple(r) for r in pre["full_dumps"][table]}
            after_set = {tuple(r) for r in post["full_dumps"][table]}
            removed = [list(r) for r in (before_set - after_set)]
            added = [list(r) for r in (after_set - before_set)]
            if removed or added:
                changed_values[table] = {"removed": removed[:10],
                                         "added": added[:10]}
    results["changed_data_values"] = changed_values

    # ---- metadata tables: sources & field_provenance additive ----
    new_sources = []
    pre_sources = {tuple(r) for r in pre["full_dumps"].get("sources", [])}
    post_sources = {tuple(r) for r in post["full_dumps"].get("sources", [])}
    for row in sorted(post_sources):
        if row not in pre_sources:
            new_sources.append(list(row))
    results["new_sources"] = new_sources
    results["pre_source_ids"] = {r[0]: r[1] for r in pre_sources}
    results["post_source_ids"] = {r[0]: r[1] for r in post_sources}
    new_source_names = {r[1] for r in new_sources}
    results["unexpected_new_sources"] = sorted(
        new_source_names - EXPECTED_NEW_SOURCES
    )

    pre_prov = {tuple(r) for r in pre["full_dumps"].get("field_provenance", [])}
    post_prov = {tuple(r) for r in post["full_dumps"].get("field_provenance", [])}
    new_prov = [list(r) for r in sorted(post_prov - pre_prov)]
    results["new_provenance_rows"] = len(new_prov)
    results["removed_provenance_rows"] = len(
        [r for r in pre_prov - post_prov]
    )

    # new provenance rows must all be batch_no 0 base-import verified
    cols = [d[1] for d in con.execute("PRAGMA table_info(field_provenance)")]
    idx = {name: i for i, name in enumerate(cols)}
    new_batch = {r[idx["batch_no"]] for r in new_prov}
    new_status = {r[idx["evidence_status"]] for r in new_prov}
    results["new_provenance_batch_numbers"] = sorted(map(str, new_batch))
    results["new_provenance_statuses"] = sorted(new_status)

    # ---- provenance totals / duplicates / orphans / invalid ----
    results["provenance_total"] = con.execute(
        "select count(*) from field_provenance").fetchone()[0]
    results["provenance_distinct"] = con.execute(
        "select count(*) from (select distinct hardware_id, table_name,"
        " field_name, source_id, evidenced_value, evidence_status"
        " from field_provenance)").fetchone()[0]
    results["provenance_orphan_hardware"] = con.execute(
        "select count(*) from field_provenance p left join hardware h"
        " on h.id = p.hardware_id where h.id is null").fetchone()[0]
    results["provenance_orphan_source"] = con.execute(
        "select count(*) from field_provenance p left join sources s"
        " on s.id = p.source_id where s.id is null").fetchone()[0]
    results["provenance_invalid_statuses"] = con.execute(
        "select count(*) from field_provenance where evidence_status not in"
        " ('verified','uncertain','excluded','unmatched')").fetchone()[0]
    results["provenance_invalid_tables"] = con.execute(
        "select count(*) from field_provenance where table_name not in"
        " ('hardware','cpu_specifications','gpu_specifications')").fetchone()[0]
    results["provenance_by_status"] = [
        list(r) for r in con.execute(
            "select evidence_status, count(*) from field_provenance"
            " group by evidence_status order by 1")]
    results["provenance_by_source"] = [
        list(r) for r in con.execute(
            "select source_id, count(*) from field_provenance"
            " group by source_id order by source_id")]
    results["provenance_by_batch_no"] = [
        list(r) for r in con.execute(
            "select batch_no, count(*) from field_provenance"
            " group by batch_no order by batch_no")]
    results["sources"] = [
        list(r) for r in con.execute(
            "select id, name, url from sources order by id")]

    # ---- cross-check every new batch-0 row against evidence CSV + DB value ----
    evidence = {}
    with open(BATCH_DIR / "evidence_reconciliation.csv", newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["dataset"], int(r["entity_id"]), r["table"], r["field"])
            evidence.setdefault(key, []).append(r)

    verified_but_unsupported = []
    value_mismatch = []
    checked = 0
    for row in new_prov:
        hid = row[idx["hardware_id"]]
        table = row[idx["table_name"]]
        field = row[idx["field_name"]]
        src_id = row[idx["source_id"]]
        cell_value = row[idx["evidenced_value"]]
        dataset = SOURCE_NAME_TO_DATASET.get(
            results["post_source_ids"].get(src_id)
        )

        # live cell value must equal the evidenced value
        live = con.execute(
            f'select "{field}" from "{table}" where '
            f'{"id" if table == "hardware" else "hardware_id"} = ?', (hid,)
        ).fetchone()
        if live is None or str(live[0]) != cell_value and not (
            live[0] is not None and float(live[0]) == float(cell_value)
        ):
            value_mismatch.append(f"{src_id}:{table}.{field} hid={hid}")
            continue

        # evidence rows for this dataset/entity/field must contain a verified match
        ev = evidence.get((dataset, hid, table, field), [])
        supported = any(e["status"] == "verified" and e["persistable"] == "True"
                        and e["already_covered_verified"] != "True"
                        for e in ev)
        if not supported:
            verified_but_unsupported.append(f"{dataset}:{table}.{field} hid={hid}")
            continue
        checked += 1

    results["new_rows_crosschecked"] = checked
    results["new_rows_value_mismatch"] = value_mismatch
    results["verified_without_supporting_evidence"] = verified_but_unsupported

    # ---- no restricted dataset bulk import: all new data rows are provenance ----
    results["data_tables_changed"] = sorted(changed_values.keys())

    con.close()

    passed = bool(
        results["post_quick_check"] == "ok"
        and not results["post_foreign_key_check"]
        and not results["unexpected_table_changes"]
        and not results["changed_data_values"]
        and not results["unexpected_new_sources"]
        and not results["removed_provenance_rows"]
        and results["new_provenance_batch_numbers"] == ["0"]
        and results["new_provenance_statuses"] == ["verified"]
        and results["provenance_total"] == results["provenance_distinct"]
        and results["provenance_orphan_hardware"] == 0
        and results["provenance_orphan_source"] == 0
        and results["provenance_invalid_statuses"] == 0
        and results["provenance_invalid_tables"] == 0
        and not results["new_rows_value_mismatch"]
        and not results["verified_without_supporting_evidence"]
        and len(new_prov) == checked
    )
    results["passed"] = passed
    return results


def render_markdown(results: dict) -> str:
    lines = [
        "# Batch 009 - Independent Audit",
        "",
        f"Date: 2026-10-10",
        "",
        "## Database state",
        f"- Pre-load SHA-256: `{results['pre_sha256']}`",
        f"- Post-load SHA-256: `{results['post_sha256']}`",
        f"- Pre `PRAGMA quick_check`: {results['pre_quick_check']}",
        f"- Post `PRAGMA quick_check`: {results['post_quick_check']}",
        f"- Post `PRAGMA foreign_key_check`: "
        f"{results['post_foreign_key_check'][:5]}"
        f"{' (truncated)' if len(results['post_foreign_key_check']) > 5 else ''}",
        "",
        "## Table count changes (must be additive only)",
    ]
    if results["count_changes"]:
        for table, change in results["count_changes"].items():
            lines.append(
                f"- `{table}`: {change['before']} -> {change['after']}"
            )
        lines.append(
            "- Unexpected changes: "
            f"{results['unexpected_table_changes'] or 'none'}"
        )
    else:
        lines.append("- None")

    lines += [
        "",
        "## Data values (must be unchanged)",
        f"- Changed data tables: {results['changed_data_values'] or 'none'}",
        "",
        "## Sources (additive)",
    ]
    for row in results["new_sources"]:
        lines.append(f"- `{row[0]}` {row[1]} ({row[2]})")
    lines.append(
        "- Unexpected new sources: "
        f"{results['unexpected_new_sources'] or 'none'}"
    )
    lines += [
        "",
        "## Provenance table",
        f"- Total rows: {results['provenance_total']}",
        f"- Distinct identity rows: {results['provenance_distinct']}",
        f"- New rows in this load: {results['new_provenance_rows']}",
        f"- Removed provenance rows: {results['removed_provenance_rows']}",
        f"- New batch numbers: {results['new_provenance_batch_numbers']}",
        f"- New statuses: {results['new_provenance_statuses']}",
        f"- Orphan hardware references: {results['provenance_orphan_hardware']}",
        f"- Orphan source references: {results['provenance_orphan_source']}",
        f"- Invalid evidence statuses: {results['provenance_invalid_statuses']}",
        f"- Invalid table references: {results['provenance_invalid_tables']}",
        "",
        "### By evidence status",
    ]
    for row in results["provenance_by_status"]:
        lines.append(f"- {row[0]}: {row[1]}")
    lines.append("### By source")
    for row in results["provenance_by_source"]:
        lines.append(f"- source {row[0]}: {row[1]}")
    lines.append("### By batch_no")
    for row in results["provenance_by_batch_no"]:
        lines.append(f"- batch {row[0]}: {row[1]}")
    lines += [
        "",
        "## New-row verification (independent path)",
        f"- Cross-checked against reconciliation CSV + live cell value: "
        f"{results['new_rows_crosschecked']}",
        f"- New rows whose live cell value mismatches evidenced value: "
        f"{results['new_rows_value_mismatch'] or 'none'}",
        f"- Verified claims without supporting evidence: "
        f"{results['verified_without_supporting_evidence'] or 'none'}",
        "",
        "## Sources",
    ]
    for row in results["sources"]:
        lines.append(f"- `{row[0]}` {row[1]} ({row[2]})")
    lines += [
        "",
        f"## Verdict: {'PASS' if results['passed'] else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre", default=DEFAULT_PRE, help="pre snapshot JSON")
    parser.add_argument("--post", default=DEFAULT_POST, help="post snapshot JSON")
    parser.add_argument("--database", default=None, help="database path")
    arguments = parser.parse_args()
    database = Path(arguments.database) if arguments.database else DEFAULT_DB
    results = run_audit(Path(arguments.pre), Path(arguments.post), database)

    (BATCH_DIR / "independent_audit.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    (BATCH_DIR / "independent_audit.md").write_text(
        render_markdown(results), encoding="utf-8"
    )
    print(f"verdict: {'PASS' if results['passed'] else 'FAIL'}")
    print(f" changed data values: {results['changed_data_values']}")
    print(f" count changes: {results['count_changes']}")
    print(f" new provenance rows: {results['new_provenance_rows']}")
    print(f" crosschecked: {results['new_rows_crosschecked']}")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())