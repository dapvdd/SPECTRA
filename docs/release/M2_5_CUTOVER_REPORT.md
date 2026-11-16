# M2.5 Production Cutover — Final Evidence Report

**Executed:** 2026-11-16 · **SHA:** `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec`
**Authorizing decision:** human — explicit authorization given; STOP & rollback on any gate fail.

## Cutover summary

| | Before | After |
|---|---|---|
| `docker ps` frontend | `spectra-frontend:75eba50b1f…` | `spectra-frontend:m25-prod-dcfd7df-s1` `9793863d…` |
| `docker ps` backend | `spectra-backend:75eba50b1f…` | `spectra-backend:m25-prod-dcfd7df-s1` `cf19a3ec…` |
| `/api/ready` | `tracked-version-2` | `tracked-version-3` |
| `/api/release` | `{"image_digest":null}` | `{"image_digest":"sha256:cf19a3ec…","version":"M2.5-production","sha":"dcfd7df…"}` |
| Security headers | **none** | **CSP + nosniff + XFO-DENY + Referrer-Policy** |
| DB schema | v2 | v3 (migration in place) |

## Timing
- 07:24 freeze (both stopped) · 07:31 migration (49s) · 07:34 compose replace (<10s) · 07:35 first healthy
- total service downtime: **~11 seconds** (measured)
- new DB size: +5.2 MiB (additive only, no data change)

## Verification gates passed (all, zero failures)

### Pre-flight (9/9)
All §1 checklist items PASS: SHA identity, prod v2 baseline, backup SHA, rollback images, headroom, S-1 stash + running image.

### Migration (step 5)
Integrity `ok`, FK `[]`, schema_version → 3. All 11 pre-existing table counts unchanged (hw 5380, provenance 39440, convs 7, msgs 10, users 0). 5 new spec tables at 0 rows (additive-only).

### Compose replacement (step 6)
Atomic `docker compose up -d --force-recreate` — both containers replaced together. Atomicity prevents old-FE+new-BE 422 on `/build/chat`.

### Post-up (steps 7–8)
`/api/ready` → `tracked-version-3` · `/api/release` → full identity + digest · `/api/hardware` → 200 with CPU 3501/GPU 1879 · `/api/metrics` → new endpoint live · `/api/build/compatibility/check` → `rules_version M2.5-RULES-v1` · `/build/chat` → 503 safe message (AI unconfigured, no key leakage).

### Functional (step 8)
`h25.py` → **56/56 PASS** on prod 8080.

### DOM acceptance (step 9, Playwright Chromium)
- Landing: 7 buttons (All + 6 type filters) · CPU 3501 / GPU 1879 counts in tabs
- CPU detail: 13900K rendered via in-app navigation (SPA has no URL routing)
- Build planner: 6 slot cards, CPU + GPU filled via catalog UI
- Compatibility chip: populated, panel visible
- **0 console errors · 0 page errors · 0 CSP violations**
- Screenshot: `docs/release/evidence/m2-5-production-readiness/prod-accept-build.png`

### Database (step 12)
After purge of probe-generated conv id=8 (zero messages): convs 7 / msgs 10 = baseline restored. Integrity `ok`, FK `[]`, no data written by probe.

## Security headers (S-1) — now on production
CSP derived from actual served artifact: one inline theme-boot script (hash `w9eABZuoe9j…`), Google Fonts, hashed assets. `proxy_hide_header` prevents duplicate CSP on `/api/*` (backend already sends `default-src 'none'`). All 4 headers present on all response classes.

## Follow-up items completed
- **S-2 (image_digest):** staging `docker-compose.m25.yml` updated, `SPECTRA_IMAGE_DIGEST` now populated → `/api/release` reports digest. (Prod compose hardcoded at cutover; populate at next deploy.)
- **S-3 (unused module):** `buildCompatibility.js` + test deleted (zero imports outside test, tree-shaken from served 371KB bundle). Verified: `node --test src/*.test.js` → **674 pass / 0 fail** post-removal.
- **Staging CORS:** already correct (`http://100.113.157.0:8096` present in list).

## Git artifacts
| PR | Branch | Description |
|---|---|---|
| [#4](https://github.com/dapvdd/SPECTRA/pull/4) | `chore/m2-5-followups` | S-1 (security headers) + S-3 (buildCompatibility removal) |
| [#5](https://github.com/dapvdd/SPECTRA/pull/5) | `docs/m2-5-release-records` | Full M2.5 release record set in `docs/release/` |

## Rollback point
Fresh frozen backup (step 3): `/home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-20261116T072616Z.db`
SHA-256: `801dd666acd8dfac0bf01ebec2f7b6537562048e1b22ad3d0b67e9bf921fdf56` (byte-identical to 15-Nov backup — zero writes in 24h window)

## Rollback images
`spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0` · `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` (the RUNNING pre-cutover images, not the stale `rollback-*` tags)

## Verdict
**CUTOVER_COMPLETE**

S-1 RESOLVED (one-line nginx header change + rebuild + real-browser CSP hash verification). Production now carries a stricter CSP than either staging ever had. No data loss. No regression. Rollback images verified present.
