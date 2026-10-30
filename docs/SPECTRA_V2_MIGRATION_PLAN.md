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

### Step 4 — GPU comparison parity (1.1)
- Add backend GPU comparison route + tests; keep CPU `/comparison/explanation` unchanged.
- Frontend GPU comparison calls the backend; remove the client-side GPU comparison copy.
- **Apply to:** source tree only. Verify: CPU + GPU parity tests pass; existing suites green.

### Step 5 — Search, pagination, facets (1.3)
- Add optional params to `GET /hardware` (default preserves current behavior).
- Frontend server-driven pages + facets.
- **Apply to:** source tree only. Verify: contract tests both sides; catalog default unchanged.

### Step 6 — Benchmark quality scoring (1.2)
- Add quality columns via a new migration (rehearsed on a copy) and the deterministic scoring service.
- Expose score in benchmark API; frontend quality badges (this is 2.3, orderable after).
- **Apply to:** DB via migration on a **copy** first; then promote to staging/local; production only after approval. Verify: formula tests; no GPU benchmark changes; provenance intact.

### Step 7 — Reusable normalizer/validator (1.5)
- Promote importer code into a public module; importers reuse it; behavior identical.
- **Apply to:** source tree only. Verify: full suite green.

### Step 8 — Authentication & ownership (2.1)
- Feature flag `SPECTRA_AUTH_ENABLED` (default off). Add users + owners when on.
- Harden rate limiter header parsing and eviction.
- **Apply to:** source tree; DB migration on copy (add `owner_id` nullable). Verify: off-by-default regression proof + on-mode scoping tests.

### Step 9 — Frontend decomposition (2.2)
- Split `App.jsx` into `components/` in pure-refactor PRs, each keeping 572 tests green.
- **Apply to:** source tree only. Verify: tests + build + lint per PR.

### Step 10 — Data debt resolution (2.4)
- Fix the 20 unattributed rows, 2 rejected / 60 NULL-confidence rows, 46 bare names **only where sources allow**; document each decision; no fabricated values.
- **Apply to:** DB on copy first; provenance-first; no restricted/unknown-license bulk reuse.

### Step 11 — Product intelligence (Phase 3) — only after Phase 0/1 land.

---

## 4. Rollback & roll-forward for each step

Every step is per-PR and reversible:

- **Code steps** (1, 2, 4, 5, 7, 9): no DB change → revert commit if needed.
- **Migration steps** (3, 6, 8, 10): rehearsal copy first; file-restore rollback proven by hash (Batch 018 method); never run against production DB without explicit approval.
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
