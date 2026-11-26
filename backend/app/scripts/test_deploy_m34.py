"""M3.4 Task 5 — staged deployment orchestrator tests.

Pins the write-loss guard, the honest downtime accounting, and the
stage gating. Docker-dependent stages are exercised with the real code
paths but offline: _compose is monkeypatched; identity capture runs
against real temporary SQLite files.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from backend.app.scripts import deploy_m34
from backend.app.scripts.deploy_m34 import (
    StageRunner,
    capture_db_identity,
    identities_match,
    run_rehearsal,
)


def _make_db(path: Path, rows: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE hardware (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER)")
    conn.execute("INSERT INTO schema_version (id, version) VALUES (1, 4)")
    conn.executemany("INSERT INTO hardware (name) VALUES (?)", [(f"hw{i}",) for i in range(rows)])
    conn.commit()
    conn.close()
    return path


def _identity_with_sha(path: Path) -> dict:
    return capture_db_identity(path)


class TestDbIdentity:
    def test_identical_captures_match(self, tmp_path):
        db = _make_db(tmp_path / "spectra.db")
        first = _identity_with_sha(db)
        second = _identity_with_sha(db)
        ok, reason = identities_match(first, second)
        assert ok, reason
        assert second["schema_version"] == 4
        assert second["row_counts"]["hardware"] == 3

    def test_write_between_captures_detected(self, tmp_path):
        db = _make_db(tmp_path / "spectra.db")
        first = _identity_with_sha(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO hardware (name) VALUES ('late-write')")
        conn.commit()
        conn.close()
        second = _identity_with_sha(db)
        ok, reason = identities_match(first, second)
        assert not ok
        assert "ABORT" in reason or "changed" in reason

    def test_missing_file_fails_closed(self, tmp_path):
        ok, reason = identities_match(
            {"exists": False}, {"exists": False}
        )
        assert not ok


class TestWriteLossGuard:
    def test_guard_aborts_on_lost_writes(self, tmp_path, monkeypatch):
        release_dir = tmp_path / "release"
        release_dir.mkdir()
        runner = StageRunner(release_dir, "5c2c7d9a")
        db = _make_db(tmp_path / "spectra.db")

        ok, prep = runner.stage_prepare(db, tmp_path / "backups")
        assert ok
        assert prep["db_identity"]["sha256"]

        # A write lands between prepare and cutover (the lost-write hazard).
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO hardware (name) VALUES ('written-after-prepare')")
        conn.commit()
        conn.close()

        ok, guard = runner.check_write_loss_guard(db)
        assert not ok
        assert guard["reason"] and "changed" in guard["reason"].lower() or "ABORT" in guard["reason"]

        # Cutover must abort, not proceed to swap.
        monkeypatch.setattr(deploy_m34, "_compose", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
        ok, report = runner.stage_cutover(tmp_path / "compose.json", db)
        assert not ok
        assert report.get("aborted") is True
        # Down ran, but up never ran.
        assert "up" not in report or report.get("up") is None

    def test_guard_passes_when_no_writes(self, tmp_path):
        release_dir = tmp_path / "release"
        release_dir.mkdir()
        runner = StageRunner(release_dir, "5c2c7d9a")
        db = _make_db(tmp_path / "spectra.db")
        runner.stage_prepare(db, tmp_path / "backups")
        ok, guard = runner.check_write_loss_guard(db)
        assert ok
        assert guard["reason"] == "identity match: zero writes between stages"


class TestStageGating:
    def test_preflight_stage_reports_failures(self, tmp_path, monkeypatch):
        release_dir = tmp_path / "release"
        release_dir.mkdir()
        # A real (existing) directory with a wrong SHA must fail the stage
        # and report blockers — never crash (offline: docker compose checks
        # are preflight-internal; on a machine without docker they report
        # failure, which is the fail-closed behavior under test).
        runner = StageRunner(release_dir, "nonexistent-sha")
        ok, report = runner.stage_preflight()
        assert not ok
        assert report["stage"] == "preflight"
        assert report["blocker_count"] >= 1


class TestRehearsalAccounting:
    def test_downtime_measured_without_operator_pause_subtraction(self, tmp_path, monkeypatch):
        release_dir = tmp_path / "release"
        release_dir.mkdir()
        db = _make_db(tmp_path / "spectra.db")

        # Preflight would fail offline; patch it to pass for this rehearsal.
        class FakeResult:
            all_passed = True
            def to_dict(self):
                return {"all_passed": True, "checks": [], "blocker_count": 0}

        monkeypatch.setattr(
            deploy_m34, "run_preflight", lambda *a, **k: FakeResult()
        )
        # _compose: record timestamps; simulate a slow operator window by
        # making up take some wall time between down and up.
        calls = []

        def fake_compose(compose_file, project, *args):
            calls.append(args)
            if args[0] == "down":
                import time as _t
                _t.sleep(0.2)  # simulates operator verification pause
            return subprocess.CompletedProcess(args, 0, "", "")

        monkeypatch.setattr(deploy_m34, "_compose", fake_compose)

        # Acceptance probes: patched HTTP via urllib in stage_acceptance is
        # exercised through a local monkeypatched urlopen.
        class FakeResponse:
            status = 200
            def read(self):
                return json.dumps({"status": "healthy", "git_sha": "5c2c7d9a37109da99f20a34973503d1bd6deb236"}).encode()
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        import urllib.request
        monkeypatch.setattr(
            urllib.request, "urlopen", lambda url, timeout: FakeResponse()
        )

        timeline = run_rehearsal(
            release_dir=release_dir,
            expected_sha="5c2c7d9a37109da99f20a34973503d1bd6deb236",
            compose_file=tmp_path / "compose.json",
            volume_db_path=db,
            base_url="http://127.0.0.1:8080",
            project="spectra-rehearsal",
        )

        assert timeline["verdict"] == "REHEARSAL_PASS", timeline
        acceptance = next(s for s in timeline["stages"] if s.get("stage") == "acceptance")
        downtime = acceptance["downtime"]
        # Honest accounting fields present; no "effective downtime" field.
        assert "down_completed_at" in downtime
        assert "first_accepted_probe_at" in downtime
        assert "operator pauses are" in downtime["note"]
        assert "NOT subtracted" in downtime["note"]

    def test_rehearsal_aborts_on_preflight_failure(self, tmp_path, monkeypatch):
        release_dir = tmp_path / "release"
        release_dir.mkdir()

        class FakeResult:
            all_passed = False
            blocker_count = 2
            def to_dict(self):
                return {"all_passed": False, "checks": [], "blocker_count": 2}

        monkeypatch.setattr(deploy_m34, "run_preflight", lambda *a, **k: FakeResult())
        timeline = run_rehearsal(
            release_dir=release_dir,
            expected_sha="bad",
            compose_file=tmp_path / "compose.json",
            volume_db_path=tmp_path / "missing.db",
            base_url="http://127.0.0.1:8080",
        )
        assert timeline["verdict"] == "PREFLIGHT_FAILED"
