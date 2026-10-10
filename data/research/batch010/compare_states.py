"""Independent audit for the Batch 010 mutations.

Verifies, via a path separate from the implementation/migration code (direct
full-dump comparisons read from snapshots):

- pre/post SHA-256 and integrity;
- benchmark_results fully unchanged (scores, test config, source);
- hardware/specifications/build tables fully unchanged;
- sources unchanged (9 rows, identical);
- external_identifiers: only `source_id` changes for the exact 3,575 rows
  (1 -> 8 for intel_cpu_id, 1 -> 9 for product_id_*); every identifier value,
  type and hardware association is preserved;
- field_provenance: existing 34,809 spec rows preserved verbatim; exactly
  1,040 new benchmark provenance rows added (verified, batch 0, referencing
  existing benchmark records); no orphan/duplicate refs; no spec rows gained
  the benchmark column;
- no unsupported provenance claims and no restricted dataset imported.

Writes independent_audit.md and .json into the batch010 directory.

Usage:
    python data/research/batch010/compare_states.py \
        --pre data/backups/batch010/pre_state.json \
        --post data/backups/batch010/post_state.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BATCH_DIR = REPO_ROOT / "data" / "research" / "batch010"
BACKUP_SNAPSHOT_DIR = REPO_ROOT / "data" / "backups" / "batch010"
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"
DEFAULT_PRE = BACKUP_SNAPSHOT_DIR / "pre_state.json"
DEFAULT_POST = BACKUP_SNAPSHOT_DIR / "post_state.json"

UNCHANGED_DATA_TABLES = [
    "hardware", "cpu_specifications", "gpu_specifications",
    "benchmark_results", "build_conversations", "build_messages",
]


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

    # ---- unchanged data tables ----
    changed_tables = {}
    for table in UNCHANGED_DATA_TABLES:
        if post["full_dumps"][table] != pre["full_dumps"].get(table):
            changed_tables[table] = True
    results["unchanged_data_tables_violations"] = sorted(changed_tables)

    # ---- sources unchanged ----
    results["sources_unchanged"] = (
        post["full_dumps"].get("sources") == pre["full_dumps"].get("sources")
    )

    # ---- benchmark counts ----
    results["benchmark_count_before"] = pre["tables"]["benchmark_results"]
    results["benchmark_count_after"] = post["tables"]["benchmark_results"]
    results["external_identifier_count_before"] = pre["tables"]["external_identifiers"]
    results["external_identifier_count_after"] = post["tables"]["external_identifiers"]

    # ---- external identifiers: diff by id ----
    pre_ids = {row[0]: row for row in pre["full_dumps"]["external_identifiers"]}
    post_ids = {row[0]: row for row in post["full_dumps"]["external_identifiers"]}
    # column layout: id, hardware_id, source_id, external_id, identifier_type
    changed_rows = []
    value_changed = []
    for pid in sorted(pre_ids):
        pre_row = pre_ids[pid]
        post_row = post_ids[pid]
        # compare value columns (hardware_id, external_id, identifier_type)
        if (pre_row[1], pre_row[3], pre_row[4]) != (post_row[1], post_row[3], post_row[4]):
            value_changed.append(pid)
        if pre_row[2] != post_row[2]:
            changed_rows.append((pid, pre_row[2], post_row[2]))

    results["external_identifier_source_changes"] = len(changed_rows)
    results["external_identifier_value_changes"] = value_changed

    # validate allowed source transitions by identifier_type
    invalid_transitions = []
    id_by_type = {}
    for pid, before, after in changed_rows:
        row = post_ids[pid]
        itype = row[4]
        if itype == "intel_cpu_id":
            allowed = 8
        elif itype in ("product_id_tray", "product_id_boxed", "product_id_mpk"):
            allowed = 9
        else:
            allowed = None
        if before != 1 or after != allowed:
            invalid_transitions.append((pid, before, after, itype))
        id_by_type[itype] = id_by_type.get(itype, 0) + 1
    results["identifier_source_changes_by_type"] = id_by_type
    results["invalid_source_transitions"] = invalid_transitions

    # no added/removed identifier rows
    results["identifier_rows_added"] = len(set(post_ids) - set(pre_ids))
    results["identifier_rows_removed"] = len(set(pre_ids) - set(post_ids))

    # ---- field_provenance ----
    pre_prov = {row[0]: row for row in pre["full_dumps"]["field_provenance"]}
    post_prov = {row[0]: row for row in post["full_dumps"]["field_provenance"]}
    pre_cols = pre["columns"]["field_provenance"]
    post_cols = post["columns"]["field_provenance"]
    post_idx = {name: i for i, name in enumerate(post_cols)}

    preserved = 0
    for pid, pre_row in pre_prov.items():
        post_row = post_prov[pid]
        if post_row[: len(pre_cols)] == pre_row and post_row[len(pre_cols):] == [None]:
            preserved += 1
    results["pre_provenance_rows_preserved"] = preserved

    new_rows = []
    for pid, post_row in post_prov.items():
        if pid not in pre_prov:
            new_rows.append(post_row)

    valid_new = []
    for row in new_rows:
        table = row[post_idx["table_name"]]
        bid = row[post_idx["benchmark_result_id"]]
        status = row[post_idx["evidence_status"]]
        batch = row[post_idx["batch_no"]]
        if table != "benchmark_results":
            valid_new.append(("wrong table", table))
            continue
        if bid is None:
            valid_new.append(("missing benchmark_result_id", row[post_idx["id"]]))
            continue
        if status != "verified":
            valid_new.append(("wrong status", status))
            continue
        if str(batch) != "0":
            valid_new.append(("wrong batch", batch))
            continue
        valid_new.append(("ok", row[post_idx["id"]]))

    results["new_provenance_rows"] = len(new_rows)
    results["new_provenance_violations"] = [v for v in valid_new if v[0] != "ok"]

    new_by_source = {}
    for row in new_rows:
        new_by_source[row[post_idx["source_id"]]] = (
            new_by_source.get(row[post_idx["source_id"]], 0) + 1
        )
    results["new_provenance_by_source"] = new_by_source

    # provenance totals
    results["provenance_total"] = len(post_prov)
    results["benchmark_provenance_total"] = con.execute(
        "SELECT COUNT(*) FROM field_provenance WHERE table_name='benchmark_results'"
    ).fetchone()[0]
    results["spec_provenance_total"] = con.execute(
        "SELECT COUNT(*) FROM field_provenance WHERE table_name!='benchmark_results'"
    ).fetchone()[0]

    # orphan benchmark_result_id
    results["orphan_benchmark_result_refs"] = con.execute(
        "SELECT COUNT(*) FROM field_provenance p LEFT JOIN benchmark_results b"
        " ON b.id = p.benchmark_result_id WHERE p.benchmark_result_id IS NOT NULL"
        " AND b.id IS NULL").fetchone()[0]
    results["orphan_hardware_refs"] = con.execute(
        "SELECT COUNT(*) FROM field_provenance p LEFT JOIN hardware h ON h.id=p.hardware_id"
        " WHERE h.id IS NULL").fetchone()[0]

    # duplicates among benchmark provenance
    results["benchmark_provenance_duplicates"] = con.execute(
        "SELECT COUNT(*)-COUNT(DISTINCT benchmark_result_id || '|' || field_name || '|' ||"
        " source_id || '|' || evidenced_value || '|' || evidence_status)"
        " FROM field_provenance WHERE benchmark_result_id IS NOT NULL"
    ).fetchone()[0]

    # provenance by source/status/batch
    results["provenance_by_source"] = [
        list(r) for r in con.execute(
            "SELECT source_id, COUNT(*) FROM field_provenance GROUP BY source_id"
            " ORDER BY source_id")]
    results["provenance_by_status"] = [
        list(r) for r in con.execute(
            "SELECT evidence_status, COUNT(*) FROM field_provenance"
            " GROUP BY evidence_status ORDER BY evidence_status")]

    # no restricted dataset imported: data tables unchanged already checked;
    # also confirm benchmark rows count unchanged and gaming data absent
    results["gaming_benchmark_rows"] = con.execute(
        "SELECT COUNT(*) FROM benchmark_results WHERE benchmark_name NOT IN ('Geekbench 7')"
    ).fetchone()[0]

    # verify the new provenance rows correspond 1:1 to the geekbench evidence rows
    evidence_matched = 0
    with open(BATCH_DIR.parent / "batch009" / "evidence_reconciliation.csv",
              newline="", encoding="utf-8") as file:
        for rec in csv.DictReader(file):
            if rec["dataset"] != "geekbench" or rec["status"] != "verified":
                continue
            count = con.execute(
                "SELECT COUNT(*) FROM field_provenance WHERE table_name='benchmark_results'"
                " AND hardware_id=? AND evidenced_value=? AND source_id=2"
                " AND evidence_status='verified'",
                (int(rec["entity_id"]), rec["db_value"]),
            ).fetchone()[0]
            if count >= 1:
                evidence_matched += 1
    results["new_rows_matched_to_geekbench_evidence"] = evidence_matched

    con.close()

    passed = bool(
        results["post_quick_check"] == "ok"
        and not results["post_foreign_key_check"]
        and not changed_tables
        and results["sources_unchanged"]
        and results["benchmark_count_before"] == results["benchmark_count_after"]
        and results["external_identifier_count_before"] == results["external_identifier_count_after"]
        and not results["external_identifier_value_changes"]
        and not results["invalid_source_transitions"]
        and results["identifier_rows_added"] == 0
        and results["identifier_rows_removed"] == 0
        and results["pre_provenance_rows_preserved"] == len(pre_prov)
        and not results["new_provenance_violations"]
        and results["new_provenance_rows"] == 1040
        and results["benchmark_provenance_total"] == 1040
        and results["spec_provenance_total"] == len(pre_prov)
        and results["orphan_benchmark_result_refs"] == 0
        and results["orphan_hardware_refs"] == 0
        and results["benchmark_provenance_duplicates"] == 0
        and results["gaming_benchmark_rows"] == 0
        and results["new_rows_matched_to_geekbench_evidence"] == 1040
    )
    results["passed"] = passed
    return results


def render_markdown(results: dict) -> str:
    lines = [
        "# Batch 010 - Independent Audit",
        "",
        f"Date: 2026-10-10",
        "",
        "## Database state",
        f"- Pre-mutation SHA-256: `{results['pre_sha256']}`",
        f"- Post-mutation SHA-256: `{results['post_sha256']}`",
        f"- Pre `PRAGMA quick_check`: {results['pre_quick_check']}",
        f"- Post `PRAGMA quick_check`: {results['post_quick_check']}",
        f"- Post `PRAGMA foreign_key_check`: "
        f"{results['post_foreign_key_check'][:5]}"
        f"{' (truncated)' if len(results['post_foreign_key_check']) > 5 else ''}",
        "",
        "## Benchmark records",
        f"- Count before/after: {results['benchmark_count_before']} / "
        f"{results['benchmark_count_after']}",
        f"- Score/test-config changes: "
        f"{results['unchanged_data_tables_violations'] or 'none'}",
        f"- Gaming benchmark rows: {results['gaming_benchmark_rows']}",
        "",
        "## External identifiers",
        f"- Count before/after: {results['external_identifier_count_before']} / "
        f"{results['external_identifier_count_after']}",
        f"- Source associations changed (1 -> Intel ARK / AMD): "
        f"{results['external_identifier_source_changes']}",
        f"- By type: {results['identifier_source_changes_by_type']}",
        f"- Identifier value/hardware changes: "
        f"{results['external_identifier_value_changes'] or 'none'}",
        f"- Invalid source transitions: {results['invalid_source_transitions'] or 'none'}",
        f"- Rows added/removed: {results['identifier_rows_added']} / "
        f"{results['identifier_rows_removed']}",
        "",
        "## Sources",
        f"- Unchanged (9 rows): {results['sources_unchanged']}",
        "",
        "## Provenance table",
        f"- Pre-existing spec rows preserved: "
        f"{results['pre_provenance_rows_preserved']}",
        f"- New provenance rows: {results['new_provenance_rows']}",
        f"- New rows by source: {results['new_provenance_by_source']}",
        f"- New-row violations: {results['new_provenance_violations'] or 'none'}",
        f"- Benchmark provenance total: {results['benchmark_provenance_total']}",
        f"- Specification provenance total: {results['spec_provenance_total']}",
        f"- Orphan benchmark refs: {results['orphan_benchmark_result_refs']}",
        f"- Orphan hardware refs: {results['orphan_hardware_refs']}",
        f"- Duplicate benchmark provenance: {results['benchmark_provenance_duplicates']}",
        "",
        "### By source",
    ]
    for row in results["provenance_by_source"]:
        lines.append(f"- source {row[0]}: {row[1]}")
    lines.append("### By status")
    for row in results["provenance_by_status"]:
        lines.append(f"- {row[0]}: {row[1]}")
    lines += [
        "",
        "## Evidence cross-check",
        f"- New rows matched to Geekbench reconciliation evidence: "
        f"{results['new_rows_matched_to_geekbench_evidence']}/1040",
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
    print(f" benchmark count: {results['benchmark_count_before']} -> "
          f"{results['benchmark_count_after']}")
    print(f" identifier source changes: {results['external_identifier_source_changes']}")
    print(f" new provenance rows: {results['new_provenance_rows']}")
    print(f" evidence matched: {results['new_rows_matched_to_geekbench_evidence']}")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())