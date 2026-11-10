"""Alert evaluation for SPECTRA (M3.4 — alerting readiness).

Defines the actionable alert set from OBSERVABILITY_PLAN.md and evaluates
them against observed signals. This is a LOCAL evaluation engine: it reads a
signals dict (produced by a monitoring probe or the /metrics + /ready +
backup-state collectors) and returns the alerts that should fire.

Design
------
- Each alert has: id, severity, condition (evaluated), message, and runbook
  pointer. Only actionable alerts are defined — if no operator action
  exists, it is a metric, not an alert.
- Firing logic is pure: evaluate(signals) -> list[Alert]. Trivially testable,
  no external notifier is wired (per the operation contract: no unsolicited
  external notifications). Operators can pipe the output anywhere.
- Signals are dicts so probes written in bash/python/curl can all feed it.

Alert set
---------
- backend_down: /ready probe failing repeatedly.
- frontend_down: frontend / probe failing.
- high_5xx_rate: 5xx share of recent requests above threshold.
- db_integrity_failure: PRAGMA integrity_check != ok.
- backup_stale: newest backup older than the max age.
- backup_missing: no backup files found.
- low_disk: free space below the minimum.
- container_restart_storm: restart count jumped within the window.
- ai_provider_failure: AI error share above threshold when configured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    id: str
    severity: str  # "critical" | "warning"
    message: str
    runbook: str


# Thresholds (documented in OBSERVABILITY_PLAN.md; tune with evidence only).
HIGH_5XX_RATE = 0.05          # >5% of requests
MIN_BACKUP_MAX_AGE_HOURS = 48 # backup must be fresher than this
MIN_FREE_BYTES = 1 << 30      # 1 GiB
RESTART_STORM_COUNT = 3       # restarts within the window
AI_FAILURE_RATE = 0.5         # >50% AI calls failing when configured


def _require(signals: dict, key: str):
    if key not in signals:
        return None
    return signals[key]


def evaluate(signals: dict) -> list[Alert]:
    """Evaluate one observation window. Returns the alerts that should fire."""
    alerts: list[Alert] = []

    # Backend availability.
    ready_ok = _require(signals, "backend_ready_ok")
    if ready_ok is False:
        alerts.append(Alert(
            id="backend_down",
            severity="critical",
            message="/ready is failing: backend or database unavailable",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#backend-down",
        ))

    frontend_ok = _require(signals, "frontend_ok")
    if frontend_ok is False:
        alerts.append(Alert(
            id="frontend_down",
            severity="critical",
            message="frontend is not serving requests",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#frontend-down",
        ))

    # HTTP error share.
    total = _require(signals, "total_requests")
    server_errors = _require(signals, "server_errors")
    if isinstance(total, int) and isinstance(server_errors, int) and total > 20:
        rate = server_errors / total
        if rate > HIGH_5XX_RATE:
            alerts.append(Alert(
                id="high_5xx_rate",
                severity="critical",
                message=f"5xx rate {rate:.1%} over the last {total} requests (threshold {HIGH_5XX_RATE:.0%})",
                runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#high-5xx-rate",
            ))

    # Database integrity.
    integrity = _require(signals, "db_integrity")
    if integrity is not None and integrity != "ok":
        alerts.append(Alert(
            id="db_integrity_failure",
            severity="critical",
            message=f"SQLite integrity_check returned {integrity!r} — stop writes, restore from backup",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#db-integrity-failure",
        ))

    # Backups.
    backup_age_hours = _require(signals, "backup_age_hours")
    if backup_age_hours is None:
        alerts.append(Alert(
            id="backup_missing",
            severity="critical",
            message="no backup file found in the backup directory",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#backup-missing",
        ))
    elif backup_age_hours > MIN_BACKUP_MAX_AGE_HOURS:
        alerts.append(Alert(
            id="backup_stale",
            severity="warning",
            message=f"newest backup is {backup_age_hours:.0f}h old (max {MIN_BACKUP_MAX_AGE_HOURS}h)",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#backup-stale",
        ))

    # Disk.
    free_bytes = _require(signals, "free_bytes")
    if isinstance(free_bytes, int) and free_bytes < MIN_FREE_BYTES:
        alerts.append(Alert(
            id="low_disk",
            severity="warning",
            message=f"only {free_bytes / (1 << 30):.1f} GiB free (minimum {MIN_FREE_BYTES / (1 << 30):.0f} GiB)",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#low-disk",
        ))

    # Container restarts.
    restarts = _require(signals, "restart_count")
    if isinstance(restarts, int) and restarts >= RESTART_STORM_COUNT:
        alerts.append(Alert(
            id="container_restart_storm",
            severity="critical",
            message=f"container restarted {restarts} times within the window",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#restart-storm",
        ))

    # AI provider (only meaningful when configured).
    ai_configured = _require(signals, "ai_configured")
    ai_calls = _require(signals, "ai_calls")
    ai_failures = _require(signals, "ai_failures")
    if (
        ai_configured
        and isinstance(ai_calls, int) and isinstance(ai_failures, int)
        and ai_calls >= 5
        and ai_failures / ai_calls > AI_FAILURE_RATE
    ):
        alerts.append(Alert(
            id="ai_provider_failure",
            severity="warning",
            message=f"AI provider failing for {ai_failures}/{ai_calls} calls — check key, quota, connectivity",
            runbook="docs/v3.1/PRODUCTION_RUNBOOK.md#ai-provider-failure",
        ))

    return alerts


def format_alerts(alerts: list[Alert]) -> str:
    """Plain-text rendering for logs or a notifier pipe."""
    if not alerts:
        return "no alerts"
    return "\n".join(
        f"[{a.severity.upper():8s}] {a.id}: {a.message} (runbook: {a.runbook})"
        for a in alerts
    )
