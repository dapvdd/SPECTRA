"""Stage 6 output: write calibration-verification report JSON + Markdown to docs/fan.

Read-only against the dev DB. Generates:
- docs/fan/stage6_calibration.json
- docs/fan/CALIBRATION_REPORT.md
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import calibration_verify as cv

OUT = PROJECT_ROOT / "docs" / "fan"


def _markdown(report: dict) -> str:
    lines = [
        "# Stage 6 — Calibration Verification Report",
        "",
        "**Tool**: `calibration_verify.py` (read-only, dev DB).",
        f"**Dev DB**: `{report['target']}`",
        "",
        "**Purpose**: verify that the suitability star anchors hard-coded in "
        "`suitability_service.py` match the actual percentile distribution of "
        "the benchmarked (Geekbench 7) population. Drift is *reported*, never "
        "silently rewritten.",
        "",
        "## Families",
        "",
        "| Family | Status | Max % err | Documented anchors (p10→p90) | Observed (p10→p90) |",
        "|---|---|---:|---|---|",
    ]
    for family, entry in report["families"].items():
        documented = ", ".join(f"{v:g}" for v in entry["documented"])
        observed = ", ".join(
            f"{v:g}" if v is not None else "—" for v in entry["observed"]
        )
        status = entry["status"]
        err = f"{entry['max_pct_err']:g}%" if entry["max_pct_err"] is not None else "—"
        lines.append(
            f"| {family} | {status} | {err} | {documented} | {observed} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Anchors are the p10/p30/p50/p70/p90 score boundaries of the "
        "Geekbench 7 population, mapped to stars 1–5 in "
        "`docs/SCORING_METHODOLOGY.md`.",
        "- `ok` means the documented anchors sit within 10% of the observed "
        "percentiles (no methodology change warranted).",
        "- `drift` means the observed population moved away from the documented "
        "anchors — an honest signal that star boundaries may need review; it is "
        "never auto-corrected.",
        "- This stage changes **no** scoring code: it is a verification/report "
        "pass only.",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = cv.calibration_report()

    json_path = OUT / "stage6_calibration.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    md_path = OUT / "CALIBRATION_REPORT.md"
    md_path.write_text(_markdown(report), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())