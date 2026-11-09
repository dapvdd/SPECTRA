# SPECTRA V3 — Production Release Report

**Date:** 2026-11-09
**Target:** DavidLab SPECTRA (port 8080, compose project `spectra` at `/home/david/projects/spectra`)
**Final verdict: MERGED_DEPLOYMENT_BLOCKED**

The release was merged and pushed, but deployment was stopped before any
production change. The V3 frontend requires the newer backend
(`/comparison/gpu`); replacing the backend requires the schema v2 production
migration, which is gated behind a separate explicit approval per the release
authorization ("Do not treat this as authorization to destroy or replace
production data"; Phase 3 stop rule).

---

## 1. Merge (Phase 2) — COMPLETE

| Item | Value |
|---|---|
| Source branch | `feat/spectra-v3-phase-g-premium-polish` |
| Approved source HEAD | `d462040db0e85b2e4becf19b5ad45a132a637e6a` |
| Working tree at merge | clean |
| Pre-merge `origin/main` | `f0e377dce841cf8d9d9f40c3aeac354e42cdc115` (verified ancestor → fast-forward eligible) |
| Merge mode | `git merge --ff-only` (no merge commit, no squash, no force) |
| Resulting main SHA | `d462040db0e85b2e4becf19b5ad45a132a637e6a` |
| Push | `f0e377d..d462040 main -> main` (verified: `origin/main` = `d462040`) |

Release-gate evidence on merged main:

- Frontend: `npm test` → **626 pass, 0 fail**.
- Backend: `python -m pytest backend/ -q` → **973 passed, 2 skipped**
  (the only 2 failures during earlier runs were environment artifacts: the
  local `data/spectra.db` was schema v2 while tests expect the v1 template;
  reproduced-then-resolved with a v1 copy, see §4).
- Phase G changed **zero** backend files vs prior main
  (`git diff f0e377d..d462040 --stat -- backend/ Dockerfile.backend
  requirements.txt compose.yaml` is empty) and added **no new API calls**
  beyond tests.

## 2. Production state at report time (untouched)

| Item | Value |
|---|---|
| `spectra-frontend` | container `bcaf420cb171…`, image `52369140ad11` (built 2026-11-08), Up 33h |
| `spectra-backend` | container `206e172b9633…`, image `bcd58f603cdd` (built **2026-10-14**), Up 2 weeks, healthy |
| Serves | frontend `100.113.157.0:8080`; backend internal-only, nginx proxies `/api/` → `backend:8000` |
| Database | `spectra-sqlite-data` volume → `/app/data/spectra.db` (SQLite) |
| DB sha256 | `327c40caf7562f398da8585de9c9e6c63a01924daab824178470a402245ae822` (51,191,808 bytes; identical before and after this session) |
| DB integrity | `PRAGMA integrity_check` = ok (read-only connection) |
| DB contents | 9 tables; hardware 5,380 / cpu 3,501 / gpu 1,879 / benchmarks 1,040 / conversations 6 / messages 10 / sources 9 |
| Disk | 744G free |
| Rollback images | `spectra-frontend:rollback-pre-cachepolicy-20261108` (`8fe6b0501905`), `spectra-frontend:rollback-pre-v3-20261108` (`0d33d2ebfcdd`) |

## 3. Backend compatibility result (Phase 3)

Production backend predates the V2 merge (`647272d`, PR #1) and lacks:

| Endpoint | V3 frontend usage | Old backend |
|---|---|---|
| `POST /comparison/gpu` | **flagship two-slot GPU comparison workspace** | 404 |
| `GET /hardware/facets` | catalog type/manufacturer counts | 404 |
| `POST /hardware/recommend` | recommendation hooks | 404 |

Degradation audit (App.jsx:3202–3213, 2563–2570): facets failures are silently
caught (stale/empty counts), but GPU-comparison failure renders an explicit
**error state** in the Phase F/G headline workspace. A frontend-only deploy
would knowingly ship a broken flagship feature → rejected per Phase 6
("do not mask the incompatibility").

Fact: the **currently deployed** frontend bundle
(`assets/index-qdrmLzgf.js`, Nov 8) already calls `/hardware/facets` and
`/hardware/recommend` — production is already partially degraded today. The V3
deploy adds no *new* incompatibility class, but the GPU-comparison error state
is new user-visible breakage.

**Minimum compatible backend revision:** current `main` backend at `d462040`
(contains facets, gpu comparison, recommend, auth; requirements adds
bcrypt/httpx; remote's deploy-only local commits — uvicorn pin, nginx proxy
route — are content-identical in `origin/main`'s Dockerfiles/requirements).

## 4. Migration analysis and rehearsal (no production writes)

ORM-vs-production schema gap (exact, script-verified):
`hardware.segment`, `build_conversations.owner_id`, plus the `users` table
(v2). Production DB has no `schema_version` tracking (pre-Batch-017 state).

**New backend + un-migrated DB breaks build chat**: the ORM selects `owner_id`
→ `OperationalError` on `/build/chat` and conversation routes. Migration is a
hard prerequisite of the backend swap, not optional.

Order matters — the runner's v1 baseline expects Batch-017 columns already
present. Rehearsed **end-to-end on a disposable copy of production**
(`spectra_backup_20261109.db` → rehearsal copy):

1. `add_hardware_segment --database <copy>` → column added, verification passed.
2. `backfill_segment --apply` (defaults to `data/spectra.db`; pointed at the
   rehearsal copy in the documented procedure) → 2,494 classified
   (mobile 1047 / server 1209 / workstation 238), idempotent, self-backup.
3. `runner upgrade --database <copy>` → applied v1 `baseline-current-schema`
   + v2 `auth-tables` (users table, nullable `owner_id`, index); legacy rows
   keep `owner_id=NULL`.
4. `runner --verify` → `{"status": "verified", "version": 2}`.

Live rehearsal of the new backend from merged `main` against the migrated
copy (local uvicorn, disposable DB):

- `/health` 200; `/ready` → `{"status":"ready","database":"reachable",
  "migrations":"tracked-version-2"}`.
- `GET /hardware/facets` → 200 with exact production counts
  (CPU 3,501 / GPU 1,879; Intel 2,959 / AMD 1,439 / NVIDIA 876 / ATI 106).
- `POST /comparison/gpu` (real GPU ids 3361/3362) → 200, 826-byte payload.
- `/build/chat` reached the AI provider path (502 provider failure with no
  `GEMINI_API_KEY` in rehearsal — route, auth dependency, and DB access all
  exercised; no schema errors).

Both migrations are additive; v2 is reversible via
`runner --target 1` (drops index, column, users table). Full-suite rerun on
merged main with a v1-copy database template: **973 passed, 2 skipped**.

## 5. Database backup (Phase 1) — COMPLETE, production untouched

- Method: SQLite `src.backup(dst)` **inside the backend container** (consistent
  snapshot), then `docker cp` out. Original never written.
- File: `/home/david/projects/spectra/backups/spectra_backup_20261109.db`
- sha256: `a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7`
- Verified: integrity ok; hardware 5,380 / conversations 6 / messages 10 —
  matches production exactly.

## 6. Rollback references (all pre-staged, nothing executed)

- Frontend image: retag current `52369140ad11` → redeploy (or use
  `rollback-pre-cachepolicy-20261108`).
- Backend image: current `bcd58f603cdd` still tagged `spectra-backend:latest`.
- Database: `backups/spectra_backup_20261109.db` (pre-migration). Never restore
  it over a post-migration DB that has accepted new writes; v2 is also
  reversible in place via `runner --target 1`.

## 7. Required approval to complete deployment

Deployment is blocked pending one explicit approval covering this exact plan:

1. `docker compose pull`/fetch `main@d462040` on DavidLab; reconcile the
   deploy checkout (local uncommitted edits duplicate origin/main content;
   deploy-only commits already incorporated upstream — plan: reset to
   `origin/main`, preserving the checkout's local history for reference).
2. Rebuild backend image from `d462040`; tag old `bcd58f603cdd` →
   `spectra-backend:rollback-pre-v3-migration-20261109`.
3. Stop backend, apply migrations **in-place on the volume DB** (verified
   sequence §4; backup + rollback staged), restart backend.
4. Rebuild frontend image from `d462040`; retag `52369140ad11` →
   `rollback-pre-v3-20261109-full`; deploy frontend only.
5. Live verification: Phase 5 checklist (assets hash-matched to `d462040`,
   themes, hero, catalog search/filter/sort, CPU/GPU detail, GPU-first
   comparison, build selection, two-slot comparison, facets, console, 390px).
6. Rollback on failure: restore prior images; DB handled per §6 rules.

## 8. Remaining defects / risks

- GPU comparison + facets + recommend are 404 on the old backend (pre-existing;
  degrades silently today, would error-state visibly on V3 frontend-only).
- Auth endpoints exist on new backend but `SPECTRA_AUTH_ENABLED` is unset in
  production env → auth OFF; legacy conversations (owner NULL) accessible as
  today. Enabling auth later needs `GEMINI_API_KEY`-style env handling and
  secret management (out of scope).
- `build/chat` requires `GEMINI_API_KEY`; production compose passes an empty
  default → AI chat fails 502 until the key is provided (pre-existing).
