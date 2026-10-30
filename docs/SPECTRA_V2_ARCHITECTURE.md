# SPECTRA V2 — Architecture

**Date:** 2026-10-30
**From:** Audited revision `89473bb` (`feature/spectra-delivery-20261028`)
**Principle:** Preserve existing capabilities; extend the current stack unless a migration is technically justified. No rewrites.

---

## 1. Design goals

SPECTRA V2 must remain an evidence-first hardware intelligence platform. The V2 architecture extends the proven `DATA → COMPUTATION → AI` chain from V1 while addressing the confirmed bottleneck set — API contract consistency, deterministic comparison parity for CPU and GPU, a proper migration runner, observability, and hardening that does not break the existing 703 backend / 572 frontend tests.

Design tenets (unchanged from V1, carried forward):
1. Real data over fabricated data.
2. Deterministic computation over opaque scoring.
3. Evidence over unsupported AI claims.
4. Explicit unknowns over false precision.
5. Small verifiable changes over large rewrites.
6. Regression tests alongside feature development.

---

## 2. Target architecture (incremental, layered)

```
                       ┌───────────────────────────────┐
                       │  React SPA (existing plan)    │
                       │  App.jsx decomposed            │
                       │  catalog / detail / compare /  │
                       │  build / chat views            │
                       └──────────────┬────────────────┘
                                      │ HTTPS (TLS at reverse proxy)
                                      ▼
                       ┌───────────────────────────────┐
                       │  FastAPI (existing)           │
                       │  + response models            │
                       │  + pagination/search          │
                       │  + GPU comparison route       │
                       │  + auth/TLS-ready            │
                       └──────┬──────────┬─────────────┘
                              │          │
                      ┌───────▼──┐   ┌───▼────────────┐
                      │  SQLite  │   │  Gemini (AI)   │
                      │ (survives│   │  + explanations │
                      │  upgrade)│   │  + chat        │
                      └─────┬────┘   └────────────────┘
                            │
                     ┌──────▼──────┐
                     │  Migrations │
                     │  (versioned)│
                     │  + backups  │
                     └────────────┘
```

Extension points are deliberately named so that no step requires rebuilding V1.

---

## 3. Backend extension design

### 3.1 API contract conformance (P0)
- Add Pydantic `response_model` to `GET /hardware` and `GET /hardware/{id}`.
- `GET /hardware/{id}` returns a true `HTTPException(404)` for missing hardware; keep the frontend's special-case handling updated in lockstep (it currently compares `payload.error`).
- Add `release_date` and `architecture` to the catalog list payload (the frontend already consumes detail for these; a lighter catalog is a cheap win).

### 3.2 Pagination, search, facets (P1)
- Add `limit`/`offset` (or cursor) parameters to `GET /hardware`; keep `type`/`manufacturer` filters server-side.
- Add a server-side search parameter (`q`) and facet filters (segment, socket, architecture, release year). Frontend switches from full-client "load more" to server-driven pages. Backwards-compatible default (no params returns current behavior for tests).

### 3.3 GPU comparison parity (P1)
- Add a backend `POST /comparison/gpu` (or generalize `/comparison`) that mirrors `comparison_service.py` for GPU metrics (VRAM, bandwidth, clocks, TDP, length, bus width) with the same `unavailable`/tie semantics.
- Keep the CPU-only `/comparison/explanation` behavior; extend the frontend to call the backend for GPU too, removing the divergent client-side copy (single source of truth for comparison logic).

### 3.4 Migration runner (P0)
- Introduce Alembic (or a minimal versioned runner) so schema changes are version-aware, ordered, and reversible.
- Add a `schema_version`/`alembic_version` tracking mechanism; convert existing additive migrations into the runner where safe (never destructive).

### 3.5 Authentication & data ownership (P2, designed now)
- Add `users` table and token-based auth (e.g., hashed API tokens / JWT) that is **off by default** (V1 stays unauthenticated); when enabled, conversations and comparisons are scoped to the owner.
- Add `owner_id` (nullable) to `build_conversations` so existing rows remain valid; ownership is additive.
- Rate limiter: use trusted proxy header parsing (respect `Forwarded`/`X-Forwarded-For` only from trusted proxies), add bucket eviction, and keep it opt-in.

---

## 4. Data & provenance extension design

### 4.1 Confidence & quality scoring (P1)
- Add a `benchmark_quality` dimension: a deterministic score derived from record_count (sample size), score variance across records, source confidence, and match quality — never from invented values. Report it beside each benchmark and use it to weight comparison evidence.
- Add a boolean/derived `quality_blocked` concept where provenance is `excluded`/`unmatched` (already carried in `evidence_status`); surface it in the UI inline.

### 4.2 GPU benchmark roadmap (depends on a licensed source)
- Extend `benchmark_results` with nullable columns for GPU-specific semantics (e.g., `settings`, `resolution`, `gpu_workload`).
- Only import from a source with `clear` license + reproducible provenance (the same four-criteria gate as V1).
- Until then, keep 0 GPU benchmarks and keep the honesty contract.

### 4.3 Data acquisition & validation
- Promote importer normalization/validation into reusable public modules (currently importer-local), enabling a single validated import API.
- Back-fill `recorded_at` on benchmarks only from real access evidence (never invented dates).

---

## 5. AI / explanation extension design

- **Grounding:** keep `GeminiProvider`; add explicit evidence-citing behavior where each `known_fact` carries the `source` + `source_url` it came from (the frontend already has `SourceDisclosure`; connect AI output to the same evidence model).
- **Confidence-aware answers:** inject the new benchmark-quality dimension into the prompt context so the AI can state "N samples, high confidence" vs "limited evidence".
- **Explainability:** expose deterministic rule explanations (socket, PSU suggestion margin, interface) alongside AI text — the `buildCompatibility.js` rules become a backend-visible, documentable component.
- No changes to the prompt safety contract (evidence priority, unknown handling, no fabricated measurements) — carried forward unchanged.

---

## 6. Frontend UX extension design

- **Component decomposition:** split `App.jsx` into a `components/` tree (Header, Catalog, DetailView, CompareView, BuildView, ChatView) while keeping per-concern logic modules and tests.
- **Responsive & accessible:** keep the theme system, skip-link, keyboard focus, reduced-motion; extend mobile verification (batch016 proved 390px no-overflow).
- **Inline evidence & quality badges:** surface `verified/uncertain/excluded` and confidence inline per field (data already present in provenance API).
- **Catalog UX:** server-side search/facets, pagination, segment/manufacturer/type chips; keep "verified coverage" framing.

---

## 7. Observability, testing & release engineering

- **Logging:** structured JSON logging via `logging` → stdout; request-id middleware.
- **Health:** keep `/health`; add `/ready` (DB + migrations current) and `/live` probe semantics for orchestration.
- **Metrics:** optional Prometheus `/metrics` (opt-in, no new dependency unless warranted) or lightweight counters endpoint.
- **CI/CD:** add GitHub Actions: backend pytest, frontend node --test + build + lint, and a data-integrity check (row counts, quick_check, FK) — all with no external secrets for the non-AI suites; AI suites run only when `GEMINI_API_KEY` is provided.
- **Testing:** keep the fresh numbers (703 + 572 + 54) as the baseline gate; add contract tests for the new routes, migration tests on copies, and quality-score tests.

---

## 8. What stays the same (non-negotiables)

- SQLite remains the database through V2 (single-node, low-cost, honest limitation). PostgreSQL is a possible later migration but is **not** justified now.
- React + FastAPI stack is kept; no framework migration.
- The evidence contract, honesty rules, and provenance model are preserved.
- All 703 backend + 572 frontend + 54 classifier tests keep passing through every step.
- No production infra is modified during design/planning; everything is staged on copies.

---

## 9. Risk register (top risks)

| Risk | Mitigation |
|---|---|
| Making catalog/API changes breaks the frontend contract | Add response models + update frontend in the same PR; contract tests on both sides |
| Batch 018 applied to production in this project | **Not performed**; explicit approval gate retained from `MIGRATION_READINESS_BATCH018.md` |
| Auth rollout regresses unauthenticated V1 | Off by default; additive `owner_id`; feature-flagged |
| Migration runner rewrite breaks existing DBs | Run against copies first; additive-only conversions; version table added, never destructive |
| GPU benchmark import introduces bad data | Same four-criteria gate; NULL-only; provenance-first |
| `App.jsx` decomposition introduces regressions | Keep tests; land decomposition as pure refactor PRs |
