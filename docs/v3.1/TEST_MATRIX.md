# SPECTRA V3.1 — Test Matrix

Date: 2026-11-10
Scope: what the V3.1 branch proves, scenario by scenario. Every row maps to an
executing test; counts measured on the branch at commit `6d303d2`.

---

## 1. Suite totals (branch state)

| Suite | Result | Command |
|---|---|---|
| Backend pytest | **1095 passed, 2 skipped, 2 deselected** (17.3 s) | `python -m pytest backend -q` with the CI ignore/deselect list |
| Frontend node --test | **635 passed, 0 failed** | `node --test src/*.test.js` |
| Frontend production build | success (355.88 kB JS / 122.72 kB CSS) | `npx vite build` |
| oxlint | 0 errors; 3 pre-existing warnings (`set-state-in-effect`) — out of scope | `npx oxlint src` |

Baseline for comparison (pre-branch): backend 971 passed / frontend 626.
**Delta: +124 backend tests, +9 frontend tests, all green.**

Skipped tests are AI-gated (need a real `GEMINI_API_KEY`); deselected are
Docker-persistence cycle tests needing a container runtime. Both categories
pre-date V3.1 and are unchanged.

## 2. V3.1 milestone coverage

### M1 — Auth hardening

| Scenario | Test | Result |
|---|---|---|
| Bootstrap creates first admin, strength-checks password | `scripts/test_bootstrap_admin.py` (9 tests) | pass |
| Bootstrap refuses weak password / second run / populated table | same | pass |
| 401 on protected writes without token | `test_auth_security.py` (19, incl. pre-existing IDOR/token) | pass |
| Cross-user (IDOR) isolation, expired/invalid tokens | `test_auth_security.py` | pass |
| Security headers on 2xx, 4xx, and 404 | `test_v31_matrix.py::TestSecurityHeadersRegression` | pass |

### M2 — Deployment guardrails

| Scenario | Test | Result |
|---|---|---|
| 8 preflight checks: SHA, git-clean, compose collision, image tags, backup, migration, disk, volume | `scripts/test_deploy_preflight.py` (25 tests) | pass |
| Ops-dir + separate source-checkout shape (production shape) | `test_deploy_preflight.py::test_ops_dir_with_separate_source_checkout` | pass |
| Legacy/dirty tree refused | same file + **live verified** on david-lab (5 blockers raised) | pass |
| Wrapper refuses legacy checkout; python3 fallback; dry-run | **live verified** (dry-run passed, no mutation) | pass |
| `/release` identity endpoint, no secrets | `test_release.py` (11) + `test_v31_matrix.py` | pass |
| Browser stale-tab detection (cache-defeated release fetch) | `frontend/src/releaseIdentity.test.js` (9 tests) | pass |

### M3 — Backup & observability

| Scenario | Test | Result |
|---|---|---|
| WAL-aware consistent backup; SHA256/integrity/FK/row-count verification | `scripts/test_backup_database.py` (12 tests) | pass |
| Stale output replaced; refuses bad source | same | pass |
| Restore rehearsal on disposable target; refuses live-looking paths, empty catalog, same-target | `scripts/test_restore_rehearsal.py` (11 tests) | pass |
| Retention keeps newest N; never touches non-backup names; refuses keep<1 / empty dir | same | pass |
| **Live restore rehearsal on the real 51 MB production backup** | run on david-lab — SHA `a82529ec…` match, integrity ok, 5380/3501/1879 rows | pass |
| `/metrics` bounded cardinality (no IDs/queries/bodies), aggregation | `middleware/test_metrics.py` (6) + `test_v31_matrix.py` | pass |
| Alert evaluation: 9 conditions incl. empty-signals → `backup_missing` | `scripts/test_alerts.py` (21 tests) | pass |

### M4 — AI provider readiness

| Scenario | Test | Result |
|---|---|---|
| Missing key → **503** (not 500) on `/comparison/explanation`, `/hardware/chat`, `/build/chat` | `test_v31_matrix.py::TestAIEndpointFailureModes` | pass |
| Concurrency exhaustion → **429** on all three endpoints | same + `test_concurrency_limit.py` (8 tests) | pass |
| Semaphore released on success AND failure (no leak) | `test_concurrency_limit.py` | pass |
| True concurrent calls bounded; excess refused | `test_concurrency_limit.py::test_concurrent_calls_bounded` | pass |
| `ai_provider_state` = unconfigured/unusable/configured; key never in output | `test_release.py::TestProviderState` + `TestNoSecretLeakage` | pass |
| Existing AI behaviour (retries, backoff, sanitization, prompt anti-invention, input limits) | pre-existing AI suite (261 chat/explanation tests) | pass |

### M5 — Cross-cutting regression matrix

| Scenario | Test | Result |
|---|---|---|
| Disallowed CORS origin gets no grant; preflight OPTIONS rejected | `test_v31_matrix.py::TestCORSEnforcement` | pass |
| Headers on success / auth rejection / not-found | `TestSecurityHeadersRegression` | pass |
| `/release` + `/metrics` never leak configured key; no stack traces in errors | `TestNoSecretLeakage` | pass |
| Rate limiter opt-in (disabled by default, headers unchanged) | matrix + pre-existing | pass |

## 3. Live verification on david-lab (read-only toward production)

| Scenario | Result |
|---|---|
| Restore rehearsal on the real backup copy | **pass** (SHA match, integrity ok, full catalog) |
| Preflight on real ops dir + source checkout | **8/8 PASS** |
| Preflight on legacy checkout | **REFUSED** (5 blockers) — takeover guard proven |
| Wrapper dry-run | **pass**, zero mutation |
| Live HTTP probes (`/api/health`, `/api/ready`, `/api/auth/status`, cache headers) | all as documented in BASELINE_AUDIT.md §3.5 |

## 4. Not covered (explicit gaps)

- **AI-gated tests (2 skipped)** need a real provider key; the mock-based
  suite covers the failure modes. Activate per AI_PROVIDER_READINESS.md §6 and
  the skips resolve.
- **Docker persistence cycle tests (2 deselected)** need a container runtime
  on the test host; they exercise compose restart persistence, orthogonal to
  V3.1 changes.
- **End-to-end browser run against a live deployment** — release-identity is
  unit-tested with injected fetches; a real-browser pass is part of the next
  release's deploy verification, not this branch (deploy is user-gated).
- **Notification transport** — the alert engine outputs text; wiring a real
  channel is a user decision (OBSERVABILITY_PLAN.md §4).
