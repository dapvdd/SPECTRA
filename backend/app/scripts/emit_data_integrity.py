"""Stage 7 output: write data-integrity drill report JSON + Markdown to docs/fan.

Read-only against the dev DB. Generates:
- docs/fan/stage7_integrity.json
- docs/fan/DATA_INTEGRITY_REPORT.md
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import data_integrity_verify as div

OUT = PROJECT_ROOT / "docs" / "fan"


def _markdown(result: dict) -> str:
    lines = [
        "# Stage 7 — Data Integrity Drill Report",
        "",
        f"**Tool**: `data_integrity_verify.py` (read-only, dev DB).",
        f"**Target**: `{result['target']}`",
        "",
        f"**Verdict**: `{result['verdict']}`",
        "",
        "## Quick check",
        "",
        f"- `quick_check`: `{result['quick_check']}` "
        + ("✓ OK" if result["quick_check"] == "ok" else "✗ FAIL"),
        "",
        "## Referential integrity",
        "",
        f"- FK violations: `{result['foreign_key_check_violations']}` "
        + ("✓ 0 — PASS" if result["foreign_key_check_violations"] == 0
           else f"✗ {result['foreign_key_check_violations']} violations"),
        "",
        "## Row-count floors",
        "",
        "| Table | Rows | Minimum | Met? |",
        "|---|---|---:|---:|---|",
    ]
    for table, minimum in result["row_counts_minimum"].items():
        n = result["row_counts"].get(table, "—")
        met = result["min_met"].get(table, False)
        lines.append(f"| {table} | {n} | {minimum} | {'✓' if met else '✗'} |")
    lines += [
        "",
        "## Curated counts (mission-relevant tables)",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]
    for table, n in result["curated_counts"].items():
        lines.append(f"| {table} | {n} |")
    lines += [
        "",
        "## Schema presence",
        "",
        f"- Complete: `{'Yes' if result['schema_present']['complete'] else 'No'}`",
        f"- Tables: {', '.join(sorted(result['schema_present']['tables'])[:8])}...",
        "",
        "## Safety note",
        "",
        "This drill is **read-only**: the target file is never written. "
        "A `FileNotFoundError` is raised if the path does not exist — the drill "
        "refuses to create an empty database by connecting to a missing path.",
    ]
    return "\n".join(lines)


def main() -> int:
    dev_db = str(PROJECT_ROOT / "data" / "dev" / "spectra_dev.db")
    OUT.mkdir(parents=True, exist_ok=True)
    result = div.integrity_verdict(dev_db)

    json_path = OUT / "stage7_integrity.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str),
                         encoding="utf-8")

    md_path = OUT / "DATA_INTEGRITY_REPORT.md"
    md_path.write_text(_markdown(result), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())