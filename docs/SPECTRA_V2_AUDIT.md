# SPECTRA V2 — Repository & Production Audit

**Date:** 2026-10-30
**Audited repository:** `C:\Users\user\spectra-local`
**Remote:** `https://github.com/dapvdd/SPECTRA.git`
**Audited revision:** `89473bb` (`feature/spectra-delivery-20261028`, HEAD)
**Method:** Read-only inspection of the working tree, Git history, Docker configuration, database copies, and fresh verification runs. No production database, container, or deployment was modified. No credentials were exposed.

---

## 1. Repository state & revision control

### 1.1 Confirmed Git state (verified at audit time)

| Item | Value |
|---|---|
| Current branch | `feature/spectra-delivery-20261028` |
| HEAD | `89473bb` (`feat(batch018): production migration readiness - rehearse on isolated copy`) |
| Working tree | Clean for tracked files |
| Untracked | 20 files (19 `data/research/*.py` audit scripts + `docs/DATA_COMPLETENESS_BASELINE.md`) — preserved unchanged |
| Origin HEAD (feature branch) | `89473bb` — in sync (`git ls-remote` confirmed) |
| Origin `main` | `2297c7d` |
| Commits ahead of `main` | 7 |
| Tags | None |
| CI/CD | None found (no `.github/workflows`, no pipeline config) |

**Confirmed:** the feature branch is pushed and in sync with the GitHub remote. `main` is 7 commits behind. The feature branch is the authoritative integration line for the recent delivery work (segment model, opt-in rate limiter, Batch 018 readiness).

**Assumed (not verified live):** GitHub pull-request state and full per-branch merge history beyond the branch tip.

### 1.2 Deployment revision (assumption, not re-verified live)

`docs/SPECTRA_SYSTEM_AUDIT.md` (2026-10-28) records the DavidLab server checked out at `cca96d9` with uncommitted comparison work identical to upstream `70bf68c`. The deployed revision **was not re-verified live** in this audit (no SSH/container access taken). Treat the deployed revision as `cca96d9`-era **or newer**, per that prior document. The deployed revision must be re-checked before any V2 deployment step.

---

## 2. Architecture (confirmed from source)

```
React 19 + Vite 8 (SPA)          FastAPI (Uvicorn)             SQLite
 frontend/src/App.jsx       -->   backend/app/main.py    -->   data/spectra.db
        |                          |  |  |  |  |
        |                    services schemas models migrations importers
        +-- API (fetch) --->       |  |
                                  +-- Gemini REST (AI endpoints only)
```

- **Frontend:** React 19 + Vite 8, plain JavaScript (no TypeScript), `.jsx` modules per concern, Node's built-in test runner (`node --test`), Oxlint, single monolithic `App.jsx` (~3,300 lines) plus per-concern logic modules.
- **Backend:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 declarative, SQLite, `pytest`/`unittest`.
- **AI:** Google Gemini REST via a single `GeminiProvider` (retries, redacted logging, 30s timeout). Three AI endpoints + persistent build conversations.
- **Deployment:** Docker Compose (`compose.yaml`) with backend + frontend (Nginx), named volume `spectra-sqlite-data`, healthcheck, entrypoint template-DB initialization.

Confirmed at the DB layer: 9 tables (`hardware`, `cpu_specifications`, `gpu_specifications`, `benchmark_results`, `sources`, `field_provenance`, `external_identifiers`, `build_conversations`, `build_messages`).

---

## 3. Database schema (confirmed)

| Table | Purpose | Notes |
|---|---|---|
| `hardware` | identity: name, manufacturer, type, release_date, architecture, segment | `type` constrained by app convention (`CPU`/`GPU`); `segment` from Batch 017 |
| `cpu_specifications` | cores, threads, base/boost clock GHz, TDP W, process node nm, socket | 1:1 with hardware |
| `gpu_specifications` | memory GB, memory type, clocks MHz, bandwidth GB/s, bus width bits, TDP W, interface, length mm | 1:1 with hardware |
| `benchmark_results` | benchmark_name, score, unit, test_type, source_id, recorded_at | 1:N; all Geekbench 7 CPU |
| `sources` | name, url, publisher, description, license_*, terms_notes, attribution, retrieved_on | 10 rows |
| `field_provenance` | field-level evidence log (source_id, table_name, field_name, evidenced_value, confidence, evidence_status, match_method, batch_no, ...) | additive; never mutates values |
| `external_identifiers` | external_id, identifier_type, source_id | unique per hardware+source+type+id |
| `build_conversations` / `build_messages` | persistent build chat, keyed by CPU+GPU pair | 1:N messages |

**Migration approach:** no Alembic. Additive `ALTER TABLE` scripts run manually (`backend/app/migrations/*.py`), each standalone and mostly idempotent. No version table, no version-aware runner, no automated migration pipeline.

---

## 4. Dataset inventory & quality (confirmed from DB copies)

### 4.1 Catalog

| Dataset | Local `spectra.db` | Staging `spectra_staging.db` |
|---|---:|---:|
| `hardware` | 5,380 | 5,380 |
| CPU | 3,501 | 3,501 |
| GPU | 1,879 | 1,879 |
| `benchmark_results` | 1,040 | 1,040 |
| `sources` | 10 | 10 |
| `field_provenance` | 39,440 | 40,405 |
| `external_identifiers` | 3,575 | 3,575 |
| `build_conversations` / `build_messages` | 6 / 10 | 6 / 10 |

**Batch 018 status (confirmed):**
- Local `spectra.db`: **0** `batch_no=18` provenance rows (Batch 018 NOT applied).
- Staging `spectra_staging.db`: **965** `batch_no=18` provenance rows (Batch 018 applied to staging only).
- Production: **not touched** — per `docs/MIGRATION_READINESS_BATCH018.md`, Batch 018 is **rehearsed only**, awaiting explicit approval. Production baseline hash recorded as `327c40ca…ae822`.

This is the single most important reconciliation finding: **staging has Batch 018 (interface 95.1%, bus width 78.2%); local `spectra.db` is at the pre-Batch-018 baseline (interface 45.2%, bus width 76.8%)**.

### 4.2 Benchmark dataset

- All 1,040 results are **Geekbench 7**, split single-core / multi-core, **all CPU**.
- **0 GPU benchmark results** — deliberate, documented product decision (no source met licensing + provenance + accessibility + semantics + identity + reproducibility).
- Only 518/5,380 hardware rows have any benchmark (~9.6%).

### 4.3 Field coverage (validated, from `docs/HARDWARE_DATA_COVERAGE.md` + `COVERAGE_VERIFIED.md`)

- CPU strongest: `cores` 99.9%, `socket` 94.6%, `base_clock` 93.5%. Weakest: `boost_clock_ghz` 69.3%, `process_node_nm` 70.6%.
- GPU strongest: `memory_type` 100%, `core_clock` 99.8%. Weakest: `length_mm` 40.8% (pre-Batch-018 `interface` 45.2%; 95.1% with Batch 018).
- 20 hardware rows have **no provenance** (reported `unattributed`, never guessed).
- 2 `rejected`-confidence and 60 NULL-confidence provenance rows should be re-audited.
- 46 CPU rows carry bare model numbers ("980", "6376") with no full product name.

### 4.4 Source registry (confirmed, 10 sources)

Licence statuses: 3 `clear` (GPU Ark CC BY 4.0, Wikipedia CC BY-SA 4.0, derived naming conventions), 4 `unknown` (Geekbench, Intel ARK x2, AMD), 1 `restricted` (PassMark), 1 `unresolved` (legacy unknown), 1 `restricted` (TechPowerUp). Honest license discipline is a core project strength.

---

## 5. API surface (confirmed from `backend/app/main.py`)

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /`, `GET /health` | welcome, liveness | healthy, deterministic |
| `GET /hardware?type=` | catalog list | **no response_model** (inline dicts), no pagination, no search, no release_date/architecture |
| `GET /hardware/{id}` | detail + specs | **returns HTTP 200 `{"error":...}` on missing hardware** instead of a 404 — inconsistent contract |
| `GET /hardware/{id}/benchmarks` | benchmarks + filters | 404s properly |
| `GET /sources`, `GET /sources/{id}` | source transparency | 404s properly |
| `GET /hardware/{id}/provenance` | field provenance | 404s properly |
| `GET /benchmarks/{id}/provenance` | benchmark provenance | 404s properly |
| `POST /comparison/explanation` | AI explanation | needs Gemini |
| `POST /hardware/chat` | AI hardware chat | needs Gemini |
| `POST /build/chat` | AI build chat | needs Gemini |
| `POST/GET /build/conversations…` | persistent build conversations | create-or-reuse, type-safe build identity |

**Backend comparison gaps:** `comparison_service.py` only compares CPUs (cores, threads, base/boost clock, TDP, power-efficiency). **There is no backend GPU comparison route** — GPU comparison is entirely client-side in `frontend/src/comparison.js`.

---

## 6. Authentication, authorization, security (confirmed)

- **No authentication.** API is unauthenticated by design; no users, tokens, ownership, or RBAC. `PRODUCTION_READINESS.md` states this explicitly.
- **Rate limiting:** opt-in middleware exists (`SPECTRA_RATE_LIMIT_ENABLED=1`), per-IP fixed-window, AI/public classes, 429 + Retry-After. Disabled by default. **Known weakness (documented in `DELIVERY_REVIEW.md`): it trusts arbitrary `X-Forwarded-For` values and retains per-client buckets without eviction** — a cost-control knob, not a security boundary.
- **CORS:** configurable via env. `allow_credentials=True` with explicit origins.
- **TLS:** delegated to reverse proxy; not implemented in-app. Docker is HTTP.
- **Secrets:** `.env` gitignored (sample value is a dummy). AI logging sanitizes API keys/URLs.
- **Data isolation:** build conversations are keyed by CPU+GPU pair only — fetchable by anyone who knows the id. No user ownership.
- **No CI/CD, no dependency/security scanning, no container scanning.**

---

## 7. Performance, scalability, maintainability (confirmed)

- **SQLite single-file, single-writer** — no horizontal scaling; documented limitation.
- `GET /hardware` returns the full catalog in one payload; frontend does "load more" client-side. No pagination/cursor; catalog grows => latency and payload growth.
- `GET /hardware/{id}` fetches the full 5,380-row catalog implicitly in the frontend for the homepage; per-detail N+1s are avoided in provenance service via `selectinload`.
- `App.jsx` is a ~140 KB single component file with every view inlined — maintainability risk; no component files.
- Manufacturer filter in `catalog.js` is currently hard-coded to `Intel/AMD/NVIDIA/ATI` (fixed since the audit doc which recorded it as CPU-only).
- No structured logging, no metrics/telemetry, no error tracking, no tracing.
- **Tests:** no CI runner; all verification is local/manual.

---

## 8. Testing & verification (freshly re-run at audit time)

| Suite | Result (fresh run) |
|---|---|
| Backend `pytest backend -q` | **703 passed, 2 skipped** (skips are Docker-volume/environment-dependent) |
| Backend sprint18b classifier | **54 passed** |
| Frontend `node --test src/*.test.js` | **572 passed, 0 failed** |
| Frontend `vite build` | passes (40 modules; JS 327.8 kB / gzip 93.9 kB; CSS 86.5 kB) |
| Frontend `oxlint src` | 0 errors, 1 pre-existing warning (`App.jsx:3107` set-state-in-effect) |

These confirm the published numbers in `docs/` (703/572) and that the committed tree is healthy at audit time.

---

## 9. Deployment, migrations, backups, rollback (confirmed)

- **Docker Compose** with backend + frontend/Nginx, healthcheck, `depends_on: service_healthy`, named SQLite volume, entrypoint template-DB init on empty volume.
- **DB backups:** `data/backups/` convention exists for batch migrations; Batch 018 established a rigorous consistency-safe backup + rollback procedure (SQLite online backup API, `BEGIN IMMEDIATE`, hash-verified restore) rehearsed on isolated copies only.
- **No Alembic; no automated migration runner; no versioned schema table.**
- **No backup automation** for the running deployment (manual/scheduled only).
- **No CI/CD**, no staging promotion pipeline, no automated release process.

---

## 10. Technical debt & architectural bottlenecks (confirmed)

1. `GET /hardware/{id}` 200-with-error instead of 404; catalog routes lack Pydantic response models.
2. No backend GPU comparison; comparison logic duplicated/twinned between frontend and a thin backend CPU-only service.
3. No Alembic / version-aware migrations; one-off additive scripts only.
4. No authentication / ownership / data isolation.
5. Rate limiter trusts `X-Forwarded-For`; no eviction; disabled by default.
6. Single monolithic `App.jsx`; no component decomposition.
7. No pagination/search/facets on the catalog API.
8. No telemetry, structured logging, error tracking, or observability.
9. GPU benchmark dataset absent (by design, but a stated roadmap gap).
10. 20 unattributed hardware rows; 2 rejected / 60 NULL-confidence provenance rows; 46 bare-number CPU names.
11. No CI/CD; no automated test gate; no dependency scanning.
12. Segment coverage only 46.3% (2,886 NULL classified as honest unknown).
13. `main` is 7 commits behind the feature branch — integration work needed.

---

## 11. Confirmed vs Assumed summary

### Confirmed (directly inspected / freshly verified)
- Git branch, HEAD, clean tree, 20 untracked files, remote sync of `89473bb`.
- Backend/frontend stack, DB schema, API surface, dependencies, Docker setup.
- DB row counts and **Batch 018 absent from local, present in staging, not applied to production**.
- All test/build/lint results listed above (fresh runs at audit time).
- License/source registry, provenance model, rate limiter design, build AI evidence contract.
- No CI/CD configuration anywhere in the repository.

### Assumed (from prior documents, not re-verified live)
- The DavidLab deployed revision (`cca96d9`-era per `SPECTRA_SYSTEM_AUDIT.md`); production DB hash `327c40ca…` (per `MIGRATION_READINESS_BATCH018.md`); production health/behavior were not re-probed to avoid touching production.
- SPECTRA V1 remains operational on the production server throughout this upgrade (per the same prior readiness report).

---

## 12. Scope of this delivery

This audit produced four documents (`SPECTRA_V2_AUDIT.md`, `SPECTRA_V2_ARCHITECTURE.md`, `SPECTRA_V2_ROADMAP.md`, `SPECTRA_V2_MIGRATION_PLAN.md`). **No V2 feature code was implemented**; no production infrastructure was modified; the working tree's untracked research files were preserved unchanged.
