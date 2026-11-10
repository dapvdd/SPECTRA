# SPECTRA V3.1 — Baseline Audit (Phase 0)

Date: 2026-11-10
Auditor: Crown AI (GLM 5.3 Flash) — Operation SPECTRA V3.1
Scope: Phase 0 baseline discovery; read-only production inspection; no production mutation.

---

## 1. Source baseline

| Item | Value | Evidence |
|---|---|---|
| Local checkout | `C:\Users\user\spectra-local` | working tree clean (`git status --porcelain=v1` empty) |
| Local branch | `main` at `06e14da4c42c5a5274d9e09b769310b6a4ce3cca` | `git rev-parse HEAD` |
| `origin/main` | `06e14da4c42c5a5274d9e09b769310b6a4ce3cca` (same) | `git fetch origin; git rev-parse origin/main` |
| Remote | `https://github.com/dapvdd/SPECTRA.git` | `git remote -v` |
| Unmerged feature branches | `feat/spectra-v3-experience-reconstruction`, `feat/spectra-v3-hardware-experience`, `feat/spectra-v3-neural-luxury`, `feat/spectra-v3-phase-g-premium-polish` | `git branch -a` — none merged into `main`; historical V3 work, superseded by the deployed release |
| Previously deployed release | `75eba50b1f09052f40409f6066a2ac030344d1a0` | historical; see §3 — this SHA is the **deployed** release but **not** the `main` HEAD |

Note: `main` HEAD (06e14da) contains documentation-only commits after the deployed
release SHA (75eba50). The deployed images were built from 75eba50; subsequent main
commits are docs-only and do not change runtime behaviour.

## 2. Local test baseline (pre-change)

| Suite | Result | Command |
|---|---|---|
| Backend pytest | **971 passed, 2 skipped, 2 deselected** in 25.6 s | `python -m pytest backend -q …` (CI's ignore/deselect list) |
| Frontend node --test | **626 passed, 0 failed** in 0.93 s | `node --test src/*.test.js` |
| Frontend oxlint | 0 errors, 3 pre-existing warnings (`set-state-in-effect` in `App.jsx`, `useRecommendation.js`, `useSuitability.js`) | `npx oxlint src` |
| Frontend production build | **success** — `dist/index.html 2.77 kB`, `index-*.css 122.72 kB`, `index-*.js 355.88 kB` | `npx vite build` |

Skipped backend tests are AI-gated (require a real `GEMINI_API_KEY`); deselected are
Docker-persistence cycle tests that require a container runtime.

## 3. Production audit (read-only, via `ssh david-lab`)

### 3.1 Containers

| Container | Image | Status | Restart count |
|---|---|---|---|
| `spectra-frontend` | `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` | Up 10 h | 0 |
| `spectra-backend` | `spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0` | Up 10 h (healthy) | 0 |

- Compose project: `spectra`; config file: `/home/david/releases/spectra-75eba50-ops/compose.json`; working dir: `/home/david/releases/spectra-75eba50-ops`.
- Images carry the org label `org.opencontainers.image.revision=75eba50b1f09052f40409f6066a2ac030344d1a0`.
- `docker events` over the last 48 h shows only the backend health check's
  `curl` subprocess exiting (exit 0) every 10 s — no container restarts, no dies.

### 3.2 Ports and exposure

- `spectra-frontend`: publishes `100.113.157.0:8080 -> 8080` (Tailscale IP only, via
  `/home/david/projects/spectra/compose.override.yaml` style `!override` in the ops
  compose — the compose.json records the resolved port mapping).
- `spectra-backend`: no host port published; reachable only on the Compose internal
  network (`8000/tcp`) and through nginx `/api/` proxy.
- Production URL: `http://100.113.157.0:8080/`.

### 3.3 Database (read-only inspection inside `spectra-backend`)

Python sqlite3 read-only queries against `/app/data/spectra.db` (51,191,808 bytes,
volume `spectra-sqlite-data`):

```
integrity: ok            (PRAGMA integrity_check)
hardware: 5380
cpus:     3501
gpus:     1879
migration: 2             (schema_version)
conversations: 6
users: 0
```

Matches the reported baseline exactly. **No production data was modified.**

### 3.4 Runtime configuration (non-secret values only)

`spectra-backend` environment (as resolved in the container):

| Variable | Value | Assessment |
|---|---|---|
| `SPECTRA_DATABASE_URL` | `sqlite:////app/data/spectra.db` | OK |
| `SPECTRA_CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173` | Localhost only; benign for same-origin browser use through nginx (see F-05) |
| `GEMINI_API_KEY` | *(empty)* | AI provider unconfigured — confirmed |
| `GEMINI_MODEL` | *(empty)* | AI provider unconfigured — confirmed |
| `SPECTRA_AUTH_ENABLED` | *(unset → default off)* | Auth disabled — confirmed |
| `SPECTRA_AUTH_SECRET` | *(unset)* | Token verification would fail closed (401) if auth were enabled without it — fail-closed behaviour is correct |
| `SPECTRA_RATE_LIMIT_ENABLED` | *(unset → disabled)* | Rate limiting opt-in, currently off |

`spectra-frontend` environment: build-time only (`VITE_API_BASE_URL=/api` baked into the
bundle at image build time); no runtime secrets.

### 3.5 Live HTTP behaviour

| Probe | Result |
|---|---|
| `GET /api/health` (through nginx) | `200` `{"status":"healthy"}` |
| `GET /api/ready` | `200` `{"status":"ready","database":"reachable","migrations":"tracked-version-2"}` |
| `GET /api/auth/status` | `200` `{"auth_enabled":false}` |
| `GET /api/` | `200` `{"message":"Welcome to SPECTRA API","status":"online"}` |
| `GET /` (HTML shell) | `200`, `Cache-Control: no-cache`, `ETag: "6af1f5a7-a98"` — revalidated on every load |
| `GET /assets/index-DG6KnBNx.js` | `200`, `Cache-Control: max-age=31536000` **and** `public, immutable`, `Expires: +1 year`, `ETag "6af1f5a7-56e28"` |

**ISSUE 3 (frontend cache headers) is already resolved in the deployed release:** hashed
assets carry both `max-age=31536000` and `public, immutable`; the HTML shell is
`no-cache`. The current `Dockerfile.frontend` in the repository produces exactly this
behaviour.

### 3.6 Backup posture (observed, not modified)

| Item | Finding |
|---|---|
| `/home/david/projects/spectra/backups/` | `spectra_backup_20261109.db` (51,191,808 bytes — same size as the live DB, consistent with a full copy) |
| `/home/david/releases/spectra-75eba50-ops/` | Release-day backups: `backup-20261109T162847Z.db`, `backup-immediate-pre-migration.db`, `restore-proof-20261109T162847Z.db`, `restore-immediate-proof.db` |
| Scheduled backups | **None for SPECTRA.** Host crontab has only the DavidLab cloud-storage job (`30 3 * * * …/davidlab-cloud-storage/backup.sh`), which does not cover `/home/david/projects/spectra/backups/` |

### 3.7 Release checkout topology

| Path | Role | State |
|---|---|---|
| `/home/david/releases/spectra-75eba50` | Release source checkout (immutable reference) | clean |
| `/home/david/releases/spectra-75eba50-ops` | Active deployment dir (compose.json, evidence, backups) | operational |
| `/home/david/projects/spectra` | **Legacy dirty checkout** | dirty (see §4, F-04) |

## 4. Known-issue verification

| # | Reported issue | Verified? | Detail |
|---|---|---|---|
| 1 | Authentication disabled | **Confirmed** | `SPECTRA_AUTH_ENABLED` unset; `/api/auth/status` → `auth_enabled: false`; `users` table has 0 rows |
| 2 | AI provider unavailable | **Confirmed** | `GEMINI_API_KEY` and `GEMINI_MODEL` both empty in the backend container |
| 3 | Frontend cache headers missing `public, immutable` | **Already resolved** | Live assets now send both `max-age=31536000` and `public, immutable`; HTML is `no-cache` (§3.5). Root cause (pre-cache-policy image) is tagged and retained as `spectra-frontend:rollback-pre-cachepolicy-20261108` |
| 4 | Legacy deployment takeover risk | **Confirmed** | Legacy checkout `/home/david/projects/spectra` ships the same `compose.yaml` with `container_name: spectra-backend`/`spectra-frontend`, project name `spectra`, and port 8080. `docker compose up -d` from there would collide with the running release (same project + container names). Its working tree is dirty (modified `Dockerfile.frontend`, `App.jsx`, `comparison.py`, new `buildCompatibility.js`, etc.) — building from it would also deploy unreviewed code |
| 5 | Mutable image tag risk | **Partially resolved** | Production runs SHA-tagged images, not `latest`. However, `spectra-backend:latest` (image `bcd58f603cdd`) still exists locally on the host and points at a different ID than the running release image (`8cb02c8b7e18`) — a latent rollback-downgrade hazard if anything deploys from `latest` |
| 6 | Browser release identification | **Confirmed (historical)** | The stale-tab incident motivated the shipped `Cache-Control: no-cache` on the HTML shell and ETag revalidation, which are now live. Remaining gap: no explicit release-identity surface for diagnostics (addressed in M2) |

## 5. Findings and risk register (Phase 0 scope)

Severity is assessed by operational impact and exploitability, not tool labels.

| ID | Finding | Component | Severity | Likelihood | Mitigation direction | Approval needed |
|---|---|---|---|---|---|---|
| F-01 | Auth disabled in production; write endpoints (`/build/*`) accept anonymous traffic. When `SPECTRA_AUTH_ENABLED=0`, `require_auth` returns `None` (guest) and ownership scoping is skipped — every caller shares every conversation. Rate limiting is also off. | backend auth, deployment | P1 (data integrity/privacy on a Tailscale-exposed host; exploitability requires LAN access) | Medium | Enable auth with secret + run migration v2 — requires production change approval (M1 prepares everything; activation stays user-gated) | Yes (activation) |
| F-02 | `spectra-backend:latest` and `spectra-frontend:latest` tags exist on the host and point at non-release image IDs; any automation or human `docker compose up` with `image: …:latest` in scope would silently downgrade. | host image store, deploy tooling | P2 | Low (running compose.json pins SHA tags) | Deployment preflight rejects `latest`; release docs mandate SHA tags; do not retag in this operation | No (tooling-side) |
| F-03 | Legacy checkout shares Compose project name `spectra`, container names, and port 8080 with production; tree is dirty. | legacy checkout, deploy tooling | P2 | Low-Medium (one command away) | Preflight detects project/port/container-name collisions and refuses to deploy from a dirty tree (M2.3); legacy file itself untouched | No (tooling-side) |
| F-04 | No scheduled SPECTRA backup; existing backups are release-day artefacts, not recurring. DB is 49 MB and growing with conversations. | ops | P1 (data loss window = time since last manual backup) | Medium | M3 backup tooling + retention + restore rehearsal; scheduling on the host remains a documented, user-approved step | Yes (host cron) |
| F-05 | `SPECTRA_CORS_ORIGINS` lists only localhost origins while the app is served from `100.113.157.0:8080`. Browser use is same-origin (nginx proxies `/api/`), so CORS never bites for normal use; but any future cross-origin client (or direct-origin API use) would be blocked. | backend config | P3 | Low | Document; allow-list the production origin at activation time (env change → user approval) | Yes (at activation) |
| F-06 | Duplicate route decorator on `/hardware/chat` in `backend/app/main.py` (lines 750-757) — the first decorator is shadowed. Harmless at runtime (single route registered) but a latent edit hazard. | backend code | P3 | — | Remove the duplicated decorator (M2 scope creep guard: safe cleanup) | No |
| F-07 | `verify_token` has no revocation story beyond expiry and user-deletion; tokens are stateless bearer credentials with a 24 h TTL. Acceptable for the threat model (self-hosted, Tailscale), but account recovery/bootstrap needs design (M1.5). | backend auth | P2 | — | Design + test admin bootstrap; document token lifecycle | No (code-side) |
| F-08 | `users` table empty; no admin exists. Enabling auth without a bootstrap path would lock out all users (no one can log in). | backend auth | P1 (blocks F-01 activation) | High (certain at activation time) | M1.5 bootstrap mechanism + rehearsal | No (code-side) |
| F-09 | `docker events` shows the backend health check passing every 10 s for 10+ hours; healthcheck only probes `/health` (process liveness), not `/ready` (DB + migrations). | ops | P3 | — | Document; add `/ready`-based container healthcheck at next image build (requires deployment approval to change running compose) | Yes (deployment) |
| F-10 | Frontend bundle served with a content hash but no `X-SPECTRA-Release` or equivalent diagnostic header; stale-tab diagnosis relies on comparing asset URLs manually. | observability | P3 | — | M2.5 release-identity diagnostic surface | No |

## 6. Code-quality observations (non-findings, fix opportunistically)

- `backend/app/main.py` duplicates the `@app.post("/hardware/chat")` decorator block —
  single registration results, but the duplication invites divergent edits (F-06).
- Pre-existing oxlint warnings: 3 × `set-state-in-effect` (see §2). Not security-relevant;
  out of V3.1 scope to redesign hooks.

## 7. Phase 0 exit gate

| Gate | Status |
|---|---|
| Actual baseline verified (source + remote) | **PASS** |
| Production topology understood (containers, ports, volumes, checkouts) | **PASS** |
| Known issues reproduced or explicitly marked unconfirmed | **PASS** (all 6 addressed in §4) |
| No production state modified | **PASS** — all remote commands were read-only (`docker inspect/ps/images/events`, `curl -I/-s GET`, `ls`, `grep`, sqlite read-only queries via `docker exec … python -c`) |
| Findings documented with evidence | **PASS** (§5) |

**Phase 0: PASS.** Proceeding to M1 (authentication hardening) on branch
`feat/spectra-v3.1-production-hardening`.
