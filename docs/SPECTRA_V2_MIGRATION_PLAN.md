# SPECTRA V2 — Migration Plan

**Date:** 2026-10-30
**From:** `89473bb` (`feature/spectra-delivery-20261028`)
**Doctrine:** Keep SPECTRA V1 operational; migrate in small verifiable increments; every step rehearsed on a copy before touching anything live; no production infra/database modified during planning or execution without explicit approval.

---

## 1. Principles

1. **V1 stays operational**: every step is backward-compatible; unauthenticated V1 behavior is the default until auth is explicitly enabled.
2. **Copy-first**: every schema change is applied to an isolated copy first and verified (reuse the Batch 018 rehearsal methodology).
3. **Additive over destructive**: new columns are nullable; new tables; no table rebuilds where avoidable.
4. **Reversible**: backup before applying anything; rollback proven by hash match.
5. **Independent increments**: one Phase 0/1/2/3 concern per PR.
6. **No fabricated upgrades**: coverage and test numbers reported are measured, not presumed.

---

## 2. Pre-requisites (before any migration)

- [ ] Confirm the checkout is on the latest `feature/spectra-delivery-20261028` (or the agreed integration branch) and clean.
- [ ] Confirm remote contains the tip (`git ls-remote`) — verified `89473bb` at audit time.
- [ ] Run the full test baseline (`pytest backend`, `node --test`, `vite build`, `oxlint`), record numbers.
- [ ] Take a consistency-safe backup of any DB the step will touch (SQLite online backup API per Batch 018).
- [ ] Assert the current production revision and DB hash before any change; do not assume.

---

## 3. Migration steps (in order)

### Step 1 — Repository & CI foundation (Phase 0 + 1.4)
- Add `.github/workflows/ci.yml` running: backend `pytest backend -q`, frontend `node --test src/*.test.js`, `vite build`, `oxlint`, data-integrity check. AI suites gated on `GEMINI_API_KEY` presence. ✅ DONE (`6b40aa9`): `backend/app/scripts/check_data_integrity.py` (quick_check + FK + row counts), `backend/app/scripts/ci_verify_schema.py` (fresh schema + runner + integrity), `.github/workflows/ci.yml`.
- Add structured logging + request-id middleware + `/ready` endpoint (source code only). ✅ DONE (`1.4`): `backend/app/logging_config.py` (JSON stdout, idempotent), `backend/app/middleware/request_id.py` (echo/generate `X-Request-ID`), `/ready` (DB reachable + migration state, 503 when unreachable). 7 new tests.
- **Apply to:** source tree only. **No DB write.** Verify: CI passes on a PR; local test baseline still green.
- Verified: CI builds a fresh schema, runs the migration runner, and runs the integrity check; local baseline 726 backend + 574 frontend tests, build, lint green.

### Step 2 — API contract conformance (0.1) ✅ DONE (`1972e66`)
- Change `GET /hardware/{id}` to raise `HTTPException(404)`; add Pydantic `response_model` to catalog/detail routes; add `release_date`+`architecture` to catalog payload.
- Update frontend `apiValidation.js`/call sites in the same PR so no stale special-case remains.
- **Apply to:** source tree only. **DB untouched.** Verify: 703 + 572 tests pass; manual curl 404 check.
- Verified: 703 + 574 frontend tests, build, lint (only pre-existing warning).

### Step 3 — Versioned migration runner (0.2)
- Introduce Alembic initialized against a **copy** of `data/spectra.db`.
- Establish a migration baseline that matches the current schema exactly; the runner is additive.
- Replay existing migrations as Alembic revisions where safe, or record them as baseline.
- **Apply to:** a copy only (`data/spectra.db` untouched). Verify: `upgrade head` on a copy matches schema; `downgrade` back to baseline identical; hash preserved.

### Step 4 — GPU comparison parity (1.1) ✅ DONE
- Backend: `POST /comparison/gpu` returns deterministic `unavailable/tie/difference` semantics with direction-aware TDP/length (lower-is-better); GPU comparison service `compare_gpus`; API tests in `backend/app/test_gpu_comparison_api.py`.
- Frontend: GPU comparison calls the backend via `comparisonGpu.js`/`requestGpuComparison` + `comparisonGpuInsights.js` `buildGpuInsightsFromStatus`; wiring in `App.jsx` uses an idiomatic effect with AbortController (stale requests cannot overwrite newer results, loading derived in render). CPU path unchanged.
- **Apply to:** source tree only. Verify: parity tests pass; existing suites green; lint adds no new warnings.
- Verified: 739 backend (2 skipped) + 590 frontend tests, vite build green, oxlint 1 warning — identical to the pre-existing baseline; GPU + CPU parity tests pass.

### Step 5 — Search, pagination, facets (1.3)
- Add optional params to `GET /hardware` (default preserves current behavior).
- Frontend server-driven pages + facets.
- **Apply to:** source tree only. Verify: contract tests both sides; catalog default unchanged.
- Verified: `GET /hardware` now additive (`q`, `limit`, `offset`, `manufacturer`, `segment` + `X-Total-Count` header, default byte-identical); new `GET /hardware/facets` additive. Backend 777 passed (2 skipped, 1 warning) — 26 new backend tests (`test_hardware_catalog_api.py`); frontend 598 passed (+8), vite build green, oxlint still 1 pre-existing warning only.

### Step 6 — Benchmark quality scoring (1.2)
- Compute a deterministic quality score strictly from existing data (no schema change, no DB write); expose additively in the benchmark API for later 2.3 inline badges.
- **Apply to:** source tree only (per approval: signature of the Plan spec, compute-only, no migration). A DB-column migration remains a possible later additive step if a persisted score is ever wanted.
- Verified: `GET /hardware/{id}/benchmarks` now returns an additive `quality` per row (heuristic 0..1 band from attribution/timestamp/licence/provenance signals; `None` when provenance is `excluded`/`unmatched`). Backend 789 passed (2 skipped, 1 warning) — 12 new tests in `backend/app/test_benchmark_quality.py`; frontend 598 passed, vite build green, oxlint 1 pre-existing warning only. No GPU benchmark data changed; provenance intact.

### Step 7 — Reusable normalizer/validator (1.5) ✅ DONE
- Promote shared normalization primitives (`strip_invisible_characters`, `normalize_name`, `parse_watt`, `parse_int`) into `backend/app/normalization/`; existing importer modules re-export them so importer-facing API is unchanged.
- **Apply to:** source tree only. Verify: full suite green, behavior-identical.
- Verified: 751 backend tests (2 skipped), 1 warning — 12 new tests in `backend/app/normalization/test_primitives.py`; full suite green.

### Step 8 — Authentication & ownership (2.1) ✅ DONE (`df080b4`)
- Feature flag `SPECTRA_AUTH_ENABLED` (default off) + `SPECTRA_AUTH_SECRET`. `users` table (bcrypt-hashed credentials) and nullable `owner_id` on `build_conversations`, registered as migration **v2** in the runner (`backend/app/migrations/runner.py`, `_verify_v2` verification). Copy-only: rehearse on disposable copies (`test_migration_runner.py`, `test_deployment_config.py`); never applied to production without approval.
- Harden rate limiter header parsing (`SPECTRA_TRUSTED_PROXIES`) and eviction (LRU `_MAX_BUCKETS=4096`).
- **Apply to:** source tree; DB migration rehearsed on copy. Verify: off-by-default regression proof + on-mode scoping tests.
- Verified: HMAC-SHA256 stateless tokens issued only after credential verification (register/login), constant-time validation, live-account re-check; `require_auth` raises `HTTPException(401)` (never a dep-value JSONResponse); ownership enforced on create/get/messages/turn/reset; NULL-owner rows inaccessible to authenticated users; IDOR + cross-user tests. Backend 809 passed (2 skipped, 1 warning) — 17 new auth-ON tests in `backend/app/test_auth_security.py`, migration runner updated for v2 (22 tests), deployment-config test rehearses v2 on a tmp copy; frontend 598 passed.

### Step 9 — Frontend decomposition (2.2) + quality badges (2.3) ✅ DONE (`102d869`)
- Split `App.jsx` into `components/`: `components/Markdown.jsx` (extracted `MarkdownContent`) and `components/ChatView.jsx` (`AiChatSection`, `HardwareChatSection`, `HardwareChatTranscript`); App.jsx re-imports them. App.jsx 3983 → 3776 lines; JSX behavior unchanged.
- Add `components/BenchmarkQualityBadge.jsx` — renders the additive backend `quality` field (High/Medium/Low/⚫ No score) inline on benchmark results; mobile-safe, keyboard-accessible, no client-authored data.
- **Apply to:** source tree only. Verify: tests + build + lint per PR.
- Verified: 599 frontend tests (+1 decomposition wiring rewrite; markdownRendering test now asserts the component file wiring), vite build green, oxlint only the pre-existing App.jsx `set-state-in-effect` warning (3013/2987). Roadmap 2.2/2.3 AC met.

### Step 10 — Data debt resolution (2.4) ✅ DONE (honest re-classification)
- Resolve each debt item **only where sources allow**; document each decision; **no fabricated values**. Not a DB mutation — a read-only reconciliation tool + pinned regression tests + audit doc that make the resolved/deferred/blocked split explicit and reproducible.
- Verified: `backend/app/scripts/reconcile_phase24_debt.py` (read-only, deterministic JSON) + `backend/app/test_reconcile_phase24_debt.py` (4 tests) against a disposable copy of `data/spectra.db`. Outcome: **47** bare-number names → deferred-as-intended (verified product model numbers, orderable part IDs), **62** low-confidence rows (60 NULL + 2 rejected) → already-honest (`excluded`/`unmatched`), **8** unattributed hardware → blocked-irresolvable-no-evidence. Doc `docs/PHASE24_DEBT_RESOLUTION.md`, snapshot `docs/fan/phase24_debt.json`. Backend 815 passed (2 skipped) — +10 tests this delivery (4 reconcile + 2 auth + 4 auth-from-prior); frontend 599 passed, vite build green, oxlint 1 pre-existing warning. DB untouched.

### Step 11 — Product intelligence (Phase 3) — only after Phase 0/1 land.

---

## 4. Rollback & roll-forward for each step

Every step is per-PR and reversible:

- **Code steps** (1, 2, 4, 5, 7, 9, 10): no DB change → revert commit if needed.
- **Migration steps** (3, 6, 8): rehearsal copy first; file-restore rollback proven by hash (Batch 018 method); never run against production DB without explicit approval.
- **Deployment**: container-rebuild is forward-only; the previously shipped image is retained as the rollback target. No in-place production mutation.

---

## 5. Production promotion gate (unchanged from Batch 018)

Reuse the documented procedure: explicit approval by name + ticket, consistency-safe backup retained off-container, hash-verified, `BEGIN IMMEDIATE` migration, post-verify (counts + integrity + health), rollback ready. Until an item is approved it runs only on copies/staging.

---

## 6. Testing strategy per step

| Step | Tests added/updated |
|---|---|
| 1 | CI config tested implicitly; data-integrity check |
| 2 | 404 contract test, response-model tests, frontend apiValidation tests |
| 3 | migration-up/down tests on copies, idempotency, rollback hash |
| 4 | GPU comparison parity tests |
| 5 | pagination/search/facet tests, frontend server-page tests |
| 6 | scoring formula tests, column migration tests |
| 7 | normalization reuse tests |
| 8 | auth-on scope tests, auth-off regression tests, limiter hardening tests |
| 9 | 572 frontend tests stay green per refactor PR |
| 10 | provenance reconciliation tests |

## 7. Blocker reporting

If a source, migration, or test cannot be completed because of a licensing/access blocker, report it in the PR and in the roadmap as "blocked — remains 0" rather than fabricating a value. There are no blockers in Phase 0/1 foundations; the only hard external dependency is Phase 3 source acquisition.

---

## 8. Immediate next actions (today, after approval of scope only)

1. Ship this documentation set (audit, architecture, roadmap, migration plan) to the feature branch.
2. Implement Phase 0 items (CI, API contract, migration runner) in separate small PRs.
3. Do not start Phase 1–3 code until Phase 0 is green and this roadmap is agreed.
