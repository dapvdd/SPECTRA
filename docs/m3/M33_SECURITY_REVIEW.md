# M3.3 Security Review Report (Phase 8)

**Date**: 2026-11-25
**Scope**: the isolated rehearsal deployment of RC `5c2c7d9` on DavidLab
(`100.113.157.0:8097`), plus auth/AI configuration code review. Read-only
probes; no intrusive exploitation; no production mutations.
**Depth**: configuration + boundary probe review (not a full pen test).

## 1. Deployed configuration facts

| Item | Value | Source |
|---|---|---|
| `SPECTRA_AUTH_ENABLED` | unset → auth **disabled** (same as current prod) | env + `GET /api/auth/status` → `{"auth_enabled":false}` |
| `SPECTRA_AUTH_SECRET` | not set (moot while auth off) | env |
| AI | `GEMINI_API_KEY` unset → `ai_provider:"unconfigured"` | `GET /api/release` |
| DB | isolated rehearsal volume; **publisher still refuses the prod-named path** (verified live: ValueError on `/app/data/spectra.db`) | publisher `_PROD_FORBIDDEN = "data/spectra.db"` |
| Users table | empty (0 users), rehearsal + prod | Phase 0 baseline |

## 2. Probe evidence (script `m33_security.py` + follow-ups)

| # | Probe | Result | Verdict |
|---|---|---|---|
| 1 | `GET /api/auth/status` | 200 `{"auth_enabled":false}` | expected (matches prod posture) |
| 2 | Ops endpoints without token (`/api/ops/ingestion-runs`, `/api/ops/publication-batches`) | 200, JSON served | **finding F-1** (expected while auth off; gating exists and is unit-tested — 401 asserted in `test_auth_security.py` when auth on) |
| 3 | Cross-origin `Origin: http://evil.example.com` on `/api/health` | **no** `Access-Control-Allow-Origin` reflection | PASS — CORS allowlist enforced |
| 4 | SPA response headers | CSP `default-src 'self'; script-src 'self' 'sha256-…'`; `X-Content-Type-Options: nosniff` present | PASS |
| 5 | SQL-injection probe `name='; DROP TABLE hardware;--` | 200 (parameterized query; returns rows list, no 5xx, table intact) | PASS |
| 6 | Path traversal `/..%2f..%2f..%2fetc%2fpasswd` | 400 Bad Request from nginx | PASS |
| 7 | `POST /api/auth/register` with auth OFF | **500 Internal Server Error** (`RuntimeError: SPECTRA_AUTH_SECRET is not set` at `issue_token`) | **finding F-2** |
| 8 | Builder `{"cpu":null}` (null slot) | 200 honest UNKNOWN, no crash | PASS |
| 9 | Builder wrong-type id (`GPU hardware must be a GPU`) | 422 with clear validation | PASS |
| 10 | Chat message on unconfigured AI | user message persisted 201; AI reply honestly unconfigured (no fabricated content) | PASS |
| 11 | `/api/ready` exposes only `{status, database, migrations}` | no internals leaked | PASS |
| 12 | Malformed JSON bodies | FastAPI 422 with structured detail, no stack trace leak | PASS |

## 3. Findings

**F-1 — Ops endpoints readable while auth disabled (accepted posture).**
`/api/ops/ingestion-runs` and `/api/ops/publication-batches` are reachable
unauthenticated in the rehearsal deployment because `SPECTRA_AUTH_ENABLED`
is off — identical to the current production posture (M2.5) and to the
release plan. The auth gate itself is correct: with auth enabled, unit tests
assert 401 without token and 200 with a valid token
(`backend/app/test_auth_security.py:426-439`). Read-only operational data
(batch counts, provenance metadata); no PII, no secrets. **Owner decision
for production cutover**: either keep auth off (LAN-only tailscale exposure
as today) or set `SPECTRA_AUTH_ENABLED=1` + `SPECTRA_AUTH_SECRET` in the
production compose. Not a regression introduced by M3.3.

**F-2 — `POST /api/auth/register` returns 500 while auth disabled.**
Registering a user with auth off raises `RuntimeError` inside
`issue_token` (`_require_secret()`), surfacing as HTTP 500. The endpoint is
documented as "available regardless of SPECTRA_AUTH_ENABLED" (docstring),
but half-works: the user row would be created, then token issuance fails —
client gets a 500 and no feedback. Impact: misleading error for operators;
no data exposure (500 contains no stack trace). Pre-existing M2.x behavior,
unchanged by M3.3. **Recommendation (post-release)**: return 403 with
"authentication is disabled on this instance" when `auth_enabled=false`,
or make register+login fully functional when a secret is set even if auth
is off. Not a release blocker (auth is off in production by design; user
creation is an operator action).

**F-3 — Container runs as root with a broad app dir (informational).**
Both images run as root (no `USER` directive). Attack surface is the same
as the current production image; SQLite + FastAPI behind nginx with CSP.
Recommendation for a future hardening pass: run as non-root user, drop
unused capabilities. Not M3.3-specific; not a blocker.

## 4. Data-integrity security posture (release-relevant)

- Publisher prod-path refusal verified **live** on the RC code path
  (attempted publication to `/app/data/spectra.db` → ValueError; the
  rehearsal recovery used `/app/data/rehearsal_publish.db` + copy-swap
  instead). The evidence gate cannot be bypassed by path confusion.
- Fail-closed publication held: 381 UNRESOLVED manifest candidates produced
  **zero** rows; only the 62 MATCHED verified SKUs published.
- No secrets in repo, env, or logs reviewed; `GEMINI_API_KEY` unset
  everywhere; no tokens issued (users table empty).
- Injection/traversal probes caused no 5xx and no data change (integrity ok,
  FK 0 after all probes).

## 5. Coverage limits

No dependency CVE scan (offline environment; versions unchanged from the
merged PR #8 CI state); no authenticated-path fuzzing (auth disabled); no
load/DOS testing (out of scope for rehearsal). Backend test suite includes
dedicated security tests (`test_auth_security.py`, `test_m3_security.py`) —
1546 passed / 0 failed at RC.

## 6. Verdict

No new security regressions introduced by M3.3. Two pre-existing findings
(F-1 auth-off posture, F-2 register-500) documented for the owner decision
at the authorization gate. Release readiness unaffected from a security
standpoint given the deployment posture is unchanged from current prod.
