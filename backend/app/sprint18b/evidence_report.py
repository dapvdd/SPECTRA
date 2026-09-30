"""Evidence report generator for Sprint 18B.

Produces a structured report of classification results with evidence
for each decision.
"""

import json
from collections import Counter
from datetime import datetime, timezone

from backend.app.sprint18b.classifier import Classification, classify_hardware
from backend.app.sprint18b.normalizer import normalize_sample
from backend.app.sprint18b.sample_data import SAMPLE_CPUS, SAMPLE_GPUS


def generate_evidence_report() -> dict[str, object]:
    normalized_cpus, normalized_gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
    results = classify_hardware(normalized_cpus, normalized_gpus)

    classifications = Counter(r["classification"] for r in results)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "cpus": len(normalized_cpus),
            "gpus": len(normalized_gpus),
            "classifications": dict(classifications),
        },
        "results": results,
    }


def format_report(report: dict[str, object]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append("=" * 60)
    lines.append("Sprint 18B Evidence Report")
    lines.append("=" * 60)
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Total items: {summary['total']}")
    lines.append(f"  CPUs: {summary['cpus']}")
    lines.append(f"  GPUs: {summary['gpus']}")
    lines.append("  Classifications:")
    for cls, count in summary["classifications"].items():
        lines.append(f"    {cls}: {count}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("Details:")
    lines.append("-" * 60)

    for result in report["results"]:
        lines.append("")
        lines.append(
            f"[{result['classification']}] {result['manufacturer']} {result['name']} ({result['type']})"
        )
        reasons = result["reasons"]
        if reasons:
            for reason in reasons:
                lines.append(f"  - {reason}")
        else:
            lines.append("  - all required fields present and consistent")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def write_report(path: str) -> None:
    report = generate_evidence_report()
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_report(report))
        f.write("\n")
        f.write("\nJSON:\n")
        f.write(json.dumps(report, indent=2, default=str))
        f.write("\n")
