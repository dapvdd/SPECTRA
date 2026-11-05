"""Stage 9 — full regression gate for stages 6–8.

Runs the complete backend and frontend test suites against the current branch
and returns a deterministic verdict dict. All stages' scripts must coexist
without breaking the existing suite.

Contract:
- ``run_backend_suite(repo_root)`` -> dict with exit_code, stdout excerpt,
  failed count, passed count, and a deterministic pass/fail verdict.
- ``run_frontend_suite(repo_root)`` -> same structure for the frontend suite.
- ``full_gate(repo_root)`` -> combined verdict dict with per-suite results.
- Never modifies source files; runs tests as a subprocess observer only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT: Path | None = None


def project_root() -> Path:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    return _PROJECT_ROOT


def _run_pytest(args: list[str], cwd: Path) -> dict:
    """Run pytest with arguments; return structured result dict."""
    cmd = [sys.executable, "-m", "pytest", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=300,
    )
    # Parse output for summary line.
    stdout = proc.stdout or ""
    lines = stdout.strip().split("\n")
    # Look for "X passed" / "X failed" summary.
    summary = ""
    for line in reversed(lines):
        stripped = line.strip()
        if "passed" in stripped or "failed" in stripped or "error" in stripped:
            summary = stripped
            break
    return {
        "exit_code": proc.returncode,
        "summary": summary,
        "passed": _extract_count(summary, "passed"),
        "failed": _extract_count(summary, "failed"),
        "error": _extract_count(summary, "error"),
        "skipped": _extract_count(summary, "skipped"),
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
    }


def _extract_count(text: str, key: str) -> int:
    """Extract integer count for 'N key' from text like '911 passed, 2 skipped'."""
    import re
    match = re.search(rf"(\d+)\s+{key}", text)
    return int(match.group(1)) if match else 0


def run_backend_suite(repo_root: Path | None = None) -> dict:
    """Run the full backend pytest suite; return structured result."""
    root = repo_root or project_root()
    result = _run_pytest(["backend", "-q", "--tb=no"], root)
    result["suite"] = "backend"
    result["root"] = str(root)
    return result


def run_frontend_suite(repo_root: Path | None = None) -> dict:
    """Run the full frontend vitest suite; return structured result."""
    root = repo_root or project_root()
    frontend_dir = root / "frontend"

    # Try vitest with node_modules first, then npx.
    node_modules_bin = frontend_dir / "node_modules" / ".bin"
    vitest_exe = node_modules_bin / "vitest"
    if vitest_exe.exists():
        cmd = [str(vitest_exe), "run", "--reporter=verbose", "--env=jsdom"]
    else:
        cmd = ["npx", "vitest", "run", "--reporter=verbose", "--env=jsdom"]

    proc = subprocess.run(
        cmd,
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=300,
        shell=False,
    )
    stdout = proc.stdout or ""
    lines = stdout.strip().split("\n")
    summary = ""
    for line in reversed(lines):
        stripped = line.strip()
        if "passed" in stripped or "failed" in stripped or "total" in stripped:
            summary = stripped
            break
    return {
        "exit_code": proc.returncode,
        "summary": summary,
        "passed": _extract_count(summary, "passed"),
        "failed": _extract_count(summary, "failed"),
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
        "suite": "frontend",
        "root": str(frontend_dir),
    }


def run_build(repo_root: Path | None = None) -> dict:
    """Run Vite production build; return structured result."""
    root = repo_root or project_root()
    frontend_dir = root / "frontend"

    # Check npm is available.
    npm_exe = "npm.cmd" if sys.platform == "win32" else "npm"
    proc = subprocess.run(
        [npm_exe, "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "exit_code": proc.returncode,
        "summary": "build " + ("ok" if proc.returncode == 0 else "FAIL"),
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
        "suite": "frontend_build",
    }


def full_gate(repo_root: Path | None = None) -> dict:
    """Run all regression gates; return combined verdict dict."""
    root = repo_root or project_root()
    backend = run_backend_suite(root)
    frontend = run_frontend_suite(root)
    build = run_build(root)

    all_pass = all(r["verdict"] == "PASS" for r in [backend, frontend, build])

    return {
        "root": str(root),
        "backend": backend,
        "frontend": frontend,
        "frontend_build": build,
        "combined_verdict": "ALL_GREEN" if all_pass else "REGRESSION_DETECTED",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=str(project_root()),
        help="Repo root (default: auto-detected).",
    )
    parser.add_argument(
        "--suite",
        choices=["backend", "frontend", "build", "all"],
        default="all",
        help="Which suite to run.",
    )
    args = parser.parse_args()
    root = Path(args.repo)

    if args.suite == "backend":
        result = run_backend_suite(root)
    elif args.suite == "frontend":
        result = run_frontend_suite(root)
    elif args.suite == "build":
        result = run_build(root)
    else:
        result = full_gate(root)

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("combined_verdict", result.get("verdict")) in (
        "ALL_GREEN", "PASS"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())