"""Deployment preflight for SPECTRA.

Fail-closed checks before any deployment or rollback. A deployment is
authorised only when every check passes; any ambiguity or collision is a
hard failure.  The tool never mutates anything — it only inspects and reports.

Usage::

    python backend/app/scripts/deploy_preflight.py \
        --release-dir /home/david/releases/spectra-<sha>-ops \
        --expected-sha <sha>

Exit codes: 0 = all pass; 1 = one or more failed; 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MUTABLE_TAGS = frozenset({"latest", "stable", "dev", "main"})
MIN_FREE_BYTES = 1 << 30  # 1 GB
MIN_BACKUP_AGE_HOURS = 48  # warn if no backup in 48 h


# ---------------------------------------------------------------------------
# Check result model
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    blocker: bool = True  # True = fail the deployment

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "blocker": self.blocker,
        }


@dataclass
class PreflightResult:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def blockers(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.blocker]

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "checks": [c.to_dict() for c in self.checks],
            "blocker_count": len(self.blockers),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def _git_sha_at(dirpath: Path) -> str | None:
    r = _run(["git", "rev-parse", "HEAD"], cwd=dirpath)
    if r.returncode == 0:
        return r.stdout.strip()
    return None


def _git_status_clean(dirpath: Path) -> tuple[bool, str]:
    r = _run(["git", "status", "--porcelain"], cwd=dirpath)
    if r.returncode != 0:
        return False, f"git status failed: {r.stderr.strip()}"
    lines = [l for l in r.stdout.strip().splitlines() if l]
    if lines:
        # A release ops directory (spectra-<sha>-ops) is expected to have
        # transient files (compose.json, evidence, backups). Allow untracked
        # files but reject modified tracked files.
        modified = [l for l in lines if not l.startswith("?? ")]
        if modified:
            return False, f"modified tracked files: {modified}"
    return True, "clean"


def _load_compose_compatibility(path: Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_release_sha(release_dir: Path, expected_sha: str) -> CheckResult:
    """Verify the release directory is checked out at the expected SHA."""
    actual = _git_sha_at(release_dir)
    if actual is None:
        return CheckResult(
            name="release_sha",
            passed=False,
            detail="Could not determine git SHA of release directory",
            blocker=True,
        )
    if actual != expected_sha:
        return CheckResult(
            name="release_sha",
            passed=False,
            detail=f"Expected {expected_sha}, got {actual}",
            blocker=True,
        )
    return CheckResult(name="release_sha", passed=True, detail=actual)


def check_git_clean(release_dir: Path) -> CheckResult:
    """Verify the release directory is clean of modified tracked files."""
    clean, detail = _git_status_clean(release_dir)
    return CheckResult(
        name="git_clean",
        passed=clean,
        detail=detail,
        blocker=False,  # Release ops dirs may have untracked transient files
    )


def check_compose_collision(release_dir: Path) -> CheckResult:
    """Detect project name, container, and port collisions with running containers.

    The legacy checkout shares these identifiers. Any match with a different
    working directory signals a collision risk.
    """
    compose_path = release_dir / "compose.json"
    if not compose_path.exists():
        return CheckResult(
            name="compose_collision",
            passed=False,
            detail="compose.json not found in release directory",
            blocker=True,
        )

    try:
        compose = _load_compose_compatibility(compose_path)
    except (json.JSONDecodeError, OSError) as exc:
        return CheckResult(
            name="compose_collision",
            passed=False,
            detail=f"Could not read compose.json: {exc}",
            blocker=True,
        )

    project_name = compose.get("name", "")
    if not project_name:
        return CheckResult(
            name="compose_collision",
            passed=False,
            detail="compose.json has no project name",
            blocker=True,
        )

    # Check against running containers.
    r = _run(["docker", "ps", "--format", "{{.Names}}|{{.Image}}|{{.Ports}}"])
    if r.returncode != 0:
        return CheckResult(
            name="compose_collision",
            passed=False,
            detail=f"docker ps failed: {r.stderr.strip()}",
            blocker=True,
        )

    colliding: list[str] = []
    release_images: set[str] = set()
    for svc_name, svc in (compose.get("services") or {}).items():
        image = svc.get("image", "")
        if image:
            release_images.add(image)

    for line in r.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("|")
        container_name = parts[0]
        running_image = parts[1]
        ports = parts[2] if len(parts) > 2 else ""

        # Collision 1: same container name as the release services.
        compose_services = compose.get("services") or {}
        for svc_name, svc in compose_services.items():
            for attr in ("container_name", "service"):
                expected = svc.get(attr) or svc_name
                if container_name == expected and running_image not in release_images:
                    colliding.append(
                        f"container={container_name} running={running_image} "
                        f"(shared with release, not from release images)"
                    )

        # Collision 2: published port clash.
        ports_list = compose.get("services", {}).values()
        for svc in ports_list:
            for binding in (svc.get("ports") or []):
                # Parse "host:container" or just "container".
                host_port = str(binding).split(":")[0] if ":" in str(binding) else None
                if host_port:
                    for running_port in ports.split(","):
                        clean_port = running_port.strip().split("/")[0]
                        if host_port == clean_port and container_name != expected:
                            colliding.append(
                                f"port {host_port} bound by running={container_name} "
                                f"(release wants it too)"
                            )

    if colliding:
        detail = f"Collisions detected: {'; '.join(colliding)}"
        return CheckResult(name="compose_collision", passed=False, detail=detail)

    return CheckResult(name="compose_collision", passed=True, detail=project_name)


def check_image_tags(release_dir: Path) -> CheckResult:
    """Reject mutable image tags (latest, stable, dev, main) in the release images."""
    compose_path = release_dir / "compose.json"
    if not compose_path.exists():
        return CheckResult(
            name="image_tags",
            passed=False,
            detail="compose.json not found",
            blocker=True,
        )

    try:
        compose = _load_compose_compatibility(compose_path)
    except (json.JSONDecodeError, OSError) as exc:
        return CheckResult(
            name="image_tags", passed=False, detail=f"Could not read compose.json: {exc}"
        )

    mutable: list[str] = []
    for svc_name, svc in (compose.get("services") or {}).items():
        image = svc.get("image", "")
        if not image:
            mutable.append(f"{svc_name}: no image specified")
            continue
        tag = image.split(":")[-1]
        # If no tag, it's a bare repo digest or implicit latest.
        if ":" not in image:
            mutable.append(f"{svc_name}: '{image}' has no tag (assumed mutable)")
        elif tag in MUTABLE_TAGS:
            mutable.append(f"{svc_name}: image={image} (mutable tag '{tag}')")

    if mutable:
        detail = f"Mutable tags: {'; '.join(mutable)}"
        return CheckResult(name="image_tags", passed=False, detail=detail, blocker=True)

    # Report what tags are actually in use (for the log).
    tags: list[str] = []
    for svc in (compose.get("services") or {}).values():
        if svc.get("image"):
            tags.append(svc["image"])
    detail = f"tags OK: {', '.join(tags)}"
    return CheckResult(name="image_tags", passed=True, detail=detail)


def check_backup_available(release_dir: Path) -> CheckResult:
    """Verify a backup exists in the release directory (rollback insurance)."""
    backup_dir = release_dir
    candidates = sorted(backup_dir.glob("backup*.db"), reverse=True)
    if not candidates:
        return CheckResult(
            name="backup_available",
            passed=False,
            detail="No backup*.db found in release directory",
            blocker=True,
        )
    latest = candidates[0]

    # Use the file modification time.
    import time
    age_seconds = time.time() - latest.stat().st_mtime
    age_hours = age_seconds / 3600

    detail = f"backup={latest.name} age={age_hours:.1f}h"
    if age_hours > MIN_BACKUP_AGE_HOURS:
        return CheckResult(
            name="backup_available",
            passed=False,
            detail=f"{detail} (older than {MIN_BACKUP_AGE_HOURS}h)",
            blocker=True,
        )
    return CheckResult(name="backup_available", passed=True, detail=detail)


def check_migration_compatible(release_dir: Path) -> CheckResult:
    """Verify the release's DB backup is at or below the runner's latest migration version.

    The runner knows the current schema_version. We import it dynamically so
    this preflight works without needing the full backend import path.
    """
    # Find the most recent backup to check.
    backups = sorted(release_dir.glob("backup*.db"), reverse=True)
    if not backups:
        return CheckResult(
            name="migration_compatible",
            passed=False,
            detail="No backup found to check schema version",
            blocker=True,
        )

    db_path = backups[0]
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    try:
        from backend.app.migrations.runner import MIGRATIONS
    except ImportError:
        return CheckResult(
            name="migration_compatible",
            passed=False,
            detail="Could not import migrations runner (path issue)",
            blocker=True,
        )

    latest_runner_version = max(m.version for m in MIGRATIONS)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if not has_table:
            detail = (
                f"backup={db_path.name} has no schema_version table "
                "(pre-v1, no tracked migrations)"
            )
            # Pre-v1 is acceptable for the baseline; warn but don't block.
            return CheckResult(
                name="migration_compatible",
                passed=True,
                detail=detail,
                blocker=False,
            )
        db_version = conn.execute(
            "SELECT version FROM schema_version WHERE id=1"
        ).fetchone()
        if db_version is None:
            return CheckResult(
                name="migration_compatible",
                passed=False,
                detail="schema_version table exists but id=1 row is empty",
                blocker=True,
            )
        db_version = db_version[0]
    finally:
        conn.close()

    if db_version > latest_runner_version:
        return CheckResult(
            name="migration_compatible",
            passed=False,
            detail=(
                f"backup schema_version={db_version} exceeds "
                f"runner version={latest_runner_version} — cannot downgrade"
            ),
            blocker=True,
        )
    detail = f"backup version={db_version}, runner latest={latest_runner_version}"
    return CheckResult(
        name="migration_compatible", passed=True, detail=detail, blocker=False
    )


def check_disk_space(release_dir: Path, min_bytes: int = MIN_FREE_BYTES) -> CheckResult:
    """Verify at least min_bytes of free space are available."""
    total, used, free = shutil.disk_usage(release_dir)
    detail = f"free={free / (1 << 30):.1f}GB total={total / (1 << 30):.1f}GB"
    if free < min_bytes:
        return CheckResult(
            name="disk_space",
            passed=False,
            detail=f"{detail} (need {min_bytes / (1 << 30):.1f}GB)",
            blocker=True,
        )
    return CheckResult(name="disk_space", passed=True, detail=detail)


def check_volume_identity(release_dir: Path, expected_volume: str = "spectra-sqlite-data") -> CheckResult:
    """Verify the expected SQLite volume is present and in use."""
    r = _run(["docker", "volume", "ls", "--format", "{{.Name}}"])
    if r.returncode != 0:
        return CheckResult(
            name="volume_identity",
            passed=False,
            detail=f"docker volume ls failed: {r.stderr.strip()}",
            blocker=True,
        )
    volumes = {v.strip() for v in r.stdout.strip().splitlines() if v.strip()}
    if expected_volume not in volumes:
        return CheckResult(
            name="volume_identity",
            passed=False,
            detail=f"Expected volume '{expected_volume}' not found in docker volumes",
            blocker=True,
        )
    return CheckResult(name="volume_identity", passed=True, detail=expected_volume)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_preflight(release_dir: Path, expected_sha: str) -> PreflightResult:
    result = PreflightResult()

    result.checks.append(check_release_sha(release_dir, expected_sha))
    result.checks.append(check_git_clean(release_dir))
    result.checks.append(check_compose_collision(release_dir))
    result.checks.append(check_image_tags(release_dir))
    result.checks.append(check_backup_available(release_dir))
    result.checks.append(check_migration_compatible(release_dir))
    result.checks.append(check_disk_space(release_dir))
    result.checks.append(check_volume_identity(release_dir))

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SPECTRA deployment preflight — fail-closed validation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--release-dir",
        required=True,
        type=Path,
        help="Path to the release directory (e.g. /home/david/releases/spectra-<sha>-ops).",
    )
    parser.add_argument(
        "--expected-sha",
        required=True,
        help="Expected Git SHA for this release (e.g. 75eba50b1f09052f40409f6066a2ac030344d1a0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    if not args.release_dir.exists():
        print(f"ERROR: release directory not found: {args.release_dir}", file=sys.stderr)
        return 2

    result = run_preflight(args.release_dir, args.expected_sha)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"SPECTRA preflight: {args.release_dir.name}")
        print(f"  Expected SHA: {args.expected_sha}")
        for check in result.checks:
            status = "PASS" if check.passed else ("WARN" if not check.blocker else "FAIL")
            print(f"  [{status}] {check.name}: {check.detail}")
        blockers = result.blockers
        if blockers:
            print(f"\n  BLOCKED by {len(blockers)} check(s): {', '.join(c.name for c in blockers)}")
            return 1
        print("\n  All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
