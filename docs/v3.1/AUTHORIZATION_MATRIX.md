# SPECTRA V3.1 — Authorization Matrix

Date: 2026-11-10
Scope: who can call what, under both runtime configurations (auth disabled =
current production; auth enabled = post-activation). Reflects the M1 auth
hardening on `feat/spectra-v3.1-production-hardening`.

---

## 1. Roles

| Role | How it exists | Capabilities |
|---|---|---|
| Anonymous caller | Any HTTP client reaching the API | Governed by the auth mode (see §2) |
| Authenticated user | `Authorization: Bearer <token>` issued by `POST /auth/login` against a row in `users` | Own conversations; catalog reads |
| Admin | A `users` row with `role="admin"` (created only via `backend/app/scripts/bootstrap_admin.py`) | Same as user, plus bootstrap-audit surface; admin operations may expand in future releases |

Notes:
- Passwords are strength-checked and hashed (bcrypt-class) by the bootstrap CLI;
  it refuses weak passwords and refuses to run twice against a populated
  `users` table (fail-closed bootstrap, F-08).
- Tokens are stateless HS256 bearers, TTL 24 h (`SPECTRA_AUTH_TOKEN_TTL_SECONDS`);
  verification fails closed (missing/weak secret → tokens never verify).

## 2. Endpoint authorization (auth disabled — CURRENT PRODUCTION STATE)

`SPECTRA_AUTH_ENABLED` is unset in production: `require_auth` returns `None`
(guest). Ownership scoping is skipped; every caller shares every conversation.

| Endpoint group | Methods | Effective access | Data exposure |
|---|---|---|---|
| `/health`, `/ready`, `/release`, `/metrics` | GET | Public | Health/migration/aggregate metrics only; no secrets, no PII |
| `/hardware`, `/hardware/{id}`, `/comparison`, search/filter routes | GET | Public read | Full hardware catalog (5380 rows) |
| `/build/chat`, `/hardware/chat`, `/comparison/explanation` | POST | Public (503 until provider configured) | Conversation content stored unscoped — shared across all callers |
| `/auth/*` | POST | Public | Login/bootstrap surfaces; rate limiting OFF (opt-in, unset) |

Risk note (F-01, P1): any host on the tailnet can write build conversations.
The surface is Tailscale-only (`100.113.157.0:8080`), which is the only reason
this is Medium likelihood.

## 3. Endpoint authorization (auth enabled — POST-ACTIVATION TARGET)

With `SPECTRA_AUTH_ENABLED=1` and a valid `SPECTRA_AUTH_SECRET` set:

| Endpoint group | Methods | Access | Scoping |
|---|---|---|---|
| `/health`, `/ready`, `/release`, `/metrics` | GET | Public (deliberate: diagnostics for the operator) | No secrets in payloads (tested) |
| `/hardware`, `/comparison`, search routes | GET | Public read (catalog is non-sensitive) | — |
| `/build/chat`, `/hardware/chat`, `/comparison/explanation` | POST | **Bearer required** (401 without) | Conversations scoped to the authenticated user |
| `/auth/login` | POST | Public | Returns a 24 h token on success |
| Another user's conversation by id | GET/POST | **403/404 — IDOR-blocked** | Ownership enforced in the service layer |

IDOR and token-lifecycle behaviour is regression-covered in
`backend/app/test_auth_security.py` (cross-user access, expired tokens, bad
signatures, user-deletion invalidation).

## 4. Rate limiting

| Surface | Opt-in variable | Default (unset) | Notes |
|---|---|---|---|
| Catalog/reads | `SPECTRA_RATE_LIMIT_PUBLIC` | 240/min when enabled | Per-IP fixed window |
| AI endpoints | `SPECTRA_RATE_LIMIT_AI` | 30/min when enabled | Stacks with the M4.4 concurrency bound (`SPECTRA_AI_CONCURRENCY`, 4 default) which returns 429 rather than queueing |
| Trusted proxies | `SPECTRA_TRUSTED_PROXIES` | empty → client IP taken directly | Required when behind a proxy for correct per-IP limiting |

Both limiters are currently DISABLED in production (F-01 companion). Enabling
them is an env change (user-gated).

## 5. Operational authorization boundary (who may change the system)

| Action | Mechanism | Authorization |
|---|---|---|
| Deploy a release | `backend/app/scripts/deploy_release.sh` | Runs only from `/home/david/releases/spectra-<sha>-ops` after an 8-check preflight; refuses legacy checkouts and SHA mismatches |
| Restore a backup | `restore_rehearsal.py` (rehearsal) | Rehearsal refuses live-looking paths; the REAL restore over the live DB is a manual, user-executed step (documented in the runbook) |
| Create admin | `bootstrap_admin.py` | Container-internal execution; refuses populated users table; not run in production during this operation |
| Retire a backup | `restore_rehearsal.py --prune` | Keeps newest N; only touches `backup*.db`-pattern files; refuses to delete when the surviving set would be empty |
| Change production env | Host-side `.env` / compose | **User-gated** — never performed by automation in this operation |

## 6. Coverage

| Check | Where tested |
|---|---|
| 401 on protected write without token | `test_auth_security.py`, `test_v31_matrix.py` |
| IDOR cross-user isolation | `test_auth_security.py` |
| Expired/invalid token fail-closed | `test_auth_security.py` |
| Bootstrap refuses weak password / second run | `scripts/test_bootstrap_admin.py` (9 tests) |
| Secret never in `/release` or `/metrics` output | `test_v31_matrix.py::TestNoSecretLeakage` |
| 429 on concurrency exhaustion | `test_v31_matrix.py::TestAIEndpointFailureModes` |
