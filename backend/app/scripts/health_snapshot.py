"""M3.4 Task 7 — one-command health snapshot feeding the alert engine.

Collects the operational signals OBSERVABILITY_PLAN.md §2 defines, from
surfaces that already exist (no new infrastructure):

- /api/ready      -> backend_ready_ok, migrations state
- /api/health     -> frontend_ok (through nginx :8080 = full path check)
- /api/release    -> deployed version + git sha (drift/stale diagnostics)
- /api/metrics    -> total_requests + status classes -> http_5xx_rate
- backup dir      -> newest *.db mtime -> backup_age_hours (missing -> None)
- shutil.disk_usage -> free_bytes
- docker inspect  -> RestartCount (via _docker_restart_count, isolated for tests)

Then runs alerts.evaluate(signals) and prints JSON:
{"at": ..., "signals": {...}, "release": {...}, "alerts": [...], "text": ...}

No external notifications are sent (contract: local evaluation only).
Operators pipe the output anywhere.

Usage::

    python -m backend.app.scripts.health_snapshot \
        --base-url http://127.0.0.1:8080 \
        --backup-dir /home/david/backups/spectra/scheduled \
        --container spectra-backend

Exit code: 0 = snapshot collected (alerts may still be firing);
1 = snapshot could not be collected at all.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from backend.app.scripts.alerts import evaluate, format_alerts

_BACKUP_SUFFIXES = (".db",)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_json(base_url: str, path: str, timeout: float = 5.0):
    """Return (status, parsed-json-or-None). Never raises."""
    try:
        with urllib.request.urlopen(f"{base_url}{path}", timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, None
    except Exception:  # noqa: BLE001 - a down endpoint is a signal, not a crash
        return None, None


def _newest_backup_age_hours(backup_dir: Path) -> float | None:
    """Hours since the newest backup file; None when none exist."""
    backup_dir = Path(backup_dir)
    newest_mtime = None
    try:
        for entry in backup_dir.iterdir():
            if entry.is_file() and entry.name.endswith(_BACKUP_SUFFIXES):
                mtime = entry.stat().st_mtime
                if newest_mtime is None or mtime > newest_mtime:
                    newest_mtime = mtime
    except OSError:
        return None
    if newest_mtime is None:
        return None
    return max(0.0, (time.time() - newest_mtime) / 3600.0)


def _docker_restart_count(container: str) -> int:
    """RestartCount from docker inspect; -1 when unavailable (signal omitted)."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.RestartCount}}", container],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return -1
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return -1


def build_signals(
    *,
    base_url: str,
    backup_dir: Path,
    container: str,
) -> dict:
    """Collect one observation window and evaluate alerts."""
    ready_status, ready_body = _fetch_json(base_url, "/api/ready")
    health_status, _ = _fetch_json(base_url, "/api/health")
    release_status, release_body = _fetch_json(base_url, "/api/release")
    metrics_status, metrics_body = _fetch_json(base_url, "/api/metrics")

    total_requests = None
    http_5xx_rate = None
    if isinstance(metrics_body, dict):
        total_requests = metrics_body.get("total_requests")
        classes = metrics_body.get("status_classes") or {}
        server_errors = classes.get("5xx", 0)
        if isinstance(total_requests, int) and total_requests > 0:
            http_5xx_rate = server_errors / total_requests

    restart_count = _docker_restart_count(container)

    try:
        free_bytes = shutil.disk_usage(str(backup_dir)).free
    except OSError:
        free_bytes = None

    signals: dict = {
        "backend_ready_ok": ready_status == 200,
        "frontend_ok": health_status == 200,
        "total_requests": total_requests if isinstance(total_requests, int) else None,
        "http_5xx_rate": http_5xx_rate,
        "backup_age_hours": _newest_backup_age_hours(backup_dir),
        "free_bytes": free_bytes,
        "restart_count": restart_count if restart_count >= 0 else None,
    }
    # db_integrity: read from the ready probe when the backend reports it;
    # a deeper PRAGMA probe is the backup_job --verify-dir audit (Task 4).
    if isinstance(ready_body, dict):
        migrations = ready_body.get("migrations")
        if migrations:
            signals["migrations"] = migrations

    alerts = evaluate(signals)
    return {
        "at": _utc(),
        "signals": signals,
        "release": release_body if isinstance(release_body, dict) else None,
        "alerts": [
            {"id": a.id, "severity": a.severity, "message": a.message, "runbook": a.runbook}
            for a in alerts
        ],
        "text": format_alerts(alerts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--container", default="spectra-backend")
    args = parser.parse_args(argv)

    try:
        snapshot = build_signals(
            base_url=args.base_url,
            backup_dir=args.backup_dir,
            container=args.container,
        )
    except Exception as error:  # noqa: BLE001
        print(f"SNAPSHOT FAILED: {error}", file=__import__("sys").stderr)
        return 1

    print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
