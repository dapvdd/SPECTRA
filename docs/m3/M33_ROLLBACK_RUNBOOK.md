# M3.3 Rollback Runbook (Phase 9 evidence + production procedure)

**Date**: 2026-11-25
**Rehearsed on**: isolated deployment `spectra-m33-rehearsal-{backend,frontend}`
(images `m33-rc-5c2c7d9`) with dedicated volume `spectra-m33-rehearsal-data`
and network `spectra-m33-rehearsal`. Live production untouched.

## 1. Rehearsed rollback paths and measured results

| Path | Steps (rehearsed) | Measured | Result |
|---|---|---|---|
| R-1 Data rollback v4→v3 | copy backup over live file inside container → `docker restart` | **15 s** to healthy | PASS (`/api/ready` → `tracked-version-3`; hardware served) |
| R-2 Forward recovery v3→v4 | copy DB → `runner.upgrade` on the copy → swap in → restart | +4 s to healthy | PASS (v4 again; ready `tracked-version-4`) |
| R-3 Republish after rollback | `run_acquisition` × 4 manifests on a dev-named copy → copy-swap → restart | ~10 s | PASS (62 verified again; integrity ok) |
| R-4 Plain restart persistence | `docker restart` backend | 1 s to healthy | PASS (data intact) |
| R-5 Full compose down/up | `docker compose -p spectra-m33-rehearsal down` → `up -d` | ~60 s incl. pulls=none | PASS (volume persistence; 62 verified served again) |

Final post-cycle verification (all PASS): `/api/ready` = `tracked-version-4`;
`GET /api/hardware?verified=1` total = 62; `/api/health` healthy;
`/api/release` = `M3.3-rehearsal` @ `5c2c7d9…`.

**Important honesty note (observed during R-2/R-3):** rolling the DB file
back to the pristine v3 backup also removes the published v4 lifecycle data
(column is dropped by the file swap). Recovery to the full release state
requires re-running the forward migration AND republishing the manifests —
both proven above (62/62 restored, integrity ok). A pure "file swap" alone
leaves a v3-shaped catalog (5380 rows, no verified SKUs) served by an RC
app — which the app handles (500 on verified-only queries is avoided
because the column exists again only after re-migration; against a raw v3
file the RC app's verified queries would fail). **Therefore the documented
rollback for production is: stop backend → restore v3 backup file →
redeploy the PREVIOUS image (M2.5, `dcfd7df`) — not "v3 file + RC image".**

## 2. Production rollback procedure (DavidLab)

Trigger criteria: failing health checks after cutover, data-loss signal,
integrity/FK violation, or acceptance-critical defect.

```bash
# 0. Freeze: stop writes (backend down already stops all writes)
cd /home/david/releases/spectra-75eba50-ops   # current prod compose dir

# 1. Stop RC stack
docker compose -p spectra -f compose-m25.json down   # or docker stop spectra-backend spectra-frontend

# 2. Restore DB: the pre-cutover backup taken immediately before cutover
#    (SQLite Online Backup API snapshot, e.g. m33_backup_<TS>.db, 56,430,592 B)
docker volume rm spectra-sqlite-data && docker volume create spectra-sqlite-data
docker cp /home/david/backups/spectra/m33-release/<cutover_backup>.db <tmp-container>:/tmp/spectra.db
# then copy into the volume via a helper container (volume is root-owned):
docker run --rm -v spectra-sqlite-data:/data -v /home/david/backups:/src alpine \
  cp /src/spectra/m33-release/<cutover_backup>.db /data/spectra.db

# 3. Redeploy the PREVIOUS release image (M2.5, dcfd7df) — same compose file as today
docker compose -p spectra -f compose-m25.json up -d

# 4. Verify
docker ps                       # spectra-backend healthy, spectra-frontend up
curl -s http://100.113.157.0:8080/api/health
curl -s http://100.113.157.0:8080/api/ready     # tracked-version-3
curl -s "http://100.113.157.0:8080/api/hardware?limit=1"   # Athlon Gold 7220C
```

Expected post-rollback state: identical to pre-cutover M2.5 production
(5380 hw, 1040 benchmarks, 7 conversations, schema v3). The 62 verified
SKUs published during the M3.3 window are **not** in the v3 backup; they
are re-publishable any time after re-upgrade via the same evidence-gated
pipeline (idempotent; proven in Phase 5 and R-3).

## 3. Rollback data-loss analysis

- Migrations v1→v4 are additive (no destructive DDL); the only data-risk
  operation is the DB **file swap** used in rollback, which reverts to the
  snapshot point. Any writes between snapshot and rollback are lost — this
  is why the cutover procedure takes a fresh backup immediately before the
  swap and the app is stopped (no writes possible during the window).
- Conversations/messages created between cutover and rollback are lost
  (accepted: the release window is minutes and chat is not yet user-facing
  critical; auth off, 0 users today).
- field_provenance additions from publication are re-derivable (idempotent
  rerun publishes 0 new rows when data already present).

## 4. Residual rollback risks

| Risk | Mitigation |
|---|---|
| Volume path confusion (root-owned volume) | use the alpine helper-container copy; never host-path mounts |
| RC image accidentally redeployed after v3 restore | rollback runbook step 3 pins the M2.5 image tag |
| Backup file corruption | backup + restore rehearsal + SHA256 recorded pre-cutover (Phase 3 method) |
| Split-brain (old frontend + new backend) | compose down/up the whole pair together |
