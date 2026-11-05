"""Stage 4 output: write coverage report JSON + Markdown to docs/fan.

Read-only against the dev DB. Generates:
- docs/fan/stage4_coverage_verification.json
- docs/fan/COVERAGE_VERIFICATION_REPORT.md
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import coverage_verification as cv

OUT_DIR = PROJECT_ROOT / "docs" / "fan"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = cv.build_report()

    json_path = OUT_DIR / "stage4_coverage_verification.json"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# Stage 4 — CPU/GPU Coverage Verification Report",
        "",
        "**Tool**: `coverage_verification.py` (read-only, dev DB).",
        f"**Dev DB**: `{report['target']}`",
        "",
        "## Totals",
        "",
        "| Dataset | Rows |",
        "|---|---:|",
    ]
    for key in ("hardware", "cpu", "gpu", "cpu_specifications",
                "gpu_specifications", "benchmark_results"):
        lines.append(f"| {key} | {report['totals'][key]} |")

    lines += ["", "## Gap feasibility (fillable by a clear-licensed source?)", ""]
    for table in ("cpu_specifications", "gpu_specifications"):
        lines.append(f"### `{table}`")
        lines += ["", "| Field | Missing | Fillable | Reason |", "|---|---|---:|---|"]
        for entry in report["feasibility"][table]:
            lines.append(
                f"| {entry['field']} | {entry['missing']} | "
                f"{'yes' if entry['fillable'] else 'no'} | {entry['reason']} |"
            )
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "- GPU gaps (`boost_clock_mhz`, `tdp_w`, `memory_gb`) are **fillable** by "
        "the clear-licensed GPU Ark adapter, but Batch 018 already applied the "
        "non-NULL GPU Ark values; remaining NULLs are rows where GPU Ark itself "
        "has no value (ark_null) — verified by `data/research/batch017/`. "
        "So current GPU NULLs are honest gaps, not recoverable from a clear source "
        "we already hold.",
        "- CPU gaps are **blocked on license**: every candidate CPU spec source "
        "(Intel ARK, AMD CSV, Geekbench) is unknown/restricted, so none can feed "
        "the published catalog until re-approved.",
        "",
    ]
    (OUT_DIR / "COVERAGE_VERIFICATION_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(f"wrote {json_path}")
    print(f"wrote {OUT_DIR / 'COVERAGE_VERIFICATION_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
