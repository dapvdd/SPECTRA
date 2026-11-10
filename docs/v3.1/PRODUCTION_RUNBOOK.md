# SPECTRA V3.1 — Production Runbook

Date: 2026-11-10
Scope: day-to-day operations for the deployed SPECTRA V3 release, updated for
the V3.1 tooling (on branch `feat/spectra-v3.1-production-hardening`, not yet
deployed). Tools marked **[V3.1]** ship with the branch; everything else works
against the deployed 75eba50 release today.

---

## 1. System map

| Component | Location | Notes |
|---|---|---|
| Frontend | container `spectra-frontend`, image `spectra-frontend:75eba50b…` | nginx, port 8080, `/api/` proxied to backend |
| Backend | container `spectra-backend`, image `spectra-backend:75eba50b…` | FastAPI, no host port; internal `:8000` |
| Database | `/app/data/spectra.db` in `spectra-backend`, volume `spectra-sqlite-data` | SQLite, migration v2, 5380 hw rows |
| Ops dir | `/home/david/releases/spectra-75eba50-ops/` | compose.json, evidence, backups |
| Source checkout | `/home/david/releases/spectra-75eba50/` | clean, at the release SHA |
| Legacy checkout | `/home/david/projects/spectra/` | **DO NOT deploy from here** (dirty, collision hazard) |
| Production URL | `http://100.113.157.0:8080/` | Tailscale-only |

## 2. Health checks (run these first, always)

```bash
curl -fsS http://100.113.157.0:8080/api/health   # → {"status":"healthy"}
curl -fsS http://100.113.157.0:8080/api/ready    # → ready, database reachable, migrations tracked-version-2
curl -fsS http://100.113.157.0:8080/api/release  # [V3.1] version/git_sha/ai_provider_state
docker ps --filter name=spectra                   # both Up, 0 restarts
```

`/ready` is the authoritative check (DB + migrations); `/health` is liveness
only. Container healthcheck currently probes `/health` (F-09) — switch to
`/ready` at the next image build.

## 3. Alert responses

Each alert's id maps to an anchor below (from `alerts.py [V3.1]`).

### backend-down
1. `docker ps` — is the container up? `docker logs --tail 50 spectra-backend`.
2. `/api/ready` detail: `database: reachable`? If DB unreachable, check the
   volume is mounted (`docker inspect spectra-backend` → Binds/Mounts).
3. Restart policy is `unless-stopped` — a crashed container self-restarts; if
   it crash-loops, capture logs BEFORE restarting anything.
4. Escalate to the restore procedure (§5) only with evidence of DB corruption.

### frontend-down
1. `docker ps` + `docker logs --tail 30 spectra-frontend`.
2. `curl -I http://100.113.157.0:8080/` — 200 with `Cache-Control: no-cache`.
3. Backend may still be fine — the nginx proxy is the failure point.

### high-5xx-rate
1. `docker logs --tail 100 spectra-backend` — find the failing route template.
2. Common causes: AI provider failures (502) — check `/api/release`
   `ai_provider_state`; validation storms (422) are client bugs, not server.
3. [V3.1] `/api/metrics` shows status classes per route template.

### db-integrity-failure
**Stop.** This is the most severe state.
1. Freeze writes: `docker stop spectra-frontend` (traffic stops hitting the DB).
2. Capture evidence: `docker cp spectra-backend:/app/data/spectra.db /tmp/evidence-<ts>.db`.
3. Follow the restore procedure (§5) with the newest VERIFIED backup.
4. Never run `PRAGMA integrity_check` fixes on the live DB without a backup.

### backup-missing / backup-stale
1. Check the backup directory: `ls -lt /home/david/backups/spectra/` (or the
   ops dir's backups until the cron is installed).
2. Run a manual backup (§4) immediately — the data-loss window is growing.
3. If the cron is missing, install it (BACKUP_RECOVERY_PLAN.md §4, user-gated).

### low-disk
1. `df -h /home/david` — check the volume's host filesystem.
2. Safe to clean: old `/tmp` rehearsal files, old `restore-proof-*.db` copies.
3. Never delete `backup-*.db` files by hand — use the retention tool [V3.1]
   (`restore_rehearsal.py --prune <dir> --keep 7`) which refuses to over-prune.

### restart-storm
1. `docker inspect spectra-backend --format '{{.RestartCount}} {{.State.StartedAt}}'`.
2. `docker logs --previous spectra-backend` for the crash cause.
3. A restart storm with DB errors → suspect the DB; go to db-integrity-failure.

### ai-provider-failure
1. `curl http://100.113.157.0:8080/api/release` — is `ai_provider_state`
   still `configured`? If `unconfigured`, the key was lost from the env.
2. Check quota/key validity at Google AI Studio; 429s from Google surface as
   502 after retries.
3. The M4.4 concurrency bound returns 429 when saturated — a burst of 429s is
   load, not failure; a burst of 502s is the provider.

## 4. Common operations

### Manual verified backup [V3.1]
```bash
# Inside the container (once the V3.1 image ships the scripts):
docker exec spectra-backend python -m backend.app.scripts.backup_database \
    --source /app/data/spectra.db --output /tmp/backup-<ts>.db
docker cp spectra-backend:/tmp/backup-<ts>.db /home/david/backups/spectra/

# Today (deployed 75eba50 image, no scripts inside): the proven
# sqlite3-online-backup pattern from the release ops dir:
docker exec spectra-backend python -c "import sqlite3; s=sqlite3.connect('file:/app/data/spectra.db?mode=ro',uri=True); d=sqlite3.connect('/tmp/backup-<ts>.db'); s.backup(d); d.close(); s.close()"
docker cp spectra-backend:/tmp/backup-<ts>.db /home/david/backups/spectra/
```

### Restore rehearsal (MANDATORY before any real restore) [V3.1]
```bash
python3 -m backend.app.scripts.restore_rehearsal \
    --backup /home/david/backups/spectra/backup-<ts>.db \
    --target /tmp/rehearsal-<ts>.db
# must print "restore_rehearsal_passed"
```

### Deploy a release (see DEPLOYMENT_GUARDRAILS.md)
```bash
bash backend/app/scripts/deploy_release.sh \
    --release-dir /home/david/releases/spectra-<sha>-ops \
    --source-dir  /home/david/releases/spectra-<sha> \
    --repo-root   /home/david/releases/spectra-<sha> \
    --expected-sha <full-sha> --dry-run   # then remove --dry-run
```
Never deploy from `/home/david/projects/spectra` (legacy, dirty, collision).

### Check who is hitting the API
Anonymous in the current state (auth disabled, F-01). Access logs:
`docker logs spectra-frontend` (nginx access log). [V3.1] `/api/metrics`
aggregates request counts by route template (no PII).

## 5. Restore procedure (DB corruption / bad migration)

Full procedure: BACKUP_RECOVERY_PLAN.md §5. Short form:
1. Stop traffic (`docker stop spectra-frontend`).
2. Evidence-copy the failing DB OUT of the container.
3. Pick the newest VERIFIED backup.
4. Rehearse into `/tmp` — must pass.
5. `docker cp` the rehearsed file into place + `docker restart spectra-backend`.
6. Verify `/api/ready` + row counts against the rehearsal output.

The actual restore-over-live-DB is a human, user-gated mutation. Never
automate step 5.

## 6. Known gaps (status per SECURITY_FINDINGS.md)

| Gap | Interim control |
|---|---|
| Auth disabled (F-01) | Tailscale-only exposure; enable per AUTHORIZATION_MATRIX.md §3 when approved |
| No backup cron (F-04) | Manual backup after significant changes; install cron when approved |
| `:latest` tags on host (F-02) | Never reference `:latest`; preflight blocks them in releases |
| Healthcheck probes `/health` (F-09) | Use `/api/ready` manually; fix at next image build |
| AI unconfigured (F-02/known issue 2) | AI endpoints return 503; activate per AI_PROVIDER_READINESS.md §6 |

## 7. Escalation

Self-hosted single-operator system: there is no pager. The alert engine
[V3.1] prints plain-text alerts for whatever channel the operator chooses.
For anything touching production state (auth activation, restore-over-live,
cron install, image rebuild), the operator's explicit approval is the gate —
matching the operation contract under which V3.1 was built.
