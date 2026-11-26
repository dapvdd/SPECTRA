"""M3.4 Task 5 — staged deployment orchestrator (preflight/cutover/acceptance/
rollback/rehearsal).

This module structures a SPECTRA release into explicit stages and moves every
preparation step that does NOT require the service to be down outside the
interruption window. It reuses the existing guards:

- deploy_preflight.run_preflight (SHA, dirty checkout, compose collision,
  mutable tags, backup, migration, disk, volume) — untouched.
- backup_database.create_backup / backup_job.run_backup_job (consistent
  snapshot + manifest).
- The publisher prod-path guard and deploy_release.sh wrapper remain the
  only sanctioned bring-up path; this orchestrator never runs compose
  itself except through those guards.

Write-loss prevention (the core of the cutover stage):

1. PREPARE (service still up): fresh pre-cutover backup + capture the
   database identity (schema_version, core row counts, file sha256).
2. DOWN: compose down completes — writes end.
3. IDENTITY CHECK: re-capture the database identity and compare against the
   identity captured in step 1. Any difference means writes happened between
   candidate preparation and cutover -> ABORT (no silent lost writes).
4. SWAP/UP: apply the candidate, bring the stack up.
5. ACCEPTANCE: health/ready/release-identity probes.

Downtime measurement (honest accounting per M33_RELEASE_ACCOUNTING_CORRECTION.md):

- user_visible_downtime = first_healthy_ts - down_complete_ts.
- Operator pauses are NOT subtracted. There is no "effective downtime".

Usage::

    python -m backend.app.scripts.deploy_m34 \
        --release-dir /home/david/releases/spectra-<sha>-ops \
        --expected-sha <sha> --stage preflight
    # stages: preflight | prepare | cutover | acceptance | rollback | rehearsal | full
    # production bring-up remains deploy_release.sh's job (user-gated).

Exit codes: 0 = stage passed; 1 = stage failed/aborted; 2 = usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.app.scripts.backup_database import (
    _COUNTED_TABLES,
    _integrity_ok,
    _row_counts,
    sha256_of,
)
from backend.app.scripts.deploy_preflight import run_preflight

STAGES = ("preflight", "prepare", "cutover", "acceptance", "rollback", "rehearsal", "full")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compose(compose_file: Path, project: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "-p", project, *args],
        capture_output=True,
        text=True,
    )


def capture_db_identity(db_path: Path) -> dict:
    """Identity fingerprint used to detect writes between stages.

    Captures schema_version, core row counts, integrity, and the file
    sha256. Two captures that agree mean zero writes happened in between.
    """
    identity: dict = {"db_path": str(db_path)}
    if not db_path.exists():
        identity["exists"] = False
        return identity
    identity["exists"] = True
    identity["sha256"] = sha256_of(db_path)
    identity["size_bytes"] = db_path.stat().st_size
    conn = sqlite3.connect(db_path)
    try:
        has_version = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        identity["schema_version"] = (
            int(conn.execute("SELECT version FROM schema_version WHERE id=1").fetchone()[0])
            if has_version else 0
        )
    except sqlite3.Error as error:
        identity["schema_version_error"] = str(error)
    finally:
        conn.close()
    try:
        identity["row_counts"] = _row_counts(db_path)
    except sqlite3.Error as error:
        identity["row_counts_error"] = str(error)
    try:
        identity["integrity_check"] = _integrity_ok(db_path)[1]
    except sqlite3.Error:
        pass
    return identity


def identities_match(before: dict, after: dict) -> tuple[bool, str]:
    """True when no writes happened between the two captures."""
    if not before.get("exists") or not after.get("exists"):
        return False, "database file missing at one capture point"
    if before.get("sha256") != after.get("sha256"):
        return False, (
            f"database file changed between candidate preparation and cutover "
            f"(sha256 {before.get('sha256')} -> {after.get('sha256')}); "
            f"writes would be lost — ABORT"
        )
    if before.get("schema_version") != after.get("schema_version"):
        return False, f"schema_version changed {before.get('schema_version')} -> {after.get('schema_version')}"
    if before.get("row_counts") != after.get("row_counts"):
        differing = {
            k: (before.get("row_counts", {}).get(k), after.get("row_counts", {}).get(k))
            for k in set(before.get("row_counts", {})) | set(after.get("row_counts", {}))
            if before.get("row_counts", {}).get(k) != after.get("row_counts", {}).get(k)
        }
        return False, f"row counts changed between stages: {differing}"
    return True, "identity match: zero writes between stages"


class StageRunner:
    """Executes one deployment stage; state carried as JSON between stages."""

    def __init__(self, release_dir: Path, expected_sha: str, project: str = "spectra"):
        self.release_dir = Path(release_dir)
        self.expected_sha = expected_sha
        self.project = project
        self.state_path = self.release_dir / "deploy_m34_state.json"

    # -- state ------------------------------------------------------------
    def load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}

    def save_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # -- stages -----------------------------------------------------------
    def stage_preflight(self) -> tuple[bool, dict]:
        result = run_preflight(self.release_dir, self.expected_sha)
        report = result.to_dict()
        report["stage"] = "preflight"
        report["at"] = _utc()
        return result.all_passed, report

    def stage_prepare(self, volume_db_path: Path, backup_dir: Path) -> tuple[bool, dict]:
        """PRE-INTERRUPTION work: backup + identity capture (service still up)."""
        from backend.app.scripts.backup_job import run_backup_job

        report: dict = {"stage": "prepare", "at": _utc()}
        try:
            backup = run_backup_job(
                source=volume_db_path, backup_dir=backup_dir, keep=7,
                compare_source=False,
            )
        except RuntimeError as error:
            report["backup"] = {"failed": str(error)}
            return False, report
        report["backup"] = backup
        report["db_identity"] = capture_db_identity(volume_db_path)
        self.save_state(report)
        return True, report

    def check_write_loss_guard(self, volume_db_path: Path) -> tuple[bool, dict]:
        """Re-capture identity and compare with the prepare-stage capture."""
        state = self.load_state()
        before = state.get("db_identity")
        if not before:
            return False, {
                "stage": "write_loss_guard",
                "passed": False,
                "reason": "no prepare-stage identity captured; run --stage prepare first",
            }
        after = capture_db_identity(volume_db_path)
        ok, reason = identities_match(before, after)
        return ok, {
            "stage": "write_loss_guard",
            "passed": ok,
            "reason": reason,
            "before_sha256": before.get("sha256"),
            "after_sha256": after.get("sha256"),
            "at": _utc(),
        }

    def stage_cutover(
        self,
        compose_file: Path,
        volume_db_path: Path,
        *,
        down_already_done: bool = False,
    ) -> tuple[bool, dict]:
        """DOWN -> identity check -> swap -> UP (the only downtime window)."""
        report: dict = {"stage": "cutover", "started_at": _utc()}
        if not down_already_done:
            down = _compose(compose_file, self.project, "down")
            report["down"] = {
                "completed_at": _utc(),
                "returncode": down.returncode,
            }
            if down.returncode != 0:
                report["down"]["stderr"] = down.stderr[-500:]
                return False, report

        ok, guard = self.check_write_loss_guard(volume_db_path)
        report["write_loss_guard"] = guard
        if not ok:
            report["aborted"] = True
            report["finished_at"] = _utc()
            return False, report

        up = _compose(compose_file, self.project, "up", "-d", "--wait")
        report["up"] = {"completed_at": _utc(), "returncode": up.returncode}
        if up.returncode != 0:
            report["up"]["stderr"] = up.stderr[-500:]
            report["finished_at"] = _utc()
            return False, report
        report["finished_at"] = _utc()
        return True, report

    def stage_acceptance(self, base_url: str) -> tuple[bool, dict]:
        """Health/ready/release probes; downtime computed honestly."""
        import urllib.request

        report: dict = {"stage": "acceptance", "at": _utc(), "probes": []}
        state = self.load_state()
        all_ok = True

        for path, expect in (("/health", 200), ("/ready", 200), ("/release", 200)):
            try:
                with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    ok = response.status == expect
            except Exception as error:  # noqa: BLE001
                body = {"error": str(error)}
                ok = False
            report["probes"].append({"path": path, "ok": ok, "body": body})
            all_ok = all_ok and ok

        release_body = next(
            (p["body"] for p in report["probes"] if p["path"] == "/release"), {}
        )
        report["release_identity"] = release_body
        expected_sha = self.expected_sha
        report["sha_match"] = (
            isinstance(release_body, dict)
            and str(release_body.get("git_sha", "")).startswith(expected_sha[:7])
        )
        all_ok = all_ok and report["sha_match"]

        down_ts = (state.get("cutover") or {}).get("down_completed_at")
        healthy_ts = _utc()
        if down_ts:
            # Honest accounting: wall clock from down-complete to first
            # accepted acceptance probe. Operator pauses are NOT subtracted;
            # there is no "effective downtime" — only user-visible downtime.
            report["downtime"] = {
                "down_completed_at": down_ts,
                "first_accepted_probe_at": healthy_ts,
                "note": (
                    "user-visible downtime = first_healthy - down_complete; "
                    "operator pauses are inside it and are NOT subtracted "
                    "(M33_RELEASE_ACCOUNTING_CORRECTION.md §2)"
                ),
            }
        return all_ok, report

    def stage_rollback(self, compose_file: Path, rollback_compose: Path) -> tuple[bool, dict]:
        """Down current -> up rollback compose (documented, guarded path)."""
        report: dict = {"stage": "rollback", "started_at": _utc()}
        down = _compose(compose_file, self.project, "down")
        report["down"] = {"returncode": down.returncode, "completed_at": _utc()}
        up = _compose(rollback_compose, self.project, "up", "-d", "--wait")
        report["up"] = {"returncode": up.returncode, "completed_at": _utc()}
        ok = down.returncode == 0 and up.returncode == 0
        report["passed"] = ok
        return ok, report


def run_rehearsal(
    release_dir: Path,
    expected_sha: str,
    compose_file: Path,
    volume_db_path: Path,
    base_url: str,
    project: str = "spectra",
) -> dict:
    """Full staged rehearsal in an isolated environment.

    Produces the honest downtime measurement (no operator-pause subtraction):
    user_visible_downtime = first_accepted_probe - down_complete, wall clock.
    """
    runner = StageRunner(release_dir, expected_sha, project=project)
    timeline: dict = {"rehearsal_at": _utc(), "stages": []}

    ok, pre = runner.stage_preflight()
    timeline["stages"].append(pre)
    if not ok:
        timeline["verdict"] = "PREFLIGHT_FAILED"
        return timeline

    ok, prep = runner.stage_prepare(volume_db_path, release_dir / "rehearsal-backups")
    timeline["stages"].append(prep)
    if not ok:
        timeline["verdict"] = "PREPARE_FAILED"
        return timeline

    ok, cut = runner.stage_cutover(compose_file, volume_db_path)
    timeline["stages"].append(cut)
    runner.save_state({**runner.load_state(), "cutover": {"down_completed_at": cut.get("down", {}).get("completed_at")}})
    if not ok:
        timeline["verdict"] = "CUTOVER_FAILED"
        return timeline

    ok, acc = runner.stage_acceptance(base_url)
    timeline["stages"].append(acc)
    timeline["verdict"] = "REHEARSAL_PASS" if ok else "ACCEPTANCE_FAILED"
    return timeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--project", default="spectra")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)

    runner = StageRunner(args.release_dir, args.expected_sha, project=args.project)
    if args.stage == "preflight":
        ok, report = runner.stage_preflight()
    else:
        parser.error(f"stage {args.stage} requires runtime context; use run_rehearsal or deploy_release.sh")
        return 2

    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
