# SPECTRA System Audit

**Generated**: 2026-10-28
**Audited revision**: `2297c7d` (GitHub origin `main`), local clone `C:\Users\user\spectra-local`
**Deployed revision**: `cca96d9` + uncommitted comparison work (server: `/home/david/projects/spectra`)

> Methodology: this audit reconciles the local clone, the GitHub origin, and the
> deployed server. Runtime state was verified over SSH to `david-lab`; deployed
> behavior was verified against the running containers and their database; local
> behavior was verified against a local clone of the origin with a local copy of
> the deployed database. Server uncommitted work is reported, not altered.

---

## 1. Architecture reconciliation

| Layer | Local clone (authoritative) | Server deployed |
|---|---|---|
| Frontend | React 19 / Vite 8 | Nginx serving built `dist/` on port 8080 |
| Backend | FastAPI / Uvicorn | Same, in Docker container, port 8000 (internal), healthy |
| DB | SQLite copy of deployed DB (5380 rows) | SQLite in Docker volume `/app/data/spectra.db` |
| AI | Gemini REST (requires key) | Gemini configured in container |

**Local vs server divergence** (important — must be preserved, never clobbered):

- Server checked out at `cca96d9`; local clone (origin) HEAD is `2297c7d`.
  Origin is **2 commits ahead of** the server's checked-out commit:
  - `70bf68c fix(comparison): report unavailable metrics instead of crashing on null spec fields`
  - `2297c7d feat(gpu): surface memory bus width across detail, comparison, and build context`
- Server working tree carries **uncommitted edits** to
  `backend/app/schemas/comparison.py` and
  `backend/app/services/comparison_service.py` plus untracked
  `backend/app/test_comparison_service.py`, `compose.override.yaml`,
  `compose.override.yaml.bak-before-tailscale`, and `data/spectra.db.upload`.
  The uncommitted comparison edits are **byte-for-byte the changes already
  committed upstream** in `70bf68c` — i.e. the server's in-progress comparison
  work is redundant with origin. The `compose.override.yaml` binds the frontend
  to the Tailscale interface `100.113.157.0:8080`.
- Serving container health: `spectra-backend` healthy; `spectra-frontend` up.
  Backend responds 200 on `/health`; logs show only `/health` probes.

**Conclusion**: the local clone is the authoritative development baseline. The
server's uncommitted comparison work must not be committed again (it already
exists upstream), and the two Tailscale-compose override files are environment
config that should stay untracked or be documented.

## 2. Database schema (current)

SQLite, SQLAlchemy 2.0 declarative models. Tables:

| Table | Purpose | Notes |
|---|---|---|
| `hardware` | identity (name, manufacturer, type, release_date, architecture) | `type` constrained only by app convention, currently `CPU`/`GPU` |
| `cpu_specifications` | cores, threads, base/boost clock GHz, TDP W, process node nm, socket | 1:1 with hardware |
| `gpu_specifications` | memory GB, memory type, clocks MHz, bandwidth GB/s, bus width bits, TDP W, interface, length mm | 1:1 with hardware |
| `benchmark_results` | benchmark_name, score, unit, test_type, source_id, recorded_at | 1:N |
| `sources` | name, url, publisher, description, license_*, terms_notes, attribution, retrieved_on | Batch 015 transparency columns |
| `field_provenance` | field-level provenance: source_id, table_name, field_name, evidenced_value, source_url, license, confidence, evidence_status, match_method, batch_no | additive evidence log, never mutates values |
| `external_identifiers` | external_id, identifier_type, source_id | e.g. Intel ARK IDs |
| `build_conversations` / `build_messages` | persistent build chat | identity = CPU+GPU pair |
| `migrations/` | 3 one-off additive Python migrations | no Alembic |

**Migration approach**: additive `ALTER TABLE` scripts, no Alembic. Committed
migrations use additive columns/constraints only. This is safe but has no
version table / version-aware runner; each migration is a standalone module.

## 3. Data provenance model (current)

- **Field-level provenance** with `evidence_status ∈ {verified, uncertain, excluded, unmatched}`.
- **Confidence** ∈ {high, medium, rejected, None}.
- Sources carry licence metadata (`clear / unknown / restricted / unresolved`),
  attribution, terms notes, retrieval date.
- No machine-readable robots.txt / rate-limit log; ingestion batches keep
  `sources/*.txt` raw dumps in `data/research/batchNNN/sources/`.
- Batch numbers tracked per provenance row (`batch_no`), enabling replay/audit.

## 4. Validation, duplicate detection, normalization

Present in `backend/app/importers/`:

- `cpu_normalizer.py`, `cpu_validator.py`, `gpu_normalizer.py`,
  `gpu_validator.py`, `benchmark_normalizer.py`, `benchmark_matcher.py`
- Name normalization strips ™/®, normalizes whitespace, keeps model tokens.
- Unit normalization (e.g. signed/scientific notation handled deliberately).
- Duplicate detection: normalization + matching in importers; `external_identifiers`
  and provenance indexes carry uniqueness constraints.
- Idempotent imports: tests cover re-import stability.

**Gap**: normalization/validator logic is importer-local and not exposed as a
reusable public service; no real-time conflict-resolution path (imports resolve
conflicts at build time, not served at runtime).

## 5. API surface and contracts

Verified endpoints (`backend/app/main.py`):

| Method & path | Purpose | Status |
|---|---|---|
| `GET /` | welcome | ✓ |
| `GET /health` | liveness | ✓ |
| `GET /hardware?type=` | catalog list (returns only id/name/manufacturer/type) | ✓ |
| `GET /hardware/{id}` | detail + specifications (CPU 7 fields / GPU 9 fields) | ✓ |
| `GET /hardware/{id}/benchmarks` | benchmark results + filters | ✓ |
| `GET /sources`, `GET /sources/{id}` | source transparency | ✓ |
| `GET /hardware/{id}/provenance` | field provenance for hardware | ✓ |
| `GET /benchmarks/{id}/provenance` | benchmark provenance | ✓ |
| `POST /comparison/explanation` | AI explanation (Gemini) | ✓ (requires key) |
| `POST /hardware/chat` | AI hardware chat | ✓ (requires key) |
| `POST /build/chat` | AI build chat | ✓ (requires key) |
| `POST/GET /build/conversations...` | persistent build conversations | ✓ |
| `GET /hardware/999999/*` | 404 behavior | ✓ tests |

**Response model gaps found**:
- `GET /hardware` returns inline dicts (no Pydantic response_model); the
  catalog payload validator lives only in the frontend (`apiValidation.js`).
- `GET /hardware/{id}` returns a dict with `"error"` on missing hardware
  instead of raising `HTTPException(404)` — **inconsistent API contract**
  (frontend must special-case this). Verified: the deployed behavior for a
  missing hardware returns `{"error": "Hardware not found"}` with HTTP 200,
  whereas `/hardware/{id}/benchmarks` and `/provenance` correctly 404.
- The catalog list omits `release_date`/`architecture`, so the frontend has to
  fetch detail per card (or show fewer fields).
- No pagination on `/hardware`; the frontend does client-side "load more".
- No search query parameter; search is fully client-side.

## 6. Comparison engine (current)

Backend (`comparison_service.py`):
- CPU vs CPU: cores, threads, base clock, boost clock, TDP.
- No GPU comparison endpoint on the backend at all (!). GPU comparison is done
  **entirely in the frontend** (`comparison.js`).
- Missing-value handling: committed `70bf68c` now reports `winner="unavailable"`
  with `difference=None` instead of crashing.

Frontend (`comparison.js`, `comparisonDecision.js`):
- CPU metrics: Geekbench 7 multi/single (benchmark), cores, threads, boost,
  base, TDP (spec) — **7 metrics**.
- GPU metrics: VRAM, bandwidth, core clock, boost clock, TDP, length — **6
  metrics**; plus GPU table specs incl. bus width, memory type, interface,
  architecture, release date.
- Insights: measurable count, wins, ties, percentage differences, unavailable
  & pending metrics; benchmark evidence separated from spec evidence.
- CPU ↔ GPU comparison rejected (type-safe).
- GPU benchmark: **0 results** — deliberate, documented product decision.

**Gaps**:
- No desktop-vs-mobile CPU conceptual distinction in the schema (no "form factor"
  or "segment" column); a mobile chip and a desktop chip with same marketing
  name are one record. This collides with the mission's "don't confuse laptop
  and desktop GPU performance" constraint — SPECTRA currently has one catalog
  with no segment dimension at all.
- No memory bandwidth CPU metric, no per-core score, no power-efficiency
  metric, no price-perf, no gaming/productivity workload breakdown.
- Backend lacks a GPU/comparison REST route consistent with CPU comparison.

## 7. Build configurator & build intelligence (current)

- `buildConfig.js`: selects CPU + GPU, use case, resolution, and extra context;
  TDP sum is labeled "listed component TDP — not a system power draw".
- `buildIntelligence.js`: status empty/loading/partial/ready/unavailable;
  categories performance / specification / power / dataAvailability; signal
  states; strengths / considerations / data gaps.
- `signalProfile.js`: deterministic profile of a build.
- `buildChat` + persistent conversations store structured evidence answers.

**Gaps**:
- **No socket/chipset/RAM/PSU/clearance compatibility validation.** CPU socket
  exists, but there is no motherboard catalog; no RAM type; no PSU capacity; no
  case/cooler clearance. Phase 4's "validate socket, chipset, RAM type, PSU
  capacity, GPU dimensions, case clearance, cooler clearance, storage
  interfaces, BIOS compatibility, thermal constraints" cannot be fully
  satisfied without those catalogs — but the CPU socket / GPU length /
  interface data already present can power a **subset** (e.g. "GPU requires X
  PCIe slots", "CPU socket AM5 needs compatible board") as explicit-rule
  checks with clearly stated assumptions.
- Explanations: AI produces evidence-structured answers; there is no
  deterministic "why this build is compatible/mismatched" rule engine.

## 8. Search & filtering (current)

- Client-side: substring search over catalog `name`; type filter; manufacturer
  filter (Intel/AMD only — the deployed catalog is 100% Intel/AMD/ATI/NVIDIA,
  so manufacturer filter is hard-coded to two values and **cannot represent
  NVIDIA/ATI records** in the filter UI — a real gap discovered in
  `catalog.js` where `MANUFACTURER_FILTERS = ["All", "Intel", "AMD"]`).
- GPU records (NVIDIA, AMD, ATI) live in the same catalog but the manufacturer
  filter list is CPU-only.
- No backend search; no debounce/request-guard beyond `createCatalogLoadGuard`.
- No faceted filters (architecture, socket, release year, VRAM tier, etc.).

## 9. Authentication, authorization, security

- **No authentication**. `PRODUCTION_READINESS.md` states "API is
  unauthenticated by design"; no users, tokens, ownership, or RBAC tables.
- **No rate limiting** on any endpoint (public or AI).
- **Cost controls**: none enforced at API level; Gemini retries/backoff exist
  client-side of provider; no budget/usage budget, no per-key quota.
- CORS configured via env; TLS is delegated to a reverse proxy (none observed
  for the Tailscale bind; the frontend is bound to the Tailscale VPN IP).
- Secrets: `.env` gitignored; provider messages sanitize API keys from logs and
  URLs. Build-chat persistence has no ownership concept (conversation ID
  fetchable by anyone).
- No DB backup automation observed; `data/backups/` exists but the deployed
  DB lives in a Docker volume. No migration runbook preserved with versioning.

## 10. Frontend UX assessment (based on code + batch016 screenshots)

Strengths:
- Theme control (dark/light/system), skip-link, keyboard focus, reduced-motion.
- Batch 016 verified: no horizontal overflow at 390px even for a 93-char name;
  no console errors; source disclosure UI; comparison tray; benchmark-vs-spec
  separation; zero network failures in dev.

Weak points:
- `App.jsx` is a **140 KB single file** with every view inlined (catalog,
  detail, comparison, build, chat). It works and is thoroughly tested by text
  tests, but the size is a maintainability risk; there are no component files.
- Manufacturer filter hard-coded (above).
- Catalog default type filter "All" still shows CPU+GPU; the hero labels
  "Share of catalog" from live composition — good.
- Missing-data states exist (`signalProfile`, build gaps), but the **catalog
  detail view** shows `None` values plainly in several spots; data-quality
  badges (verified/uncertain/excluded) are not surfaced inline on every field.

## 11. Test suite status (verified locally)

| Suite | Result (local, HEAD 2297c7d) |
|---|---|
| Backend `pytest backend -q` | **675 passed, 2 skipped, 2 failed** (failures are Docker-dependent `test_deployment_config.py` — require a Docker volume template; environment, not code) |
| Frontend `node --test` | **549 passed, 0 failed** |
| Frontend `vite build` | passes |
| Frontend `oxlint` | 1 pre-existing warning (`App.jsx:3107`, set-state-in-effect) |
| Backend `.env`-dependent chat tests | pass once `GEMINI_API_KEY`/`GEMINI_MODEL` are present (they short-circuit to 503 otherwise, by design) |

`test_deployment_config.py` asserts hard-coded `5380` row counts and requires a
Docker volume; on a CI host without Docker or the data-template it fails. This
is brittle but intentionally environment-specific.

## 12. Prioritized gaps and recommended order

Confirmed priorities (matches user's chosen strategy):

1. **API contract fixes** (small, high value): make `GET /hardware/{id}`
   genuinely 404; add Pydantic response models to catalog/detail routes;
   document the frontend's special-casing. Add a `segment`/form-factor column
   (additive migration) with backfill = safe baseline for the mission's
   "don't confuse laptop/desktop" requirement.
2. **Comparison engine hardening**: backfill missing GPU/CPU metrics
   deterministically; add CPU power-efficiency, per-core, GPU bandwidth (already
   surfaced), and notebook vs desktop segment checks.
3. **Build intelligence**: add deterministic compatibility rules usable with
   the current CPU/GPU schema (socket class, GPU length/slots, PSU suggestion as
   `listed TDP sum + margin`, adjustments as assumptions), all labeled.
4. **Data quality / security**: schema validation module, ambiguity refusal
   (same marketing name, different segment), provenance tests, deterministic
   comparison tests, missing-data tests; **rate limiting** on AI endpoints
   (per-IP token bucket, configurable, off by default to avoid breaking tests);
   backup/migration runbook.
5. **Frontend**: inline evidence badges, manufacturer filter fix, missing-data
   states, mobile pass.
6. **Catalog expansion (Phase 2)**: deferred to a structured follow-up pipeline
   doc — see `DATABASE_EXPANSION_PIPELINE.md`.

Cross-cutting: never claim "comprehensive" from row counts; every coverage
statement in this project's docs should be phrased as *validated coverage*.
