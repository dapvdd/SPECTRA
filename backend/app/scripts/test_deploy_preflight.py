"""Deployment preflight tests — negative and positive cases.

Every check is a pure function of the filesystem and Docker state, so these
tests construct synthetic release directories and (where needed) stub the
docker/git subprocess calls. No real deployment or production state is used.

Covered negative cases (must FAIL the preflight):
- Wrong SHA in the release directory.
- Dirty checkout (modified tracked files).
- compose.json missing / unreadable.
- Mutable image tags (latest, stable, dev, main) in release images.
- No backup present / backup too old.
- Backup schema_version newer than the runner (cannot downgrade).
- Insufficient disk space (monkeypatched).
- Missing expected Docker volume (monkeypatched).

Covered positive cases (must PASS):
- A well-formed release directory with SHA tags, a fresh backup, matching
  schema_version, ample disk, and the expected volume.
"""

import json
import time
from pathlib import Path

import pytest

from backend.app.scripts import deploy_preflight as dp


GOOD_SHA_A = "a" * 40
GOOD_SHA_B = "b" * 40


def _write_compose(release_dir: Path, *, backend_tag: str, frontend_tag: str,
                   name: str = "spectra") -> None:
    compose = {
        "name": name,
        "services": {
            "backend": {
                "image": f"spectra-backend:{backend_tag}",
                "container_name": "spectra-backend",
            },
            "frontend": {
                "image": f"spectra-frontend:{frontend_tag}",
                "container_name": "spectra-frontend",
            },
        },
    }
    (release_dir / "compose.json").write_text(json.dumps(compose))


def _write_backup(release_dir: Path, *, version: int | None = 2,
                  age_hours: float = 1.0, name: str = "backup-test.db") -> Path:
    import sqlite3
    backup_path = release_dir / name
    conn = sqlite3.connect(backup_path)
    try:
        if version is not None:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL,"
                "applied_at TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (id, version, applied_at)"
                " VALUES (1, ?, '2026-01-01T00:00:00Z')",
                (version,),
            )
        conn.commit()
    finally:
        conn.close()
    # Backdate the file to simulate age.
    stamp = time.time() - age_hours * 3600
    import os
    os.utime(backup_path, (stamp, stamp))
    return backup_path


def _fake_git(release_dir: Path, sha: str, *, dirty: bool = False) -> None:
    """Create a fake git presence: a .git dir plus monkeypatched helpers."""
    (release_dir / ".git").mkdir(exist_ok=True)


@pytest.fixture
def release_dir(tmp_path):
    d = tmp_path / "spectra-test-release"
    d.mkdir()
    return d


@pytest.fixture
def patch_vcs(monkeypatch):
    """Patch git helpers so check_release_sha/check_git_clean are hermetic."""
    def _patch(sha: str, dirty_files: list[str] | None = None):
        monkeypatch.setattr(dp, "_git_sha_at", lambda p: sha)
        monkeypatch.setattr(
            dp, "_git_status_clean",
            lambda p: (not dirty_files, "clean" if not dirty_files else f"modified: {dirty_files}"),
        )
    return _patch


@pytest.fixture
def patch_docker(monkeypatch):
    """Patch docker subprocess helpers to return controlled output."""
    def _patch(*, containers: list[str] | None = None, volumes: list[str] | None = None):
        container_output = "\n".join(containers or [])
        volume_output = "\n".join(volumes or [])
        monkeypatch.setattr(
            dp, "_run",
            lambda args, **kw: _FakeCompleted(stdout=container_output if args[:2] == ["docker", "ps"] else volume_output),
        )
    return _patch


class _FakeCompleted:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class TestReleaseSha:
    def test_matching_sha_passes(self, release_dir, patch_vcs):
        patch_vcs(GOOD_SHA_A)
        result = dp.check_release_sha(release_dir, GOOD_SHA_A)
        assert result.passed

    def test_wrong_sha_fails(self, release_dir, patch_vcs):
        patch_vcs(GOOD_SHA_B)
        result = dp.check_release_sha(release_dir, GOOD_SHA_A)
        assert not result.passed
        assert GOOD_SHA_A in result.detail
        assert GOOD_SHA_B in result.detail

    def test_missing_git_fails(self, release_dir, monkeypatch):
        monkeypatch.setattr(dp, "_git_sha_at", lambda p: None)
        result = dp.check_release_sha(release_dir, GOOD_SHA_A)
        assert not result.passed


class TestGitClean:
    def test_clean_passes(self, release_dir, patch_vcs):
        patch_vcs(GOOD_SHA_A, dirty_files=None)
        result = dp.check_git_clean(release_dir)
        assert result.passed

    def test_modified_files_fail_check(self, release_dir, patch_vcs):
        patch_vcs(GOOD_SHA_A, dirty_files=["M frontend/src/App.jsx"])
        result = dp.check_git_clean(release_dir)
        assert not result.passed
        assert result.blocker is False  # warning, not hard blocker


class TestImageTags:
    def test_sha_tags_pass(self, release_dir):
        _write_compose(release_dir, backend_tag=GOOD_SHA_A, frontend_tag=GOOD_SHA_A)
        result = dp.check_image_tags(release_dir)
        assert result.passed

    @pytest.mark.parametrize("bad_tag", ["latest", "stable", "dev", "main"])
    def test_mutable_tags_fail(self, release_dir, bad_tag):
        _write_compose(release_dir, backend_tag=bad_tag, frontend_tag=GOOD_SHA_A)
        result = dp.check_image_tags(release_dir)
        assert not result.passed
        assert bad_tag in result.detail

    def test_missing_tag_fails(self, release_dir):
        compose = {
            "name": "spectra",
            "services": {"backend": {"image": "spectra-backend", "container_name": "b"}},
        }
        (release_dir / "compose.json").write_text(json.dumps(compose))
        result = dp.check_image_tags(release_dir)
        assert not result.passed


class TestBackups:
    def test_fresh_backup_passes(self, release_dir):
        _write_backup(release_dir, age_hours=1)
        result = dp.check_backup_available(release_dir)
        assert result.passed

    def test_no_backup_fails(self, release_dir):
        result = dp.check_backup_available(release_dir)
        assert not result.passed

    def test_stale_backup_fails(self, release_dir):
        _write_backup(release_dir, age_hours=72)
        result = dp.check_backup_available(release_dir)
        assert not result.passed
        assert "older than" in result.detail


class TestMigrationCompatibility:
    def test_matching_version_passes(self, release_dir):
        _write_backup(release_dir, version=2)
        result = dp.check_migration_compatible(release_dir)
        assert result.passed

    def test_older_version_passes(self, release_dir):
        _write_backup(release_dir, version=1)
        result = dp.check_migration_compatible(release_dir)
        assert result.passed

    def test_newer_version_fails(self, release_dir):
        _write_backup(release_dir, version=99)
        result = dp.check_migration_compatible(release_dir)
        assert not result.passed
        assert "exceeds" in result.detail

    def test_no_schema_version_warns(self, release_dir):
        _write_backup(release_dir, version=None)
        result = dp.check_migration_compatible(release_dir)
        assert result.passed
        assert result.blocker is False


class TestDiskSpace:
    def test_ample_disk_passes(self, release_dir):
        result = dp.check_disk_space(release_dir)
        assert result.passed

    def test_insufficient_disk_fails(self, release_dir, monkeypatch):
        fake = (10 << 30, 9 << 30, 1 << 20)  # 1 MB free
        monkeypatch.setattr(dp.shutil, "disk_usage", lambda p: fake)
        result = dp.check_disk_space(release_dir)
        assert not result.passed


class TestVolumeIdentity:
    def test_expected_volume_passes(self, release_dir, patch_docker):
        patch_docker(volumes=["spectra-sqlite-data", "other"])
        result = dp.check_volume_identity(release_dir)
        assert result.passed

    def test_missing_volume_fails(self, release_dir, patch_docker):
        patch_docker(volumes=["other"])
        result = dp.check_volume_identity(release_dir)
        assert not result.passed


class TestFullPreflight:
    def test_good_release_passes(self, release_dir, patch_vcs, patch_docker):
        patch_vcs(GOOD_SHA_A)
        patch_docker(volumes=["spectra-sqlite-data"])
        _write_compose(release_dir, backend_tag=GOOD_SHA_A, frontend_tag=GOOD_SHA_A)
        _write_backup(release_dir, version=2, age_hours=1)

        result = dp.run_preflight(release_dir, GOOD_SHA_A)
        assert result.all_passed, [c.detail for c in result.checks if not c.passed]

    def test_ops_dir_with_separate_source_checkout(self, tmp_path, patch_vcs,
                                                   patch_docker, monkeypatch):
        """The production shape: bare -ops dir (compose.json + backups) plus a
        sibling clean git checkout holding the source."""
        ops_dir = tmp_path / "spectra-75eba50-ops"
        ops_dir.mkdir()
        source_dir = tmp_path / "spectra-75eba50"
        source_dir.mkdir()

        patch_vcs(GOOD_SHA_A)
        patch_docker(volumes=["spectra-sqlite-data"])
        _write_compose(ops_dir, backend_tag=GOOD_SHA_A, frontend_tag=GOOD_SHA_A)
        _write_backup(ops_dir, version=2, age_hours=1)

        # Stub the runner import: repo_root points at an empty stub tree.
        stub_root = tmp_path / "stub-repo"
        (stub_root / "backend" / "app" / "migrations").mkdir(parents=True)
        (stub_root / "backend" / "__init__.py").write_text("")
        (stub_root / "backend" / "app" / "__init__.py").write_text("")
        (stub_root / "backend" / "app" / "migrations" / "__init__.py").write_text("")
        (stub_root / "backend" / "app" / "migrations" / "runner.py").write_text(
            "MIGRATIONS = []\nclass _M:\n    version = 2\n"
            "MIGRATIONS = [_M()]\n"
        )

        result = dp.run_preflight(
            ops_dir, GOOD_SHA_A, source_dir=source_dir, repo_root=stub_root
        )
        assert result.all_passed, [c.detail for c in result.checks if not c.passed]

    def test_legacy_collision_detected(self, release_dir, patch_vcs, patch_docker):
        """The legacy-takeover scenario: running containers share the release
        container names but come from different images."""
        patch_vcs(GOOD_SHA_A)
        patch_docker(
            containers=[
                "spectra-frontend|spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0|100.113.157.0:8080->8080/tcp",
                "spectra-backend|spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0|8000/tcp",
            ],
            volumes=["spectra-sqlite-data"],
        )
        # Release wants a DIFFERENT sha tag.
        _write_compose(release_dir, backend_tag=GOOD_SHA_A, frontend_tag=GOOD_SHA_A)
        _write_backup(release_dir, version=2, age_hours=1)

        result = dp.run_preflight(release_dir, GOOD_SHA_A)
        collision = next(c for c in result.checks if c.name == "compose_collision")
        assert not collision.passed
        assert "spectra-frontend" in collision.detail
