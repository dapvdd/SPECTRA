# SPECTRA V3.1 — Security Findings

Date: 2026-11-10
Operation: SPECTRA V3.1 production hardening
Scope: backend auth/config, deployment tooling, observability, AI provider layer, host posture. Read-only production inspection; no production mutation.

This document consolidates the Phase 0 findings (see BASELINE_AUDIT.md §5) with
the V3.1 branch's remediation status. Severity is assessed by operational
impact and exploitability, not tool labels.

---

## 1. Findings register and remediation status

| ID | Finding | Severity | Status on V3.1 branch | Activation still requires |
|---|---|---|---|---|
| F-01 | Auth disabled in production; write endpoints accept anonymous traffic; all callers share conversations (guest mode); rate limiting off | P1 | **Prepared, not activated.** `SPECTRA_AUTH_ENABLED` remains unset. M1 delivers the bootstrap CLI (`backend/app/scripts/bootstrap_admin.py`), token hardening tests (`test_auth_security.py`), and `.env.example` guidance | Production env change + admin creation (user-gated) |
| F-02 | `spectra-backend:latest` / `spectra-frontend:latest` exist on the host pointing at non-release image IDs — latent downgrade hazard | P2 | **Mitigated in tooling.** Preflight validates tags; `deploy_release.sh` refuses deployments that do not match the expected SHA. Host `:latest` tags are NOT retagged (out of scope by contract) | Optional host cleanup (user-gated) |
| F-03 | Legacy dirty checkout (`/home/david/projects/spectra`) shares compose project `spectra`, container names, and port 8080 — one command from a takeover | P2 | **Mitigated in tooling.** Preflight detects project/port/container-name collisions and dirty trees; wrapper refuses legacy checkouts outright (verified live: 5 blockers raised). Legacy checkout itself untouched | None |
| F-04 | No scheduled SPECTRA backup; backups are release-day artefacts; data-loss window unbounded | P1 | **Tooling delivered, scheduling not installed.** WAL-aware backup with verification, retention (keep-last-N), and restore rehearsal are on the branch; installing host cron is a documented, user-approved step | Host crontab change (user-gated) |
| F-05 | `SPECTRA_CORS_ORIGINS` lists only localhost while the app serves from the Tailscale IP; benign for same-origin nginx use but blocks any future cross-origin client | P3 | **Documented.** `.env.example` explains the allow-list. Production env unchanged | Env change at activation (user-gated) |
| F-06 | Duplicate `/hardware/chat` route decorator in `backend/app/main.py` — shadowed first registration, latent edit hazard | P3 | **Fixed.** Duplicate removed in M1 (commit `3441b95`) | None |
| F-07 | No token revocation beyond expiry/user-deletion; stateless 24 h bearer tokens | P2 | **Documented + tested.** Token lifecycle tests cover expiry, signature, and user-deletion invalidation; admin bootstrap gives account recovery. Full revocation (server-side denylist) is out of scope for V3.1 | None (design accepted for self-hosted threat model) |
| F-08 | `users` table empty; enabling auth would lock out everyone | P1 (blocks F-01) | **Resolved in code.** `bootstrap_admin.py` creates the first admin non-interactively with strength-checked passwords; covered by 9 tests. Not executed against production (contract) | Execution at activation (user-gated) |
| F-09 | Container healthcheck probes `/health` (process liveness) not `/ready` (DB + migrations) | P3 | **Documented.** Runbook uses `/ready` for operational checks; Dockerfile healthcheck change requires an image rebuild | Next image build (user-gated) |
| F-10 | No release-identity surface for stale-tab diagnosis | P3 | **Resolved.** `/api/release` reports version/git_sha/built_at/auth/ai state; `frontend/src/releaseIdentity.js` compares client build SHA against server release SHA with cache-defeated fetch | None |

## 2. New hardening delivered by V3.1 (not in the baseline register)

| Item | Detail | Tests |
|---|---|---|
| Security headers middleware | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, CSP on every response class (2xx/4xx) | `test_v31_matrix.py::TestSecurityHeadersRegression` |
| Aggregate request metrics | Bounded-cardinality `/metrics` (route templates only; no paths with IDs, no query strings, no bodies) | `middleware/test_metrics.py`, `test_v31_matrix.py::TestMetricsCardinality` |
| Provider concurrency bound | `SPECTRA_AI_CONCURRENCY` semaphore; excess calls get `ProviderBusyError` → **429** instead of piling up in-flight requests | `test_concurrency_limit.py`, `test_v31_matrix.py::TestAIEndpointFailureModes` |
| Provider failure mapping | Missing key → **503** (not 500) on all three AI endpoints; provider error → 502 | `test_v31_matrix.py::TestAIEndpointFailureModes` |
| Provider config diagnostics | `/api/release` reports `ai_provider_state`: unconfigured / unusable / configured — never the key value | `test_release.py::TestProviderState`, `test_v31_matrix.py::TestNoSecretLeakage` |
| Env template | `.env.example` at repo root documenting every variable incl. auth bootstrap and CORS; secrets stay gitignored (`.env` never committed — verified via `git log --all -- .env`) | — |
| Deploy guardrails | Fail-closed preflight (8 checks) + wrapper refusing legacy checkouts; browser release identification | `scripts/test_deploy_preflight.py` (25), `releaseIdentity.test.js` (9) |
| Backup/restore tooling | WAL-aware backup with SHA256 + integrity + FK verification; keep-last-N retention; disposable-target restore rehearsal | `scripts/test_backup_database.py` (12), `scripts/test_restore_rehearsal.py` (11) |
| Alert definitions | 9 actionable alerts with thresholds and runbook pointers, local evaluation engine | `scripts/test_alerts.py` (21) |

## 3. Residual risk (accepted for V3.1)

- **Auth remains disabled in production.** All M1 code paths are prepared and
  tested, but activation changes production state and stays user-gated per the
  operation contract. Until then, write endpoints accept anonymous traffic on
  the Tailscale-only surface.
- **No automated backup schedule.** Tooling exists; the cron entry must be
  installed by the user (documented in PRODUCTION_RUNBOOK.md).
- **`:latest` tags remain on the host** (not retagged by contract). Preflight
  + wrapper make accidental use unlikely; manual cleanup is a one-liner.
- **Healthcheck still probes `/health`** until the next image build.
- **No server-side token revocation** — accepted for a self-hosted,
  Tailscale-only threat model with 24 h TTL.

## 4. Verification evidence

- Backend: 1095 passed, 2 skipped (CI ignore/deselect list), including the
  15-test cross-cutting matrix (`test_v31_matrix.py`).
- Frontend: 635 passed (`node --test`), production build succeeds.
- Live rehearsal on david-lab (read-only toward production): restore rehearsal
  passed against the real 51 MB backup (SHA256 `a82529ec…` matched, integrity
  ok, 5380/3501/1879 rows); preflight 8/8 PASS on the release ops dir; legacy
  checkout REFUSED with 5 blockers; wrapper dry-run passed without mutating
  anything.
