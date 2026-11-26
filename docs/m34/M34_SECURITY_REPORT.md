# M3.4 Security Report (Task 2)

**Date**: 2026-11-26
**Branch**: `feat/m34-fortress` (baseline `main`@`5c2c7d9` = deployed production)
**Scope**: authentication boundaries, network exposure, secrets, CORS/CSP, DB permissions, dependencies, container posture.
**Method**: repository audit + read-only production inspection (`ssh david-lab`) + targeted probes. No configuration was changed on production.

## 1. Fixed: F-2 — POST /auth/register 500 when auth disabled

**Root cause** (verified in source): `register()` called `issue_token(user.id)`
unconditionally; `issue_token()` requires `SPECTRA_AUTH_SECRET` via
`_require_secret()`, which raises `RuntimeError` when the secret is unset —
exactly the auth-disabled case. Unhandled → HTTP 500.

**Fix** (this branch): `issue_token_or_placeholder()` returns a constant
placeholder that `verify_token()` can never accept when auth is off and no
secret exists; registration keeps its pre-registration contract (201, user
row created). New failure mode `SPECTRA_AUTH_REGISTRATION_ENABLED=0` → 403
"Registration is disabled." in both auth modes (no user row created; login
unaffected).

**Behavior matrix now enforced** (tested in `backend/app/test_m34_auth_fix.py`):

| Condition | Result |
|---|---|
| Auth enabled, valid registration | 201 + signed token |
| Auth enabled, registration disabled | 403 |
| Auth disabled | 201 + placeholder token (never verifies) |
| Auth disabled, registration disabled | 403, no user row |
| Invalid credentials (short password, reserved/duplicate/empty username) | 422 |
| Login, bad credentials | 401 (+ WWW-Authenticate) |
| Protected ops, auth off | open (approved posture, unchanged) |
| Protected ops, auth on, no/invalid token | 401 |

## 2. Production exposure audit (read-only, 2026-11-26)

| Check | Evidence | Finding |
|---|---|---|
| Backend port exposure | `ss -tlnp` on david-lab: only `100.113.157.0:8080` (nginx); **no** 0.0.0.0/8000 | PASS — backend unreachable off-host |
| Frontend bind | nginx binds the tailscale IP only; LAN 192.168.1.x unreachable | PASS |
| Admin/ops endpoints | `/ingestion-runs`, `/publication-batches` etc. gated by `Depends(require_auth)`; auth off → open | Documented approved posture; gated correctly when auth on |
| Tailnet reachability | `tailscale status`: devices under **3 user namespaces** (`dapvdd@`, `mukhlisinfatah406@`, `devinevos09@`) | **FINDING F-1 (critical posture)**: tailnet membership ≠ authorization; with auth disabled every tailnet device has full API access incl. conversation reads/writes |
| Tailscale ACLs | ACL/grant inspection requires tailnet admin console access (not available via SSH) | NOT VERIFIABLE from this session — owner should confirm ACL restricts :8080 to owned devices |
| Secrets | `.env` never committed (gitignored); `GEMINI_API_KEY` unconfigured in prod; auth secret unset (auth off) | PASS for current posture; secure-auth template prepared (`SECURE_AUTH_CONFIG.example.env`) |
| CORS | allowlist enforced; arbitrary origins get no grant (regression-tested) | PASS |
| CSP | nginx: hash-pinned script-src, no unsafe-inline/eval for scripts; backend JSON CSP `default-src 'none'` | PASS |
| DB permissions | single volume `spectra-sqlite-data`, app-writable only; containers currently **root** | see F-3 → fixed in Task 3 |
| Dependency vulnerabilities | `npm audit` on frontend: reported advisories in dev tooling chain (non-runtime); backend pinned requirements | RESIDUAL: add `pip-audit` to CI (recommended, not blocking) |
| SQLi / traversal / malformed JSON | regression-tested (parameterized ORM; 400 traversal; 422 malformed) | PASS |

## 3. Findings and dispositions

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| F-1 | Critical (posture) | Tailnet membership treated as authorization while 3 user namespaces share the tailnet; auth disabled | Auth config prepared (fail-closed template + activation procedure); ACL verification instructions included; **no live change without owner approval** |
| F-2 | Medium (correctness/security) | register 500 auth-off | **Fixed on branch** |
| F-3 | Medium (hardening) | Containers run as root; no cap drop / no-new-privileges / resource limits | Fixed in Task 3 (`compose.m34.yaml` + Dockerfile non-root) |
| F-4 | Low | nginx buffers 1 MB unfiltered `/api/hardware` to disk temp file | Addressed in Task 6 (in-memory buffering + gzip) |
| F-5 | Low | No dependency audit in CI | Recommended follow-up documented in M34_RELEASE_READINESS.md |

## 4. Things deliberately NOT done

- No change to live authentication (`SPECTRA_AUTH_ENABLED` stays unset in production).
- No Tailscale ACL modifications (admin console out of scope; instructions only).
- No secret values generated, transmitted, or committed.
- No dependency major-bump "fixes" without owner review.
