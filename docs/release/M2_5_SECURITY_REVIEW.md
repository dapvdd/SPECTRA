# SPECTRA M2.5 — Security Readiness Review (Phase E)

**Audited:** 2026-11-15/16 · Read-only. No fixes applied, no speculative changes.
**Evidence:** `evidence/m2-5-production-readiness/phaseE-security.txt`, container inspections, source at `dcfd7df`.

## 1. Findings overview

| # | Finding | Classification |
|---|---|---|
| S-1 | Frontend (nginx) serves **no security headers** (no CSP, X-Frame-Options, nosniff, Referrer-Policy) — identical in prod 8080 and M2.5 8096 | **REQUIRED_BEFORE_CUTOVER** |
| S-2 | `/api/release` reports `image_digest: null` (empty `SPECTRA_IMAGE_DIGEST` in compose) | NON_BLOCKING_FOLLOW_UP |
| S-3 | Unused legacy client-side compatibility module (`frontend/src/buildCompatibility.js`) | NON_BLOCKING_FOLLOW_UP |
| S-4 | Backend `/build/chat` accepts a client-supplied compatibility digest (bounded) as an authoritative AI-context fact | NON_BLOCKING_FOLLOW_UP |

No BLOCKERs. Production was **not** modified; the classification of S-1 is the only item that gates cutover (with a one-line nginx header change, staged and tested first).

## 2. Detailed audit

### Authentication & authorization
- Auth disabled in both environments (`/auth/status` → `auth_enabled:false`; prod has no `SPECTRA_AUTH_ENABLED` set). Prod `users` table has **0 rows** — no credentials to sanitize.
- `POST /auth/register` works while auth is OFF (documented pre-registration pattern): bcrypt hashes, ≥12-char password enforced (422 verified), token inert while OFF.
- Conversation ownership: `_require_conversation_for_owner` scopes reads/writes to `owner_id`; all 7 prod conversations are legacy `owner_id=NULL` and remain accessible while auth is OFF. **Disclosure:** if auth is enabled later, NULL-owner rows become inaccessible to every authenticated user — a data-migration decision for that future change, out of scope here.

### Secrets
- Prod backend env names: `SPECTRA_DATABASE_URL`, `SPECTRA_CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL` — values never printed; `GEMINI_API_KEY` is an empty string in `compose.json` (name visible, value empty).
- Staging compose holds `SPECTRA_*` only; no shared secrets between staging and prod (separate compose files, no shared env files). AI endpoints fail safe: **503** `{"detail":"Gemini API is not configured…"}` — no key leakage, verified on both shapes of request.

### Frontend security headers & CSP/XFO (S-1)
- All three nginx frontends (8080/8095/8096) send only cache headers. Config is byte-identical between prod and M2.5 Dockerfiles (`diff` = 0 lines).
- Risk: the SPA can be framed and lacks `nosniff`. Exposure is limited (Tailscale-only bind, trusted LAN), hence REQUIRED_BEFORE_CUTOVER rather than BLOCKER.
- **Remediation path (prepared, not applied):** add to the `server {}` block in `Dockerfile.frontend`:
  `add_header X-Content-Type-Options nosniff; add_header X-Frame-Options DENY; add_header Referrer-Policy no-referrer;` (and optionally a restrictive CSP) → rebuild both images → staging verify → cutover. Header additions are additive and testable in staging first.

### API security headers
- M2.5 API responses (verified on 8096): `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `content-security-policy: default-src 'none'; frame-ancestors 'none'` — the JSON API is fully locked down at `dcfd7df`.
- Prod API (75eba50 code): **none** of these (middleware added in M2.5) — the cutover strictly improves API headers. `x-request-id` present in both.

### CORS & trusted proxy
- Prod `SPECTRA_CORS_ORIGINS=localhost:8080,localhost:5173` is **stale** (no Tailscale origin). Browser calls to `/api/…` from the page served on :8080 are same-origin, so nothing breaks today; cross-origin tooling gets 400. M2.5 staging list includes `http://100.113.157.0:8096` and behaves correctly (preflight 200 + ACAO echo). **Action for cutover:** set prod CORS list to include the real origin (config-only, in the cutover compose).
- nginx sets `X-Forwarded-For/Proto`; app does not rely on trusted-proxy headers for security decisions (auth is token-based, no IP logic) — no proxy-trust vulnerability found.

### Container & Docker surface
- Prod containers: `privileged=false`, `cap_add=[]`, no docker.sock, only the data volume rw. M2.5 backend bind-mounts a host dir (staging-only pattern); production plan keeps the named volume → no new exposure.
- All three HTTP ports bind `100.113.157.0` (Tailscale) only — `ss -tlnp` verified; no public exposure.

### Writable mounts & logging
- Prod: single rw mount `/app/data` (the DB) — minimal and intended.
- Logging: request-id middleware logs ids, not bodies; `/metrics` is aggregate-only (bounded route templates, status classes, latency samples) — no user data, verified by code read + endpoint behavior.

### Backup permissions
- Backup file `0600`, backup dir root-squashed to `david`; backups live outside any container fs and outside the repo (nothing committable contains secrets or DB bytes).

## 3. Staging findings assessment (from staging deployment report)

1. **Missing frontend CSP/XFO** → classified **REQUIRED_BEFORE_CUTOVER** (see S-1 remediation path; low risk today, trivial to fix before cutover).
2. **Null image_digest** → NON_BLOCKING_FOLLOW_UP: provenance mechanism documented in the Provenance doc §5 (populate digest at deploy; staging recreate + compose edit requires authorization).
3. **Unused compatibility client module** → NON_BLOCKING_FOLLOW_UP: `frontend/src/buildCompatibility.js` has zero non-test imports (grep-verified) and is **tree-shaken out** of the deployed bundle (0 hits for `COMPATIBILITY_EXPLICIT_ASSUMPTIONS` / `buildPowerSuggestion` in the serving bundle); it is dead weight in the repo only. Remove in a normal PR.
4. **Client-supplied digest validation** → NON_BLOCKING_FOLLOW_UP: the digest is schema-bounded (`extra=forbid`, `Literal` states, ≤7 rule results with 600-char explanation cap, ≤7 unresolved with 300-char cap, ≤6 positive-int slots) and the prompt treats it as a pass-through of SPECTRA's own verdicts; with AI unconfigured the surface is dormant. Revisit hardening (e.g. server-side recomputation) when auth + AI are enabled.

## 4. Verdict

No BLOCKER. One REQUIRED_BEFORE_CUTOVER (S-1, one-line nginx header change + rebuild + staging verification), three NON_BLOCKING_FOLLOW_UPs. Security posture after cutover improves over production today (API headers added). Production data isolation was preserved throughout this review.
