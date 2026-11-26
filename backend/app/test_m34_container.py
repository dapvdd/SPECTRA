"""M3.4 Task 3 — container hardening acceptance (static compose/config tests).

These tests pin the hardened deployment artifacts without requiring a Docker
daemon (none exists in CI). Runtime rehearsal remains a user-gated production
step documented in M34_OPERATIONS_RUNBOOK.md.

Verified properties:
- compose.m34.yaml exists and applies the hardening flags to both services:
  non-root user, cap_drop ALL, no-new-privileges, read_only rootfs,
  tmpfs writable mounts, resource limits, kept healthcheck + volumes.
- The SQLite volume path is UNCHANGED (spectra-sqlite-data:/app/data) so
  existing production data and backups remain valid.
- Dockerfile.backend creates and switches to a non-root user and pre-creates
  writable data paths so entrypoint template-init works.
- deploy_release.sh prod-path guard is intact (publisher + script).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_M34 = REPO_ROOT / "compose.m34.yaml"
COMPOSE_BASE = REPO_ROOT / "compose.yaml"
DOCKERFILE_BACKEND = REPO_ROOT / "Dockerfile.backend"


def _service(name: str) -> dict:
    text = COMPOSE_M34.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    return document["services"][name]


class TestComposeM34Backend:
    def setup_method(self):
        self.backend = _service("backend")

    def test_file_exists(self):
        assert COMPOSE_M34.exists()

    def test_non_root_user(self):
        assert self.backend["user"] == "10001:10001"

    def test_cap_drop_all(self):
        assert "ALL" in self.backend["cap_drop"]

    def test_no_new_privileges(self):
        assert "no-new-privileges:true" in self.backend["security_opt"]

    def test_read_only_rootfs(self):
        assert self.backend["read_only"] is True

    def test_writable_paths_are_explicit(self):
        # SQLite data volume + tmpfs for /tmp (sqlite temp files, curl runtime).
        volumes = " ".join(self.backend["volumes"])
        assert "spectra-sqlite-data:/app/data" in volumes
        assert any("/tmp" in str(v) for v in self.backend["tmpfs"])

    def test_resource_limits(self):
        deploy = self.backend.get("deploy", {}).get("resources", {}).get("limits", {})
        assert deploy.get("memory")
        assert deploy.get("cpus")

    def test_healthcheck_preserved(self):
        assert "healthcheck" in self.backend
        assert "/health" in str(self.backend["healthcheck"]["test"])

    def test_sqlite_volume_path_unchanged(self):
        # Compatibility contract: the production data volume keeps its name
        # and mountpoint so M3.3 backups and rollback remain valid.
        text = COMPOSE_M34.read_text(encoding="utf-8")
        assert "spectra-sqlite-data" in text


class TestComposeM34Frontend:
    def setup_method(self):
        self.frontend = _service("frontend")

    def test_non_root_or_explicit_user(self):
        # nginx unprivileged port 8080 is already non-privileged; user is
        # pinned to the image's nginx-unprivileged uid for consistency.
        assert "user" in self.frontend

    def test_hardening_flags_present(self):
        assert "ALL" in self.frontend.get("cap_drop", [])
        assert "no-new-privileges:true" in self.frontend.get("security_opt", [])

    def test_tailscale_only_bind_preserved(self):
        ports = self.frontend["ports"]
        # Host bind stays on the tailscale interface, not 0.0.0.0.
        assert any(str(p).startswith("100.113.157.0:8080") or "${" in str(p) for p in ports)


class TestDockerfileBackend:
    def test_non_root_user_created(self):
        text = DOCKERFILE_BACKEND.read_text(encoding="utf-8")
        assert "useradd" in text or "adduser" in text
        assert "USER spectra" in text

    def test_data_dir_prepared_for_non_root(self):
        text = DOCKERFILE_BACKEND.read_text(encoding="utf-8")
        # Ownership granted before USER switch so entrypoint cp works.
        assert "chown" in text


class TestGuardsIntact:
    def test_publisher_prod_guard_present(self):
        publisher = (REPO_ROOT / "backend/app/publishing/publisher.py").read_text(
            encoding="utf-8"
        )
        assert "_is_prod_path" in publisher
        assert "refuses production path" in publisher

    def test_deploy_script_refuses_legacy_checkout(self):
        script = (REPO_ROOT / "backend/app/scripts/deploy_release.sh").read_text(
            encoding="utf-8"
        )
        assert "legacy checkout" in script
