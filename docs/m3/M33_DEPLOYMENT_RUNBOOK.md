# M3.3 Deployment Runbook (Phase 10)

**Date**: 2026-11-25
**Target**: DavidLab production (`david-lab`, 100.113.157.0 via tailscale)
**From**: M2.5-production, SHA `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec`
**To**: M3.3, SHA `5c2c7d9a37109da99f20a34973503d1bd6deb236`
(branch `release/m33-production`, RC images already built and rehearsed)

## 0. Preconditions (all verified in Phases 0–9)

- [x] CI green on RC: 1546 passed / 2 skipped / 0 failed
- [x] Backup taken + restore-verified: `/home/david/backups/spectra/m33-release/m33_backup_20261125T062546Z.db` (SHA256 `d4d19d55…`)
- [x] Migration rehearsal v3→v4 PASS (additive, 0 row loss, idempotent)
- [x] Publication rehearsal PASS (62 verified SKUs, idempotent)
- [x] Isolated deployment rehearsal PASS (API 18/18, visual 10/10)
- [x] Security review: no new regressions (2 pre-existing findings documented)
- [x] Rollback rehearsal PASS (all 5 paths; measured timings below)

## 1. Artifacts

Images (built on david-lab from RC clone at `/tmp/spectra-m33-rc`, exact
SHA checkout, `.dockerignore` excludes `.git`):
- `spectra-backend:m33-rc-5c2c7d9`
- `spectra-frontend:m33-rc-5c2c7d9`

For production, retag with the release identity:

```bash
docker tag spectra-backend:m33-rc-5c2c7d9 spectra-backend:m33-prod-5c2c7d9
docker tag spectra-frontend:m33-rc-5c2c7d9 spectra-frontend:m33-prod-5c2c7d9
```

## 2. Measured timings (downtime estimate)

| Step | Measured |
|---|---|
| Backend container stop+start | 5.2 s |
| Start → first healthy response | 2.4 s |
| Full stop→healthy cycle (rehearsal) | **7.5 s** |
| Migration v3→v4 on prod-size DB (56 MB) | **1.89 s** |
| Backup copy-into-volume (helper container) | ~2–5 s (56 MB) |

**Estimated total downtime window: < 60 s** (compose down 5 s + backup
snapshot 5 s + DB file swap <1 s + compose up 8 s + health verification
10 s, plus generous margin). The app serves no users today (auth off,
0 users, internal tool), so the window is non-disruptive; schedule anyway
outside active hours.

## 3. Exact production cutover sequence

```bash
# ---- Pre-flight (T-30 min) ----
cd /home/david && ls backups/spectra/m33-release/m33_backup_20261125T062546Z.db
ssh david-lab 'docker images | grep m33-prod'          # images present
ssh david-lab 'docker exec spectra-backend curl -s http://localhost:8000/health'
# → {"status":"healthy"}   (current prod green before starting)

# ---- 1. Take the FRESH pre-cutover backup (authoritative rollback point) ----
docker exec spectra-backend python /tmp/backup.py      # Online Backup API method
# evidence JSON + SHA256 recorded; VERIFY sha256 matches before proceeding

# ---- 2. Stop the current production stack (writes end here) ----
cd /home/david/releases/spectra-75eba50-ops
docker compose -p spectra -f compose-m25.json down

# ---- 3. Migrate the DB in place on a COPY, then swap (prod-safe pattern) ----
docker run --rm -v spectra-sqlite-data:/data -v /home/david/backups:/src \
  alpine sh -c 'cp /data/spectra.db /src/spectra/m33-release/pre_cutover_copy.db'
docker run --rm -v spectra-sqlite-data:/data --entrypoint python \
  spectra-backend:m33-prod-5c2c7d9 /tmp/migrate_copy_and_swap.py
# (script: copies volume DB → /tmp/copy.db, runs runner.upgrade(copy),
#  integrity+FK checks, THEN swaps into /data/spectra.db atomically)
# NOTE: the RC runner REFUSES to upgrade /app/data/spectra.db directly —
# the copy-swap pattern is mandatory and is exactly what was rehearsed.

# ---- 4. Update compose to the M3.3 images ----
# edit compose-m25.json → compose-m33.json: image tags m33-prod-5c2c7d9,
# SPECTRA_RELEASE_VERSION=M3.3-production,
# SPECTRA_RELEASE_SHA=5c2c7d9a37109da99f20a34973503d1bd6deb236,
# SPECTRA_RELEASE_BUILT_AT=<now>, keep SPECTRA_AUTH_ENABLED unset (owner
# decision from security review F-1), CORS unchanged.

# ---- 5. Start the M3.3 stack ----
docker compose -p spectra -f compose-m33.json up -d

# ---- 6. Verify (acceptance gates) ----
docker ps --format '{{.Names}} {{.Status}}'        # both healthy
curl -s http://100.113.157.0:8080/api/health        # {"status":"healthy"}
curl -s http://100.113.157.0:8080/api/ready         # migrations tracked-version-4
curl -s http://100.113.157.0:8080/api/release       # version M3.3-production, sha 5c2c7d9
curl -s 'http://100.113.157.0:8080/api/hardware?verified=1' -o /dev/null -w '%{http_code} %{header_json}' | grep -i x-total-count   # 62
curl -s 'http://100.113.157.0:8080/api/hardware?limit=1'  # AMD Athlon Gold 7220C (legacy intact)
curl -s http://100.113.157.0:8080/ -o /dev/null -w '%{http_code}'   # 200 SPA
# Browser spot-check: Explore page shows CPU 3501 / GPU 1879 / RAM 32 /
# STORAGE 10 / MOTHERBOARD 13 / PSU 7 (visual acceptance reproduction).

# ---- 7. Record evidence ----
# save /api/release, /api/ready, verified count output to
# /home/david/backups/spectra/m33-release/cutover_evidence_<TS>.json
```

## 4. Post-cutover verification checklist (gate to declare success)

1. `docker ps` — backend `healthy`, frontend `up`.
2. `/api/health` = `{"status":"healthy"}`.
3. `/api/ready` = `migrations: tracked-version-4`.
4. `/api/release` = `M3.3-production` + SHA `5c2c7d9…`.
5. `GET /api/hardware?verified=1` X-Total-Count = **62**.
6. Legacy intact: `GET /api/hardware?limit=1` → Athlon; total = 5442.
7. SPA loads, catalog composition matches (3501/1879/32/10/13/7).
8. Builder check (7950X + B650-PLUS + DDR5) → rules with reason codes.
9. integrity_check ok + FK 0 (inside container, read-only).
10. Observation window 30 min: no 5xx in backend logs, health green.

## 5. Abort criteria → rollback

Any gate fails after two fix attempts in-window, or data loss signal →
execute `M33_ROLLBACK_RUNBOOK.md` §2 (measured: <60 s to previous release).
