# SPECTRA V2 — Roadmap

**Date:** 2026-10-30
**Gate:** Each item must keep the existing test baseline green (703 backend / 572 frontend / 54 classifier) and must not modify production infra.

Legend — Priority: P0 (foundation) / P1 (high) / P2 (medium) / P3 (roadmap/future). Complexity: S/M/L.

---

## Phase 0 — Stabilize & gate (P0)

### 0.1 API contract conformance
- **Priority:** P0 · **Dependencies:** none · **Effort:** S
- **Benefits:** removes the 200-with-error abstraction, gives typed Pydantic responses, eases API tests/validation clients.
- **Acceptance criteria:** `GET /hardware/{id}` returns 404 for missing ids; `GET /hardware` and `GET /hardware/{id}` have `response_model`; `release_date`+`architecture` in catalog payload; existing 703 backend / 572 frontend tests still pass (frontend special-case removed in same PR).
- **Risks:** frontend contract drift → mitigated by updating the frontend validation in the same change; contract tests both sides.

### 0.2 Versioned migration runner
- **Priority:** P0 · **Dependencies:** none · **Effort:** M
- **Benefits:** replaces one-off additive scripts with ordered, reversible, auditable schema changes; enables future schema work (owner, quality columns) safely.
- **Acceptance criteria:** Alembic (or equivalent) initialized on a copy; `schema_version` tracked; all existing additive migrations replayed idempotently on a fresh copy; dry-run + rollback verified on copies; no existing DB altered outside copy.
- **Risks:** conversion errors → mitigate with copy-only rehearsal and hash verification (reuse Batch 018 method).

### 0.3 CI/CD baseline
- **Priority:** P0 · **Dependencies:** none · **Effort:** M
- **Benefits:** turns the strong local test culture into an enforced gate; catches regressions automatically.
- **Acceptance criteria:** GitHub Actions runs backend pytest, frontend node --test, vite build, oxlint, and a data-integrity check on every PR; non-AI suites run without secrets; AI suites skipped when no key; no `.env`/secrets in CI.
- **Risks:** CI environment drift (Docker-dependent tests) → those tests stay excluded/skipped as today.

---

## Phase 1 — Data quality, comparison parity, observability (P1)

### 1.1 Backend GPU comparison / single comparison engine
- **Priority:** P1 · **Dependencies:** 0.1 · **Effort:** M
- **Benefits:** removes the CPU-only backend vs client-side GPU divergence; single source of truth for deterministic comparison; enables AI explanation for GPU with backend-verified facts.
- **Acceptance criteria:** `POST /comparison/gpu` returns the same `unavailable`/tie/difference semantics as CPU; frontend GPU comparison calls the backend; comparison logic tests cover both CPU and GPU; no behavioral change to existing CPU path.
- **Risks:** behavioral parity → comprehensive parity tests; frontend migration done in the same PR.

### 1.2 Benchmark quality & confidence scoring
- **Priority:** P1 · **Dependencies:** 0.2 (new columns) · **Effort:** M
- **Benefits:** honest quality dimension (sample count, variance, source confidence) that weights evidence without inventing numbers; enables confidence-aware AI and inline badges.
- **Acceptance criteria:** deterministic score computed from existing data only; exposed in benchmark API; documented formula; new tests; 0 GPU benchmarks unchanged; no scoring for `excluded`/`unmatched`.
- **Risks:** overclaiming confidence → strictly derived, formula documented, no user-facing "absolute" claims.

### 1.3 Server-side search, pagination, facets
- **Priority:** P1 · **Dependencies:** 0.1 · **Effort:** M
- **Benefits:** catalog scales beyond the single 5,380-row payload; enables rich faceted discovery (segment, socket, architecture, year, VRAM tier).
- **Acceptance criteria:** `GET /hardware` supports `q`, `limit`, `offset`, typed/manufacturer/segment filters; default (no params) preserves current behavior so tests pass; frontend uses server pages; facet counts accurate.
- **Risks:** default-behavior change → additive params only; frontend fallback for old calls.

### 1.4 Observability (structured logging, readiness, metrics)
- **Priority:** P1 · **Dependencies:** none · **Effort:** S–M
- **Benefits:** production reliability; request-id correlation; `/ready` for orchestration; capacity to detect slow queries/AI failures.
- **Acceptance criteria:** structured JSON logs; `/health` unchanged; `/ready` checks DB + migrations; optional metrics endpoint; no PII/keys in logs (extends existing redaction).
- **Risks:** none material (additive).

### 1.5 Normalizer/validator as reusable service
- **Priority:** P1 · **Dependencies:** none · **Effort:** M
- **Benefits:** single validated ingestion path; new catalogs (RAM/SSD/etc.) reuse it; reduces importer duplication.
- **Acceptance criteria:** importer-local normalization promoted to `backend/app/normalization` (or similar), tested, imported by importers without behavior change; existing tests pass.
- **Risks:** refactor regression → keep behavior-identical tests.

---

## Phase 2 — V1 functionality preserved, hardening (P2)

### 2.1 Authentication & data ownership (opt-in) — **DONE** (commit `df080b4`)
- **Priority:** P2 · **Dependencies:** 0.2, 1.1 · **Effort:** L
- **Benefits:** addresses "user data ownership" mission goal; enables multi-user deployment; scopes conversations and comparisons per owner.
- **Acceptance criteria:** auth feature-flagged OFF by default (V1 unauthenticated untouched); when ON, `owner_id` on `build_conversations`, tokens verified, endpoints 401/403 correctly; existing rows (owner NULL) continue to work; rate limiter hardened (trusted-proxy headers + eviction).
- **Risks:** regression in unauthenticated mode → default OFF + dual-path tests; user isolation bugs → scoping tests.

### 2.2 Frontend component decomposition — **DONE** (commit `102d869`)
- **Priority:** P2 · **Dependencies:** none · **Effort:** L
- **Benefits:** 140 KB single-file `App.jsx` risk resolved; better maintainability, reviewability.
- **Acceptance criteria:** views split into `components/` (`ChatView.jsx`, `Markdown.jsx`); all frontend tests pass with identical behavior (599 = baseline + decomposition wiring test); lint clean except pre-existing warning; build size not increased beyond reasonable.
- **Risks:** pure-refactor regressions → behavior-identical tests before/after each PR.

### 2.3 Inline evidence & quality badges in UI — **DONE** (commit `102d869`)
- **Priority:** P2 · **Dependencies:** 1.2 · **Effort:** M
- **Benefits:** surfaces the backend-computed quality score inline (High/Medium/Low/No score) matching mission evidence-grounding goal.
- **Acceptance criteria:** badge rendered from the additive `quality` field on benchmark results; mobile-safe; keyboard accessible (`role=text` + `aria-label` + `title`); no client-authored data for unscored rows (⚫ No score).
- **Risks:** none material (presentational).

### 2.4 Resolve provenance/dataset debt
- **Priority:** P2 · **Dependencies:** none · **Effort:** M
- **Benefits:** closes the 20 unattributed rows, 2 rejected / 60 NULL-confidence rows, 46 bare-number names (only where sources allow, never invented).
- **Acceptance criteria:** each debt item resolved or explicitly re-classified with documented evidence; no invented values; provenance rows honest.
- **Risks:** licensing (PassMark/TechPowerUp restricted) → reference-only sources, never bulk reuse; document each decision.

### 2.4 Resolve provenance/dataset debt
- **Priority:** P2 · **Dependencies:** none · **Effort:** M
- **Benefits:** closes the 20 unattributed rows, 2 rejected / 60 NULL-confidence rows, 46 bare-number names (only where sources allow, never invented).
- **Acceptance criteria:** each debt item resolved or explicitly re-classified with documented evidence; no invented values; provenance rows honest.
- **Risks:** licensing (PassMark/TechPowerUp restricted) → reference-only sources, never bulk reuse; document each decision.

---

## Phase 3 — Extended intelligence (P3 / roadmap)

### 3.1 GPU benchmark integration (licensed source only)
- **Priority:** P3 · **Dependencies:** 1.2, 1.5 · **Effort:** L
- **Benefits:** closes the largest data gap, enables GPU performance comparison + AI confidence context.
- **Acceptance criteria:** source meets all four criteria (license clear, provenance, accessibility, reproducibility); NULL-only; provenance-first; quality-scored; no fabricated FPS.
- **Risks:** no suitable source found → remains 0, documented (current honest state).

### 3.2 Deterministic compatibility & recommendation engine
- **Priority:** P3 · **Dependencies:** 1.3, 1.5 · **Effort:** L
- **Benefits:** moves `buildCompatibility.js` heuristics into a documented backend rule engine; supports socket/interface/length checks with explicit assumptions; a recommendation path once quality scores exist.
- **Acceptance criteria:** each rule labeled with assumptions; `unknown` when fields missing; PSU suggestion stays a suggestion (documented margin); no hard compatibility claims without catalogs.
- **Risks:** overclaiming compatibility → rule engine explicitly reports `requires_catalog` for missing catalogs.

### 3.3 Additional data categories & richer benchmarks
- **Priority:** P3 · **Dependencies:** 1.5 · **Effort:** L
- **Benefits:** RAM/SSD/motherboard catalogs unlock real compatibility; richer CPU/GPU datasets.
- **Acceptance criteria:** new category follows the documented expansion pipeline end-to-end with provenance and license gate; tests + docs updated.
- **Risks:** same licensing constraints; staged behind source availability.

### 3.4 Price & performance-to-price
- **Priority:** P3 · **Dependencies:** 1.2 · **Effort:** L
- **Benefits:** product goal "performance-to-price analysis".
- **Acceptance criteria:** licensed pricing source; provenance per price; deterministic per-price calc; never invented MSRP; documented coverage limits.
- **Risks:** no licensed source → remains absent (honest).

---

## Dependencies & sequencing summary

```
Phase 0  0.1 API contract ──► 1.1 GPU comparison ─► 2.1 Auth ─► 3.x
        0.2 Migrations ─────► 1.2 Quality ────────► 2.3 Badges
        0.3 CI ─────────────► 1.4 Observability ──► (release gates)
                          └─► 1.5 Normalizer ─────► 3.2/3.3
```

- 1.2 depends on 0.2 (new columns), 2.3 depends on 1.2, 2.1 depends on 0.2 + 1.1.
- 3.x all depend on Phase 0/1 foundations.
- Parallelizable: 1.4 and 1.5 can proceed alongside 1.1–1.3.

## Cross-cutting rules (all phases)

- Every migration rehearsed on a copy first; hash-verified backup/rollback (Batch 018 method).
- No production write without explicit approval.
- All AI additions preserve the existing evidence/trust boundary.
- Every PR keeps 703 + 572 + 54 tests green and adds tests for new behavior.
- No secrets in CI or in committed artifacts.
