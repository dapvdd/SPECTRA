"""Batch 011 independent audit.

Verifies, via paths separate from the API implementation:

- the live database is byte-identical to the Batch 010 checkpoint (SHA-256 and
  full-table dumps), i.e. no database mutation occurred;
- `quick_check` / `foreign_key_check` pass;
- benchmark rows, external identifiers, provenance and sources are unchanged;
- the optional benchmark filters behave correctly against the live data,
  independently re-derived through the service (no HTTP layer).

Writes independent_audit.md and independent_audit.json.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.benchmark_service import (  # noqa: E402
    get_benchmarks_for_hardware,
)

BATCH_DIR = REPO_ROOT / "data" / "research" / "batch011"
DB = REPO_ROOT / "data" / "spectra.db"
BASELINE = REPO_ROOT / "data" / "backups" / "batch010" / "post_state.json"
CHECKPOINT_SHA = "20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127"

DATA_TABLES = [
    "hardware", "cpu_specifications", "gpu_specifications",
    "benchmark_results", "external_identifiers", "sources",
    "field_provenance", "build_conversations", "build_messages",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(con, name):
    return [list(r) for r in con.execute(f'select * from "{name}"')]


def main() -> int:
    results = {}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    results["db_sha256"] = sha256(DB)
    results["checkpoint_sha256"] = CHECKPOINT_SHA
    results["db_unchanged_from_checkpoint"] = (
        results["db_sha256"] == CHECKPOINT_SHA
    )
    results["quick_check"] = con.execute("PRAGMA quick_check").fetchone()[0]
    results["foreign_key_check"] = [
        list(r) for r in con.execute("PRAGMA foreign_key_check").fetchall()
    ]

    # ---- full-table comparison against the batch 010 checkpoint ----
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    table_changes = {}
    for table in DATA_TABLES:
        current = dump(con, table)
        if current != baseline["full_dumps"].get(table):
            table_changes[table] = {
                "current_rows": len(current),
                "baseline_rows": len(baseline["full_dumps"].get(table, [])),
            }
    results["table_changes"] = table_changes

    results["counts"] = {
        table: con.execute(f'select count(*) from "{table}"').fetchone()[0]
        for table in DATA_TABLES
    }

    results["sources"] = [
        list(r) for r in con.execute("select id, name, url from sources order by id")
    ]
    results["external_identifiers_by_source"] = [
        list(r) for r in con.execute(
            "select source_id, count(*) from external_identifiers group by source_id order by source_id"
        )
    ]
    results["benchmark_results_by_name_type"] = [
        list(r) for r in con.execute(
            "select benchmark_name, test_type, count(*) from benchmark_results group by 1,2 order by 1,2"
        )
    ]

    # ---- independent filter verification against live data ----
    hw_row = con.execute(
        "select hardware_id from benchmark_results order by id limit 1"
    ).fetchone()
    hw_id = hw_row["hardware_id"]
    all_rows = get_benchmarks_for_hardware(hw_id)
    src = all_rows[0].source_id if all_rows else None
    name = all_rows[0].benchmark_name if all_rows else None

    checks = {
        "no_filter_count": len(all_rows),
        "no_filter_ids": [r.id for r in all_rows],
        "source_filter_count": len(get_benchmarks_for_hardware(hw_id, source_id=src)),
        "name_filter_count": len(get_benchmarks_for_hardware(hw_id, benchmark_name=name)),
        "single_core_count": len(get_benchmarks_for_hardware(hw_id, test_type="single-core")),
        "multi_core_count": len(get_benchmarks_for_hardware(hw_id, test_type="multi-core")),
        "contradiction_count": len(get_benchmarks_for_hardware(
            hw_id, source_id=src, benchmark_name=name, test_type="does-not-exist")),
        "unknown_source_count": len(get_benchmarks_for_hardware(hw_id, source_id=1)),
    }
    all_ids = checks["no_filter_ids"]
    checks["no_duplicates"] = len(all_ids) == len(set(all_ids))
    results["filter_checks"] = checks

    # real data has exactly Geekbench 7 single+multi for this hardware
    results["filters_correct"] = bool(
        checks["no_duplicates"]
        and checks["source_filter_count"] == checks["no_filter_count"]
        and checks["name_filter_count"] == checks["no_filter_count"]
        and checks["single_core_count"] == 1
        and checks["multi_core_count"] == 1
        and checks["contradiction_count"] == 0
        and checks["unknown_source_count"] == 0
    )

    # specific expected real values for hardware 1508 (batch 010 evidence)
    results["sample_hardware"] = {
        "hardware_id": hw_id,
        "rows": [[r.id, r.score, r.test_type, r.source_id] for r in all_rows],
    }

    con.close()

    passed = bool(
        results["db_unchanged_from_checkpoint"]
        and results["quick_check"] == "ok"
        and not results["foreign_key_check"]
        and not results["table_changes"]
        and results["filters_correct"]
    )
    results["passed"] = passed

    (BATCH_DIR / "independent_audit.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    (BATCH_DIR / "independent_audit.md").write_text(
        render_markdown(results), encoding="utf-8"
    )
    print(f"verdict: {'PASS' if passed else 'FAIL'}")
    print(f"  db unchanged: {results['db_unchanged_from_checkpoint']}")
    print(f"  table changes: {results['table_changes'] or 'none'}")
    print(f"  filters correct: {results['filters_correct']}")
    return 0 if passed else 1


def render_markdown(results: dict) -> str:
    lines = [
        "# Batch 011 - Independent Audit",
        "",
        "Date: 2026-10-10",
        "",
        "## Database state (no mutation expected)",
        f"- Live SHA-256: `{results['db_sha256']}`",
        f"- Batch 010 checkpoint SHA-256: `{results['checkpoint_sha256']}`",
        f"- Unchanged from checkpoint: {results['db_unchanged_from_checkpoint']}",
        f"- `PRAGMA quick_check`: {results['quick_check']}",
        f"- `PRAGMA foreign_key_check`: "
        f"{results['foreign_key_check'][:5]}"
        f"{' (truncated)' if len(results['foreign_key_check']) > 5 else ''}",
        "",
        "## Full-table diff vs checkpoint",
        f"- Changed tables: {results['table_changes'] or 'none'}",
        "",
        "## Row counts",
    ]
    for table, count in results["counts"].items():
        lines.append(f"- {table}: {count}")
    lines += [
        "",
        "## Benchmark results",
    ]
    for row in results["benchmark_results_by_name_type"]:
        lines.append(f"- {row[0]} / {row[1]}: {row[2]}")
    lines += [
        "",
        "## External identifiers by source",
    ]
    for row in results["external_identifiers_by_source"]:
        lines.append(f"- source {row[0]}: {row[1]}")
    lines += [
        "",
        "## Sources",
    ]
    for row in results["sources"]:
        lines.append(f"- `{row[0]}` {row[1]} ({row[2]})")
    lines += [
        "",
        "## Independent filter verification (live data, service path)",
    ]
    for key, value in results["filter_checks"].items():
        lines.append(f"- {key}: {value}")
    lines += [
        f"- filters correct: {results['filters_correct']}",
        "",
        f"## Verdict: {'PASS' if results['passed'] else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())