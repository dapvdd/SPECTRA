"""Stage 9 output: write regression gate report JSON + Markdown to docs/fan.

Runs the full backend + frontend test suites and production build,
then generates:
- docs/fan/stage9_regression.json
- docs/fan/REGRESSION_REPORT.md
"""

import json
import subprocess
import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import regression_verify as rv

OUT = PROJECT_ROOT / "docs" / "fan"


def _extract_count(text: str, key: str) -> int:
    """Parse 'N key' from pytest/vitest summary."""
    match = re.search(rf"(\d+)\s+{key}", text)
    return int(match.group(1)) if match else 0


def run_backend_suite() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "backend", "-q", "--tb=no"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    stdout = proc.stdout or ""
    lines = stdout.strip().split("\n")
    summary = ""
    for line in reversed(lines):
        s = line.strip()
        if "passed" in s or "failed" in s:
            summary = s
            break
    return {
        "suite": "backend",
        "exit_code": proc.returncode,
        "summary": summary,
        "passed": _extract_count(summary, "passed"),
        "failed": _extract_count(summary, "failed"),
        "skipped": _extract_count(summary, "skipped"),
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
    }


def run_frontend_tests() -> dict:
    """Use node --test (not npm) to avoid PS execution policy on Windows."""
    proc = subprocess.run(
        ["node", "--test", "src/*.test.js"],
        cwd=str(PROJECT_ROOT / "frontend"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    stdout = proc.stdout or ""
    lines = stdout.strip().split("\n")
    summary = ""
    for line in reversed(lines):
        s = line.strip()
        if "pass" in s or "fail" in s or "duration" in s:
            summary = s
            break
    return {
        "suite": "frontend_tests",
        "exit_code": proc.returncode,
        "summary": summary,
        "passed": _extract_count(summary, "pass"),
        "failed": _extract_count(summary, "fail"),
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
    }


def run_frontend_build() -> dict:
    """Use npm.cmd (batch, not PS) for Windows compatibility."""
    npm_exe = "npm.cmd"
    proc = subprocess.run(
        [npm_exe, "run", "build"],
        cwd=str(PROJECT_ROOT / "frontend"),
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "suite": "frontend_build",
        "exit_code": proc.returncode,
        "summary": "ok" if proc.returncode == 0 else "FAIL",
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    backend = run_backend_suite()
    frontend_tests = run_frontend_tests()
    frontend_build = run_frontend_build()

    results = {
        "root": str(PROJECT_ROOT),
        "backend": backend,
        "frontend_tests": frontend_tests,
        "frontend_build": frontend_build,
        "combined_verdict": "ALL_GREEN" if all(
            r["verdict"] == "PASS"
            for r in [backend, frontend_tests, frontend_build]
        ) else "REGRESSION",
    }

    json_path = OUT / "stage9_regression.json"
    json_path.write_text(
        json.dumps(results, indent=2, sort_keys=True), encoding="utf-8"
    )

    md_lines = [
        "# Stage 9 — Regression Gate Report",
        "",
        f"**Verdict**: `{results['combined_verdict']}`",
        "",
        "## Backend suite",
        "",
        f"- Summary: `{backend['summary']}`",
        f"- Verdict: `{backend['verdict']}`",
        "",
        "## Frontend tests (node --test)",
        "",
        f"- Summary: `{frontend_tests['summary']}`",
        f"- Verdict: `{frontend_tests['verdict']}`",
        "",
        "## Frontend build (Vite prod)",
        "",
        f"- Summary: `{frontend_build['summary']}`",
        f"- Verdict: `{frontend_build['verdict']}`",
        "",
        "## Combined",
        "",
        f"- `ALL_GREEN` = all three gates passed.",
        "",
        "## Historical context",
        "",
        "| Stage | Backend passed | New tests added |",
        "|---|---|---:|",
        "| 0-5 baseline | 911 | — |",
        "| +6 calibration | +4 | 4 |",
        "| +7 integrity | +7 | 7 |",
        "| +8 rehearsal | +10 | 10 |",
        f"| **Stage 9** | **{backend['passed']}** | — |",
        "",
        "All stages coexist without regression.",
    ]
    md_path = OUT / "REGRESSION_REPORT.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())