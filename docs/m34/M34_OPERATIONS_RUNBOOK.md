# M3.4 Operations Runbook (Task 8)

**Date**: 2026-11-26
**Applies to**: SPECTRA production on DavidLab (`david-lab`, tailscale-only `http://100.113.157.0:8080`)
**Baseline**: M3.3 @ `5c2c7d9a37109da99f20a34973503d1bd6deb236`

## 1. Daily operations — "is SPECTRA healthy right now?"

```bash
# One command: collects every signal + evaluates alerts (Task 7).
ssh david-lab
python3 -c "
import json, sys
sys.path.insert(0, '<release-dir>')
from backend.app.scripts.health_snapshot import build_signals
s = build_signals(
    base_url='http://127.0.0.1:8080',
    backup_dir='/home/david/backups/spectra/scheduled',
    container='spectra-backend',
)
print(json.dumps(s, indent=2))
"
# Non-empty alerts[] = actionable (each carries a runbook anchor).
# Empty alerts[] = healthy window.
```

Signals collected: backend_ready_ok, frontend_ok, http_5xx_rate,
backup_age_hours, free_bytes, restart_count, migrations (from `/api/ready`).

## 2. Alert handling (ids → runbook anchors)

| Alert | First action |
|---|---|
| `backend_down` | `docker ps` → `docker logs spectra-backend --tail 50`; if DB integrity, §4 |
| `frontend_down` | `docker ps` → frontend logs; restart via compose only |
| `high_5xx_rate` | `curl http://127.0.0.1:8080/api/metrics` → per-route counters |
| `db_integrity_failure` | **stop writes** (compose down) → §4 restore |
| `backup_missing` / `backup_stale` | run §3 manually; check cron mail |
| `low_disk` | prune docker/images carefully; check backup retention |
| `container_restart_storm` | `docker inspect --format '{{.RestartCount}} {{.State.Error}}'` |
| `ai_provider_failure` | check `GEMINI_API_KEY` presence in compose env (never print the value) |

## 3. Manual backup + verification (any time)

```bash
# Inside the running backend (Online Backup API — consistent under writes):
docker exec spectra-backend python -m backend.app.scripts.backup_job \
    --source /app/data/spectra.db \
    --backup-dir /backups \
    --keep 14
# (requires the backups volume mounted; see M34_BACKUP_AUTOMATION.md §4)

# Verify an entire backup set (manifests + checksums + last_good):
docker exec spectra-backend python -m backend.app.scripts.backup_job \
    --verify-dir /backups
# → {"last_good_ok": true, ...} means restorable.
```

## 4. Restore procedure (incident)

Trigger: integrity failure, data-loss signal, failed migration.

```bash
# 0. Stop writes:
docker compose -f compose.json -p spectra down
# 1. Identify last good backup (manifest sha256 + verify):
python -m backend.app.scripts.backup_job --verify-dir /backups
# 2. Restore into the volume via a helper container (--volumes-from pattern):
docker run --rm -v spectra-sqlite-data:/data -v /home/david/backups:/b alpine \
    sh -c "cp /b/<last-good>.db /data/spectra.db"
# 3. Bring up the PREVIOUS release compose (rollback images), verify:
#    /api/ready → migrations tracked-version-N; /api/hardware?limit=1 → rows
```

Full paths + rehearsed timings: `docs/m3/M33_ROLLBACK_RUNBOOK.md` (5 paths).

## 5. Deployment (M3.4 staged model — Task 5)

```bash
# PRE-INTERRUPTION (service stays up):
python -m backend.app.scripts.deploy_m34 --release-dir <dir> --expected-sha <sha> --stage preflight
python -m backend.app.scripts.deploy_m34 --release-dir <dir> --expected-sha <sha> --stage prepare   # + backup + identity
# CUTOVER (the only downtime window; write-loss guard aborts on lost writes):
./backend/app/scripts/deploy_release.sh --release-dir <dir> --expected-sha <sha>
# ACCEPTANCE: /health /ready /release; sha must match; downtime recorded honestly
# (user_visible_downtime = first_healthy − down_complete; operator pauses NOT subtracted).
```

Hardened runtime: `compose.yaml -f compose.m34.yaml` (non-root, cap_drop ALL,
no-new-privileges, read_only rootfs, tmpfs, resource limits). SQLite volume
name/mountpoint unchanged — backups and rollback remain valid.

## 6. Scheduled jobs (PREPARED, NOT ACTIVATED — owner approval required)

| Job | Config | Status |
|---|---|---|
| Nightly backup 03:17 | `ops/backup/cron_backup.sh.example` | prepared, not installed |
| Monitor probe every 5 min | `docs/v3.1/OBSERVABILITY_PLAN.md` §4 | prepared, not installed |

Activation: copy to `/home/david/ops/`, add crontab entry, verify next
morning. Never activate both jobs without owner sign-off.

## 7. Security posture switches (owner-gated)

| Switch | Current (prod) | Prepared config |
|---|---|---|
| `SPECTRA_AUTH_ENABLED` | unset (auth off) | `1` (SECURE_AUTH_CONFIG.example.env) |
| `SPECTRA_AUTH_REGISTRATION_ENABLED` | n/a (new flag, default open) | `0` (fail-closed) |
| Tailscale ACL for :8080 | owner console | verify restricts to owned devices |

Activation procedure (step-by-step, with post-cutover acceptance probes):
`docs/m34/SECURE_AUTH_CONFIG.example.env`. No live change without approval.
