# S-1 Frontend Security Headers — Fix & Staging Verification

**Date:** 2026-11-16 · **Status:** APPLIED TO STAGING, VERIFIED · **Scope:** staging 8096 only (prod untouched)

## What changed
`Dockerfile.frontend` (src clone at `dcfd7df`, staged as `s1` build):
1. Server-level `add_header` for `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
   `Referrer-Policy: no-referrer`, `Content-Security-Policy` — all with `always`.
2. CSP derived from the actual served artifact (not guessed):
   `default-src 'self'; script-src 'self' 'sha256-w9eABZuoe9jkbDmw0yxZTUjdDLgEWhWOqkKI0M+zbNM='; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
   — hash = the single inline theme-boot script (852 bytes, hex c3d78005…cd3 / base64 w9eABZuo…bNM=).
3. `proxy_hide_header` + explicit re-declare in `location /api/` — prevents duplicate CSP
   (backend's own strict `default-src 'none'` + nginx server-level header).
4. Security headers re-declared inside `/assets/` and `=/index.html` (nginx add_header inheritance:
   a block with any add_header of its own inherits none).

## Non-obvious facts discovered (matter for cutover)
- nginx `add_header` inheritance rule required re-declaration in 2 locations.
- CSP hash must be **base64**; first attempt used hex → real browser BLOCKED the theme boot
  (Playwright violation message supplied the correct hash). Fixed and re-verified.
- Backend already sends strict headers; without proxy_hide_header, `/api/*` responses carried
  BOTH backend and nginx CSP directives (duplicate headers) — found in first verification pass, fixed.
- `location /` uses `try_files … /index.html` → internal redirect re-enters `location = /index.html`,
  so that location's header set governs all SPA fallback responses.

## Evidence
- Headers verified on 5 response classes (/, /index.html, JS asset, CSS asset, /api/ready):
  all 4 security headers present exactly once per response; cache semantics unchanged
  (`no-cache` HTML; `public, immutable` assets). Script: `/tmp/verify-headers.sh` output retained here.
- Functional: 56/56 (h25.py) against 8096 after the swap.
- Real-browser DOM (Playwright Chromium, fresh context): 200, theme booted (`data-theme=light`),
  6 build slot cards, compatibility chip rendered, **0 console errors, 0 pageerrors, 0 CSP violations**.
- Diff: `s1-dockerfile.diff` (57 lines). Image `spectra-frontend:m25-staging-dcfd7df-s1` = `39e8a6c43f6e`.
- docker-compose.m25.yml now pins frontend image `…dcfd7df-s1` (backend unchanged `cd512196…`).

## Rollback
Re-point compose image tag to `spectra-frontend:m25-staging-dcfd7df` (`0ae625ae32fd`) + recreate.

## S-1 status after this change
RESOLVED for M2.5 frontend. Verdict upgrade path: CONDITIONAL_GO → GO_FOR_AUTHORIZED_CUTOVER
once this diff is applied to the prod build (same Dockerfile, fresh build at cutover per runbook §4).
