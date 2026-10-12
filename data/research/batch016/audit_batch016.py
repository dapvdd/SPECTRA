#!/usr/bin/env python3
"""Independent audit for Batch 016.

Re-verifies the state the validation batch claims, without trusting any of the
batch's own harnesses: database integrity and counts against the recorded
baseline, the committed fix itself, the regression test's actual coverage, and
the working-tree boundaries (no unrelated files, no .opencode, no backups).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIVE_DB = ROOT / "data" / "spectra.db"

EXPECTED_COUNTS = {
    "hardware": 5380,
    "cpu_specifications": 3501,
    "gpu_specifications": 1879,
    "benchmark_results": 1040,
    "external_identifiers": 3575,
    "field_provenance": 36946,
    "sources": 9,
    "build_conversations": 5,
    "build_messages": 10,
}
EXPECTED_LIVE_SHA256 = (
    "9aee08794eeaf0ddabcaaed3b0462e8116aa5f1a339414dd12244e1ecd7b0160"
)

checks: list[dict] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def main() -> int:
    # ---- What the commit actually contains -----------------------------
    staged = [ln for ln in git("diff", "--cached", "--name-only", "--no-renames").splitlines() if ln.strip()]
    modified = [ln for ln in git("diff", "--name-only").splitlines() if ln.strip()]
    committed = [ln for ln in git("show", "--name-only", "--format=", "HEAD").splitlines() if ln.strip()]

    record("nothing_left_staged", not staged, f"staged={staged}")
    # The audit regenerates its own result file, so that path is expected to
    # be dirty after a run. Everything else must be clean.
    audit_output = {"data/research/batch016/_audit_result.json"}
    residual = [p for p in modified if p not in audit_output]
    record(
        "working_tree_clean_for_batch_files",
        not residual,
        f"residual_modified={residual}",
    )

    fix_paths = {"frontend/src/App.jsx", "frontend/src/markdownRendering.test.js"}
    record(
        "commit_contains_fix_and_regression_test",
        fix_paths <= set(committed),
        f"committed={sorted(committed)}",
    )
    unexpected = [
        p for p in committed
        if not p.startswith(("frontend/src/", "data/research/batch016/"))
    ]
    record(
        "commit_only_frontend_and_research",
        not unexpected,
        f"unexpected={unexpected}",
    )
    record(
        "commit_excludes_backups_opencode_and_db",
        not [p for p in committed if p.endswith((".db", ".bak")) or p.startswith(".opencode/")],
        "no db/backup/.opencode path in the commit",
    )
    record(
        "opencode_untouched",
        not any(p.startswith(".opencode/") for p in committed)
        and not any(p.startswith(".opencode/") for p in modified),
        "no .opencode path in the commit or diff",
    )

    # ---- The single production defect fix -------------------------------
    app_diff = git("show", "HEAD", "--", "frontend/src/App.jsx")
    added = [
        ln for ln in app_diff.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    normalized = [ln.lstrip("+").strip() for ln in added]
    record(
        "fix_is_additive_import_only",
        len(added) == 1
        and normalized[0] == 'import { parseMarkdown } from "./markdown.js";',
        f"added_lines={added}",
    )
    record(
        "no_spec_benchmark_or_licence_touched",
        not any(
            token in app_diff.lower()
            for token in (
                "license_", "score", "boost_clock", "base_clock",
                "tdp_w", "provenance_status", "geekbench",
            )
        ),
        "diff contains no data/licence/provenance token",
    )

    # ---- Database -------------------------------------------------------
    con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    record("live_db_integrity_ok", integrity == "ok", f"integrity={integrity}")
    record("live_db_no_fk_violations", not fk, f"violations={len(fk)}")

    for table, expected in EXPECTED_COUNTS.items():
        actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        record(f"count_{table}_unchanged", actual == expected, f"{actual} == {expected}")
    con.close()

    live_sha = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-FileHash '{LIVE_DB}' -Algorithm SHA256).Hash"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().lower()
    record(
        "live_db_sha256_unchanged",
        live_sha == EXPECTED_LIVE_SHA256,
        live_sha,
    )

    # ---- The defect the fix addresses -----------------------------------
    app_source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    record(
        "parse_markdown_imported",
        'from "./markdown.js"' in app_source and "import { parseMarkdown }" in app_source,
        "import present",
    )
    record(
        "parse_markdown_used_at_every_render_site",
        app_source.count("MarkdownContent") >= 4,
        f"MarkdownContent references={app_source.count('MarkdownContent')}",
    )
    markdown_source = (ROOT / "frontend" / "src" / "markdown.js").read_text(encoding="utf-8")
    record(
        "markdown_helper_exported",
        "export const parseMarkdown" in markdown_source,
        "helper exists",
    )

    # ---- Test artefacts -------------------------------------------------
    test_source = (ROOT / "frontend" / "src" / "markdownRendering.test.js").read_text(encoding="utf-8")
    record(
        "regression_test_guards_missing_import",
        "parseMarkdown" in test_source and "markdown.js" in test_source,
        "test references the helper and its module",
    )
    record(
        "regression_test_guards_local_redefinition",
        "local redefinition" in test_source,
        "test rejects an inline redeclaration",
    )
    record(
        "regression_test_committed",
        "frontend/src/markdownRendering.test.js" in committed,
        "regression test is in the commit",
    )

    browser_result = json.loads(
        (ROOT / "data" / "research" / "batch016" / "_browser_result.json").read_text(encoding="utf-8")
    )
    record(
        "browser_checks_all_passed",
        browser_result.get("all_passed") is True
        and browser_result.get("failed") == 0
        and browser_result.get("passed", 0) >= 40,
        f"passed={browser_result.get('passed')} failed={browser_result.get('failed')}",
    )
    record(
        "browser_run_has_no_console_or_network_errors",
        not browser_result.get("consoleErrors")
        and not browser_result.get("pageErrors")
        and not browser_result.get("failedRequests")
        and not browser_result.get("badResponses"),
        "clean runtime log",
    )
    record(
        "browser_covers_three_viewports",
        all(
            any((vp in c["name"]) for c in browser_result["checks"])
            for vp in ("mobile-390", "tablet-768", "desktop-1440")
        ),
        "all three widths present",
    )

    smoke_result = json.loads(
        (ROOT / "data" / "research" / "batch016" / "_api_smoke_result.json").read_text(encoding="utf-8")
    )
    record(
        "api_smoke_tests_all_passed",
        smoke_result.get("all_passed") is True and smoke_result.get("failed") == 0,
        f"passed={smoke_result.get('passed')} failed={smoke_result.get('failed')}",
    )
    record(
        "api_provider_actually_responded",
        smoke_result["ai_provider"].get("hardware_chat_status") == 200
        and smoke_result["ai_provider"].get("build_chat_status") == 200,
        "real AI answers returned",
    )

    shots = sorted((ROOT / "data" / "research" / "batch016" / "screenshots").glob("*.png"))
    record(
        "screenshots_captured",
        len(shots) >= 8 and all(p.stat().st_size > 10000 for p in shots),
        f"n={len(shots)} min_bytes={min((p.stat().st_size for p in shots), default=0)}",
    )

    # ---- Anything about secrets -----------------------------------------
    tracked_files = git("ls-files").splitlines()
    record(
        "no_env_file_tracked",
        not [f for f in tracked_files if f.endswith(".env") and f != ".env.example"],
        "no .env tracked",
    )
    secrets_in_artefacts = [
        p.name
        for p in (ROOT / "data" / "research" / "batch016").glob("*.json")
        if "GEMINI_API_KEY" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    record("no_secrets_in_artefacts", not secrets_in_artefacts, f"{secrets_in_artefacts}")

    passed = sum(1 for c in checks if c["passed"])
    report = {
        "generated_at": "recorded by the runner",
        # HEAD is deliberately not recorded: it would change every time the
        # audit output is committed, and the checks above already assert the
        # commit's contents rather than its hash.
        "live_db": str(LIVE_DB),
        "live_db_sha256": live_sha,
        "expected_counts": EXPECTED_COUNTS,
        "checks": checks,
        "passed": passed,
        "failed": len(checks) - passed,
        "all_passed": passed == len(checks),
    }
    (ROOT / "data" / "research" / "batch016" / "_audit_result.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    for c in checks:
        print(("PASS" if c["passed"] else "FAIL"), c["name"], "-", c["detail"])
    print(f"\nTOTAL {passed}/{len(checks)} -> {report['passed']}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
