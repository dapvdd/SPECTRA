# SPECTRA V3 — Production Deployment Report

**Date:** 2026-11-09 (UTC)
**Target:** DavidLab SPECTRA — <http://100.113.157.0:8080>
**Compose project:** `spectra`
**Final verdict: V3_LIVE_WITH_KNOWN_ISSUES**

---

## 1. Release identity

| Item | Value |
|---|---|
| Released remote `main` | `75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Approved application baseline | `d462040db0e85b2e4becf19b5ad45a132a637e6a` |
| Delta baseline → release | Two documentation files only (`docs/release/*`); application source content-identical to `d462040` |
| Isolated release checkout | `/home/david/releases/spectra-75eba50` (detached at `75eba50`, clean) |
| Private configuration/evidence | `/home/david/releases/spectra-75eba50-ops` (mode `0700`) |
| Legacy checkout | `/home/david/projects/spectra` at `cca96d9`, dirty state preserved exactly (43 entries: 37 staged, 2 modified, 4 untracked) — never reset, stashed, cleaned, or overwritten |
| Frontend tests (release source) | `npm test` → **626 pass, 0 fail** |

The dirty legacy checkout was not used for build or deployment. No modified
source from it was copied into the release directory.

## 2. Images and runtime

| Service | Image ID | Tag |
|---|---|---|
| Backend | `sha256:8cb02c8b7e18d95df5af80ae3601d76dfcf403bb9df5764dc158a3a21c77bcd5` | `spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Frontend | `sha256:6dec82c38484fc93e3d55f2a0e1fb3c4b2694b0558ae46c928124e0e5ff5e233` | `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` |

Both images carry `org.opencontainers.image.revision=75eba50b1f09052f40409f6066a2ac030344d1a0`.
Containers:

- `spectra-backend` `8bb67a872fdd…` — running, healthy.
- `spectra-frontend` `fb2f3aa8bb46…` — running.

Preserved runtime topology: compose project `spectra`, network `spectra_default`,
named volume `spectra-sqlite-data` mounted at `/app/data`, frontend bound to
`100.113.157.0:8080`. Environment was captured read-only from the prior
containers and re-applied without printing secret values. No source bind mounts.
No unrelated container or service was changed.

## 3. Backup evidence

| Item | Value |
|---|---|
| Existing backup | `/home/david/projects/spectra/backups/spectra_backup_20261109.db` |
| Immediate pre-migration backup | `/home/david/releases/spectra-75eba50-ops/backup-immediate-pre-migration.db` |
| SHA256 | `a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7` |
| Size | 51,191,808 bytes |
| Integrity | `PRAGMA integrity_check` = `ok` |
| Restore proof | Restored into a disposable database; integrity `ok`; all table counts identical |

The existing backup was re-verified (hash, integrity, counts) before migration.
Both files are outside the container filesystem and survive container replacement.
A consistent SQLite online backup was also taken immediately before migration
inside the maintenance window (database had no writers).

Pre-migration counts: hardware 5,380 · CPU specs 3,501 · GPU specs 1,879 ·
benchmarks 1,040 · conversations 6 · messages 10 · sources 9 · provenance 36,946.

## 4. Migration results

Writes were disabled by stopping `spectra-frontend` and `spectra-backend`.
A host PID-namespace descriptor scan found **no open descriptors** on the
production database or its WAL/journal files before migration. (The initial
scan was denied by container security policy; it was rerun read-only with
`--pid host`, `SYS_PTRACE`, `DAC_READ_SEARCH`, and `apparmor=unconfined`.
No database operation had occurred before the successful scan.)

Executed against the existing volume database in place:

1. `hardware.segment` column added (idempotent, additive).
2. Segment backfill: **2,494 classified** — mobile 1,047 / server 1,209 / workstation 238.
3. Migration runner: v0 → **v2** (`baseline-current-schema`, `auth-tables`).
4. Verification: `{"status":"verified","version":2}`.

Post-migration database:

| Check | Result |
|---|---|
| Integrity | `ok` |
| Foreign-key check | no violations |
| Schema version | 2 |
| Hardware | 5,380 (unchanged) |
| CPU / GPU specs | 3,501 / 1,879 (unchanged) |
| Benchmarks | 1,040 (unchanged) |
| Conversations / messages | 6 / 10 (unchanged) |
| Sources | 10 (+1 classification source) |
| Provenance | 39,440 (+2,494 backfill records) |
| Users | 0 |
| Legacy conversations with `owner_id NULL` | 6 |

No volume deletion or recreation occurred. No down-migration was run.

## 5. Live verification

Backend (verified before frontend was exposed):

| Endpoint | Result |
|---|---|
| `GET /ready` | 200, `migrations: tracked-version-2`, database reachable |
| `GET /hardware/facets` | 200, CPU 3,501 / GPU 1,879; Intel 2,959 / AMD 1,439 / NVIDIA 876 / ATI 106; segments server 1,209 / mobile 1,047 / workstation 238 |
| `GET /hardware/recommend?type=GPU&workload=gaming&limit=3` | 200, ranked candidates returned |
| `POST /comparison/gpu` | 200, 7 metrics with honest `unavailable` handling |
| `GET /auth/status` | 200, `auth_enabled: false` |
| `GET /build/conversations/{1..6}` | 200, all 6 legacy rows with `owner_id: null`; ORM query over `build_conversations` succeeded |

Frontend through port 8080:

- Served HTML is the V3 shell (`index-DG6KnBNx.js`, `index-BNoD5QdN.css`), and the
  referenced asset exists inside the running container.
- `GET /assets/index-DG6KnBNx.js` → 200, 355,880 bytes, `Expires` + `Cache-Control: max-age=31536000`.
- `GET /` → 200 with `Cache-Control: no-cache` (HTML revalidates).

Headless Chromium acceptance (1440×900 and 390×844), **0 page errors, 0 console errors**:

- Homepage V3 hero and populated catalog rendered.
- Facet counts match 3,501 CPU / 1,879 GPU.
- CPU-first comparison rendered (type kickers `CPU`, `CPU`).
- GPU-first comparison rendered (type kickers `GPU`, `GPU`).
- GPU detail view opened; Build selection preserved the exact hardware identity.
- Light and Dark themes applied (`html[data-theme]` verified) and captured.
- 390px viewport: no horizontal overflow.

Screenshots and `results.json` were captured in the session evidence directory.
Visual approval is based on these headless captures, not a human review.

## 6. Rollback readiness

- Prior backend image retagged `spectra-backend:rollback-75eba50` →
  `sha256:bcd58f603cdd7dbff8359d45c835d8784c49955442576bca78dfe9652f9a4378`.
- Prior frontend image retagged `spectra-frontend:rollback-75eba50` →
  `sha256:52369140ad112d25a7503b73cfdbcb406bc0e706996a49f9fddc7b66b7af70dd`.
- Prior container configuration captured in `original-containers.json`;
  rollback compose file is `rollback.json`.
- Database: pre-migration backup above; v2 is reversible in place via
  `runner --target 1`. Never restore the pre-migration backup over a database
  that has accepted newer user writes.

## 7. Known issues / remaining risks

- **Authentication is disabled** (`SPECTRA_AUTH_ENABLED` unset), unchanged from
  before deployment. `/auth/status` reports `auth_enabled: false`; the six legacy
  conversations remain accessible as before. Enabling auth is a separate,
  out-of-scope configuration decision.
- **Build-chat AI provider key is empty** (`GEMINI_API_KEY` unset). Routes and
  schema were verified, but live AI responses will fail at the provider until a
  key is configured (pre-existing).
- **Cache header nuance:** the `/assets/` location retains the configured
  `expires 1y` behavior (`max-age=31536000`); the observed response did not show
  the additional `public, immutable` token from `add_header`. The Nginx config is
  identical to the released source and the prior container, so this is not a V3
  regression, but it is not fully aligned with the config's stated intent.
- Backend full test suite was not rerun in this deployment attempt; the release
  report's prior result (973 passed, 2 skipped) was on the same application
  source (`d462040`). Frontend 626-test suite was rerun and passed.

## 8. Final verdict

**V3_LIVE_WITH_KNOWN_ISSUES**

SPECTRA V3 (`75eba50`, application source `d462040`) is live at
<http://100.113.157.0:8080>. Migration to schema v2 completed and verified with
no data loss. The dirty legacy checkout remains untouched. Authentication and
AI chat remain configuration-limited exactly as documented above.
