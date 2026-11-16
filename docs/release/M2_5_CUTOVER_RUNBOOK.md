# SPECTRA M2.5 — Production Cutover Runbook (Phase H)

**Status:** Operator-ready plan. **Not executed.** Requires separate explicit authorization.
**Every command uses verified absolute paths and the exact Compose project `spectra`.** Nothing here touches other Docker projects.

## 0. Fixed inputs (all verified this audit)

| Item | Value |
|---|---|
| Release source | `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` (CI run #65 success) |
| Image options | (a) reuse staging-built images `spectra-backend:m25-staging-dcfd7df` (`cd5121964175…`) / `spectra-frontend:m25-staging-dcfd7df` (`0ae625ae32fd…`), **or** (b) rebuild at cutover from a fresh clone of the SHA — both trace to the same source; pick (a) for speed, (b) for freshness |
| Prod compose | `/home/david/releases/spectra-75eba50-ops/compose.json` (project `spectra`; volume `spectra-sqlite-data`; network `spectra_default`; port `100.113.157.0:8080:8080`) |
| Pre-cutover backup | `/home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-20261115T143818Z.db` (SHA-256 `801dd666…`) |
| Expected downtime | **≈ 30–60 s** measured basis: migration 4–7 s, container start ~2.4 s (+5 s `start_period`), compose replace 5–10 s, smoke < 10 s |
| New compose env (prod) | `SPECTRA_CORS_ORIGINS: http://100.113.157.0:8080,http://localhost:8080` (fixes stale list) · `SPECTRA_AUTH_ENABLED: "0"` (unchanged) · `SPECTRA_RELEASE_VERSION: "M2.5-production"` · `SPECTRA_RELEASE_SHA: dcfd7df…` · `SPECTRA_RELEASE_BUILT_AT: <build ts>` · `SPECTRA_IMAGE_DIGEST: <built image digest>` · `GEMINI_API_KEY`/`GEMINI_MODEL` unchanged |

## 1. Pre-cutover checklist (all must be ✅)

```bash
ssh david-lab
# ✅ provenance: staging release identity
curl -s http://100.113.157.0:8096/api/release | grep dcfd7df
# ✅ prod healthy baseline
curl -s http://100.113.157.0:8080/api/ready    # tracked-version-2
# ✅ pre-cutover backup present + hash match
sha256sum /home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-20261115T143818Z.db
# ✅ rollback images present
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep 75eba50b1f09052f40409f6066a2ac030344d1a0
# ✅ disk/mem headroom
df -h / | tail -1; free -h | head -2
# ✅ security header fix built into the chosen images (S-1) — verify:
docker exec spectra-m25-frontend sh -c 'grep -c add_header /etc/nginx/conf.d/default.conf'   # >= 3 (after fix build)
```

If the S-1 header fix has been built and staging-verified, cutover uses the fixed images; otherwise record an explicit waiver before proceeding.

## 2. Maintenance / write freeze

```bash
cd /home/david/releases/spectra-75eba50-ops
docker compose -p spectra -f compose.json stop frontend      # UI down first (users see connection refused)
docker compose -p spectra -f compose.json stop backend       # API down; DB now quiescent
```

(Precedent: the V3 deployment used the same stop-both freeze. SQLite `delete`-journal DB with no writers is quiescent.)

## 3. Fresh backup after write freeze (this is the rollback point)

```bash
docker cp /tmp/backup-tool.py spectra-backend:/tmp/backup-tool.py   # script runs sqlite3 backup API (Phase C pattern)
docker exec spectra-backend python3 /tmp/backup-tool.py             # writes /app/data/backup-<TS>.db, prints SHA-256
docker cp spectra-backend:/app/data/backup-<TS>.db /home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-<TS>.db
sha256sum /home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-<TS>.db   # must match printed hash
docker exec spectra-backend rm -f /app/data/backup-<TS>.db
chmod 600 /home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-<TS>.db
```

**Gate:** SHA-256 verified, integrity `ok`, counts match §Phase A baseline (hardware 5,380 / conv 7 / msgs 10 / users 0). Abort cutover on any mismatch.

## 4. Image verification

```bash
# whichever option was chosen:
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep dcfd7df        # (a) reuse
# or build fresh (option b, from a new clone at the SHA):
#   git clone --detach https://github.com/dapvdd/SPECTRA /home/david/releases/spectra-m25-prod-src
#   git -C /home/david/releases/spectra-m25-prod-src checkout dcfd7df3d77ba011bb92d8a3144615c5c3d373ec
#   docker build -f Dockerfile.backend -t spectra-backend:m25-prod-dcfd7df /home/david/releases/spectra-m25-prod-src
#   docker build -f Dockerfile.frontend -t spectra-frontend:m25-prod-dcfd7df /home/david/releases/spectra-m25-prod-src
```

Record final image IDs; they must match the staging evidence if reusing.

## 5. Production migration (v2 → v3, in place, after freeze)

```bash
# Run the versioned runner against the volume DB from a short-lived container
# (mount the same volume; the runner is additive + transactional + verified in rehearsal)
docker run --rm -v spectra-sqlite-data:/data -v /home/david/releases/spectra-m25-prod-src:/src -w /src python:3.13-slim \
  sh -c 'pip install -q -r requirements.txt && python3 backend/app/migrations/runner.py --database /data/spectra.db'
# expect: {"status":"upgraded","from_version":2,"to_version":3,...}
# verify:
docker run --rm -v spectra-sqlite-data:/data python:3.13-slim \
  python3 -c "import sqlite3;c=sqlite3.connect('/data/spectra.db');print(c.execute('PRAGMA integrity_check').fetchone(),c.execute('SELECT version FROM schema_version').fetchone())"
# expect: ('ok',) (1, 3)
```

**Gate:** version 3 + integrity ok + counts unchanged (run the count script from Phase C/D). Abort on failure → Rollback Runbook Strategy B (DB was not touched by new code yet).

## 6. Atomic Compose replacement (both services, one window)

```bash
cd /home/david/releases/spectra-75eba50-ops
# Edit compose.json image: lines to the M2.5 tags chosen in step 4 and add the env block from §0
docker compose -p spectra -f compose.json up -d --force-recreate    # replaces BOTH containers together
```

Atomicity rationale: new-FE + old-BE 422s on `/build/chat` (extra=forbid schema) — the mix is eliminated by replacing both in one command. Volume/network/port config is unchanged.

## 7. Health checks

```bash
docker ps --filter name=spectra --format '{{.Names}} {{.Status}}'    # both Up; backend (healthy)
curl -s http://100.113.157.0:8080/api/ready      # {"status":"ready",...,"migrations":"tracked-version-3"}
curl -s http://100.113.157.0:8080/api/release    # version M2.5-production, sha dcfd7df…, digest filled
curl -sI http://100.113.157.0:8080/ | grep -iE 'x-frame|content-type-options|referrer'   # S-1 headers present
```

**Gate:** three consecutive healthy cycles (30 s).

## 8. API smoke tests

```bash
curl -s 'http://100.113.157.0:8080/api/hardware?limit=1'                  # 200, item id 1
curl -s http://100.113.157.0:8080/api/hardware/facets                      # CPU 3501 / GPU 1879 (+ fixtures if loaded)
curl -s http://100.113.157.0:8080/api/auth/status                          # auth_enabled false
curl -s -X POST http://100.113.157.0:8080/api/build/compatibility/check \
     -H 'Content-Type: application/json' -d '{"cpu":705}' | head -c 200    # 200, rules_version M2.5-RULES-v1
```

## 9. Six-category UI acceptance (browser, hard reload)

- `GET /` → explore view shows **six** category tabs: All hardware / CPU 3501 / GPU 1879 / RAM / Storage / Motherboard / PSU (counts per prod data).
- Build Planner: six slot cards + six Browse buttons; select CPU+GPU → compatibility panel populates; `rules_version` chip correct.
- Detail pages open for one item per category (RAM/Storage/Motherboard/PSU included).
- 0 console errors. (DOM-check script from staging can be pointed at 8080 for 24/24 re-run.)

## 10. Compatibility acceptance

- One CPU+GPU+Motherboard+PSU build → expected verdict (e.g. 705 + 5119 + 5386 + 5388 on staging fixtures shows INCOMPATIBLE PSU rule semantics; use prod-equivalent ids present in prod data).
- AI context: `/api/build/chat` with a build → 503 "Gemini API is not configured" (unchanged, expected).

## 11. AI context verification

- Confirm provider state in `/api/release` (`ai_provider: unconfigured` unless key configured) and that chat endpoints fail closed with the safe message (no key leakage).

## 12. Post-cutover database validation

```bash
docker exec spectra-backend python3 - <<'EOF'
import sqlite3
c = sqlite3.connect('file:/app/data/spectra.db?mode=ro', uri=True)
print('integrity', c.execute('PRAGMA integrity_check').fetchone())
print('fk', c.execute('PRAGMA foreign_key_check').fetchall())
print('version', c.execute('SELECT version FROM schema_version').fetchone())
print('hw', c.execute('SELECT COUNT(*) FROM hardware').fetchone())
EOF
# expect ok / [] / (1,3) / 5380 — then create a probe conversation via API and delete it
```

## 13. Rollback decision criteria

See Rollback Runbook §1 triggers (health, 5xx, catalog counts, rules_version, DOM, persistence). Decision window: first 30 minutes post-cutover with traffic.

## 14. Rollback commands

One-liners referencing the Rollback Runbook:
- Strategy A: `cd /home/david/releases/spectra-75eba50-ops && docker compose -p spectra -f compose.json stop backend frontend && <restore 75eba50 image lines> && docker compose -p spectra -f compose.json up -d --force-recreate`
- Strategy B: same freeze, then the volume-restore `docker run --rm -v spectra-sqlite-data:/data -v /home/david/backups/spectra:/bk alpine …` command, then start old stack.
- **Never** `--target 1` on prod.

## 15. Post-release monitoring

- First hour: poll `/api/ready` + `/api/release` every 5 min; watch `docker logs spectra-backend --since 30m` for tracebacks; check `/api/metrics` status-class counters (new endpoint).
- 24 h: re-run counts + integrity; confirm conversation writes land (create→read→delete probe); disk delta of DB (+5.2 MB expected).

## 16. Final sign-off

Record in this repo's `docs/release/`: cutover timestamp, image IDs, backup SHA, migration output, smoke results, monitoring window result, and explicit sign-off by the authorizing operator. Update `M2_5_PRODUCTION_READINESS.md` verdict from `CONDITIONAL_GO`/`GO…PENDING` to `CUT_OVER_COMPLETE` with evidence links.
