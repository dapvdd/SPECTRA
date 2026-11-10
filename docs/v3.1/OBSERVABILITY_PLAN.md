# SPECTRA V3.1 — Observability Plan

Date: 2026-11-10
Scope: what is measured, what alerts, and how an operator answers "is SPECTRA
healthy right now?" Built in M3 (metrics + alert engine); production wiring
(scrape + notify) is documented as a user-gated step.

---

## 1. Surfaces

| Surface | Endpoint/source | Content | Safety |
|---|---|---|---|
| Liveness | `GET /api/health` | Process up + DB reachable | No secrets |
| Readiness | `GET /api/ready` | DB reachable + `migrations: tracked-version-2` | No secrets |
| Release identity | `GET /api/release` | version, git_sha, built_at, auth_enabled, ai_provider, ai_provider_state | Never reports the key value (tested) |
| Metrics | `GET /api/metrics` | Aggregate request counters by **route template** + status classes | Bounded cardinality: no raw paths with IDs, no query strings, no bodies (tested) |
| Alert engine | `backend/app/scripts/alerts.py` | Pure `evaluate(signals) -> [Alert]` with runbook pointers | Local evaluation; no unsolicited external notifications |

## 2. Metric inventory (from `/metrics` + probes)

| Metric | Source | Alert use |
|---|---|---|
| `total_requests` | middleware counters | 5xx-rate denominator |
| `status_classes` (2xx/4xx/5xx) | middleware counters | `high_5xx_rate` |
| per-route counts | middleware (template only) | localizing failures |
| `db_integrity` | `PRAGMA integrity_check` via probe | `db_integrity_failure` |
| `backup_age_hours` | newest `backup*.db` mtime | `backup_missing`, `backup_stale` |
| `free_bytes` | `statvfs`-style probe on host | `low_disk` |
| `restart_count` | `docker inspect RestartCount` delta | `container_restart_storm` |
| `ai_calls` / `ai_failures` | provider error counters (M4) | `ai_provider_failure` |
| `frontend_ok` | frontend `GET /` probe | `frontend_down` |

## 3. Alert set (all actionable; if no action exists it is a metric, not an alert)

| Alert id | Severity | Condition (defaults) | Operator action → runbook anchor |
|---|---|---|---|
| `backend_down` | critical | `/ready` failing | PRODUCTION_RUNBOOK.md#backend-down |
| `frontend_down` | critical | frontend `/` failing | #frontend-down |
| `high_5xx_rate` | critical | >5% of last ≥20 requests | #high-5xx-rate |
| `db_integrity_failure` | critical | `integrity_check` != ok | #db-integrity-failure |
| `backup_missing` | critical | no backup file found | #backup-missing |
| `backup_stale` | warning | newest backup >48 h | #backup-stale |
| `low_disk` | warning | <1 GiB free | #low-disk |
| `container_restart_storm` | critical | ≥3 restarts in window | #restart-storm |
| `ai_provider_failure` | warning | >50% of ≥5 AI calls failing (only when configured) | #ai-provider-failure |

Thresholds are constants in `alerts.py` (documented here); tune only with
evidence. All 21 evaluation tests pass, including the "silent signals" case:
**no backup signal at all fires `backup_missing`** — absence of evidence is
the alert, not peace of mind.

## 4. The monitoring probe (to install — USER-GATED)

The engine is local and dependency-free; a minimal host probe that feeds it:

```bash
# /home/david/ops/spectra_monitor.sh — run via cron every 5 min (user-gated)
signals='{}'
signals="$signals'backend_ready_ok': $(curl -fsS -m 5 http://127.0.0.1:8080/api/ready >/dev/null 2>&1 && echo true || echo false),"
# ... collect the other signals (backup age via ls -t, disk via df, restarts
# via docker inspect) ...
python3 - "$signals" <<'EOF'
import json, sys
from backend.app.scripts.alerts import evaluate, format_alerts
print(format_alerts(evaluate(json.loads(sys.argv[1]))))
EOF
```

Any non-empty output is an alert: pipe to the operator's existing channel
(the user's choice — email/ntfy/etc.; nothing is wired by this operation).
Until installed, the runbook's manual health-check covers the gap.

## 5. What observability deliberately does NOT do

- **No external notification wiring** — the operation contract forbids
  unsolicited notifications; the engine outputs text, the operator chooses the
  transport.
- **No per-request tracing** — aggregate-only metrics keep cardinality bounded
  and PII out of logs; individual request debugging uses container logs.
- **No scraping of the live DB beyond read-only PRAGMAs** — probes are
  read-only by construction.

## 6. Current production posture (baseline, unchanged by this branch)

- Healthcheck: `/health` only (F-09, P3) — switch to `/ready` at next image
  build (user-gated).
- No scrape/alert pipeline installed yet — the manual runbook checks are the
  interim control.
