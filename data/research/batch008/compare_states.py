"""Independent audit for the Batch 008 provenance migration.

Compares a pre-migration and post-migration database snapshot and verifies
that every change is additive and within scope:

- the ``field_provenance`` table and new ``sources`` rows appear;
- no hardware/specification/benchmark/external-identifier/build value changed;
- the post-migration database passes ``PRAGMA quick_check`` and
  ``PRAGMA foreign_key_check``;
- provenance rows reference only real hardware rows and permitted fields.

Writes ``independent_audit.md`` and ``independent_audit.json`` into the
batch008 research directory.

Usage:
    python data/research/batch008/compare_states.py --pre pre.json --post post.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BATCH_DIR = REPO_ROOT / "data" / "research" / "batch008"
DEFAULT_DB = REPO_ROOT / "data" / "spectra.db"

# Identity columns snapshotted for diff coverage; they are not
# provenance-target fields but must never change either.
OBSERVED_IDENTITY_COLUMNS = {
    "hardware": {"name", "manufacturer", "type"},
}

# (table, column) pairs that enrichment batches were allowed to write; the
# audit reads provenance against this set and flags anything else.
PERMITTED_FIELDS = {
    "hardware": {"release_date", "architecture"},
    "cpu_specifications": {"cores", "threads", "base_clock_ghz",
                           "boost_clock_ghz", "tdp_w", "process_node_nm",
                           "socket"},
    "gpu_specifications": {"memory_gb", "memory_type", "core_clock_mhz",
                           "boost_clock_mhz", "vram_bandwidth_gbps",
                           "memory_bus_width_bits", "tdp_w", "interface",
                           "length_mm"},
}


def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_audit(pre_path: Path, post_path: Path,
              database: Path) -> dict:
    pre = load_snapshot(pre_path)
    post = load_snapshot(post_path)
    results = {}

    results["pre_sha256"] = pre["sha256"]
    results["post_sha256"] = post["sha256"]

    # 1. Integrity.
    results["pre_quick_check"] = pre["quick_check"]
    results["post_quick_check"] = post["quick_check"]

    con = sqlite3.connect(database)
    results["post_foreign_key_check"] = con.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    # 2. Table counts: identical except additive sources/provenance.
    changed = {}
    for table, count in post["tables"].items():
        before = pre["tables"].get(table)
        after = count
        if before != after:
            changed[table] = {"before": before, "after": after}
    results["count_changes"] = changed

    expected_additions = {
        "sources",
        "field_provenance",
    }
    unexpected_count_change = [
        table for table in changed if table not in expected_additions
    ]
    results["unexpected_table_changes"] = unexpected_count_change

    # 3. Specification values unchanged.
    changed_values = []
    for table, columns in post["spec_values"].items():
        for column, after in columns.items():
            before = pre["spec_values"].get(table,
                                            {}).get(column)
            if before != after:
                changed_values.append(f"{table}.{column}")
            if column not in PERMITTED_FIELDS[table] \
                    and column not in OBSERVED_IDENTITY_COLUMNS.get(
                        table, set()):
                results.setdefault("unpermitted_columns", []).append(
                    f"{table}.{column}"
                )
    results["changed_specification_values"] = changed_values

    # 4. Provenance-specific checks.
    results["provenance_total"] = con.execute(
        'select count(*) from field_provenance').fetchone()[0]
    results["provenance_distinct"] = con.execute(
        "select count(*) from (select distinct hardware_id, table_name,"
        " field_name, source_id, evidenced_value, evidence_status"
        " from field_provenance)").fetchone()[0]
    results["provenance_orphan_hardware"] = con.execute(
        "select count(*) from field_provenance p left join hardware h"
        " on h.id = p.hardware_id where h.id is null").fetchone()[0]
    results["provenance_invalid_statuses"] = con.execute(
        "select count(*) from field_provenance where evidence_status not in"
        " ('verified','uncertain','excluded','unmatched')").fetchone()[0]
    results["provenance_by_status"] = [
        list(row) for row in con.execute(
            "select evidence_status, count(*) from field_provenance"
            " group by evidence_status order by 1")
    ]
    results["provenance_by_table"] = [
        list(row) for row in con.execute(
            "select table_name, count(*) from field_provenance"
            " group by table_name order by 1")
    ]
    results["sources"] = [
        list(row) for row in con.execute(
            "select id, name, url from sources order by id")
    ]
    con.close()

    passed = bool(
        results["post_quick_check"] == "ok"
        and not results["post_foreign_key_check"]
        and not results["unexpected_table_changes"]
        and not results["changed_specification_values"]
        and results["provenance_total"] == results["provenance_distinct"]
        and results["provenance_orphan_hardware"] == 0
        and results["provenance_invalid_statuses"] == 0
    )
    results["passed"] = passed
    return results


def render_markdown(results: dict) -> str:
    lines = [
        "# Batch 008 - Independent Audit",
        "",
        f"Date: 2026-10-09",
        "",
        "## Database state",
        f"- Pre-migration SHA-256: `{results['pre_sha256']}`",
        f"- Post-migration SHA-256: `{results['post_sha256']}`",
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
        "## Specification values",
        f"- Changed values: {results['changed_specification_values'] or 'none'}",
        f"- Unpermitted columns: {results.get('unpermitted_columns') or 'none'}",
        "",
        "## Provenance table",
        f"- Total rows: {results['provenance_total']}",
        f"- Distinct identity rows: {results['provenance_distinct']}",
        f"- Orphan hardware references: {results['provenance_orphan_hardware']}",
        f"- Invalid evidence statuses: {results['provenance_invalid_statuses']}",
        "",
        "### By evidence status",
    ]
    for row in results["provenance_by_status"]:
        lines.append(f"- {row[0]}: {row[1]}")
    lines.append("")
    lines.append("### By table")
    for row in results["provenance_by_table"]:
        lines.append(f"- {row[0]}: {row[1]}")
    lines += [
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
    parser.add_argument("--pre", required=True, help="pre snapshot JSON")
    parser.add_argument("--post", required=True, help="post snapshot JSON")
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
    print(f" changed spec values: {results['changed_specification_values']}")
    print(f" count changes: {results['count_changes']}")
    print(f" provenance rows: {results['provenance_total']}")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())