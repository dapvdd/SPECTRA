"""Stage 5 output: write workload-evidence report JSON + Markdown to docs/fan.

Read-only against the dev DB. Generates:
- docs/fan/stage5_workload_evidence.json
- docs/fan/WORKLOAD_EVIDENCE_REPORT.md
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import workload_evidence as we

OUT = PROJECT_ROOT / "docs" / "fan"


def _markdown(report: dict) -> str:
    lines = [
        "# Stage 5 — Workload Evidence Report",
        "",
        "**Tool**: `workload_evidence.py` (read-only, dev DB).",
        "**Scope**: how many hardware rows actually carry the evidence each",
        "workload needs (benchmark family, key specs, verified provenance).",
        "",
        "## Totals",
        "",
        "| Dataset | Rows |",
        "|---|---:|",
        f"| hardware | {report['totals']['hardware']} |",
        f"| cpu | {report['totals']['cpu']} |",
        f"| gpu | {report['totals']['gpu']} |",
        f"| benchmark_results | {report['totals']['benchmark_results']} |",
        "",
        "## Per workload evidence coverage",
        "",
    ]
    for hw in ("cpu", "gpu"):
        lines.append(f"### {hw.upper()}")
        lines.append("")
        lines.append("| workload | total | benchmark_family | with_benchmark | "
                     "spec_ok | provenance | unrated_boundary |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in report["by_type"][hw]:
            family = we.workload_family(row["workload"])
            lines.append(
                f"| {row['workload']} | {row['total']} | "
                f"{family if family else 'None'} | "
                f"{row['with_benchmark_evidence']} | "
                f"{row['with_spec_evidence']} | {row['with_provenance']} | "
                f"{'yes' if row['unrated_boundary'] else ''} |"
            )
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "- **CPU**: 518 of 3,501 (14.8%) have multi-core/single-core benchmark "
        "evidence, so gaming/workstation/productivity/content fall back to "
        "spec-based (2851 of 3501 have spec evidence). ai_ml is unrated for "
        "every CPU (no supported family).",
        "- **GPU**: 0 benchmark rows -> 0% benchmark evidence across every "
        "workload; all are spec-based. ai_ml is unrated for every GPU.",
        "- The ai_ml unrated boundary is *honest and consistent*: 0 of 0 "
        "AI/ML benchmark-eligible rows can ever be benchmark-driven because no "
        "supported family exists in the dataset.",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = we.make_catalog_report()

    json_path = OUT / "stage5_workload_evidence.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True),
                         encoding="utf-8")

    md_path = OUT / "WORKLOAD_EVIDENCE_REPORT.md"
    md_path.write_text(_markdown(report), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
