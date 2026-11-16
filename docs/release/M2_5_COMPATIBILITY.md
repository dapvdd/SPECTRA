# SPECTRA M2.5 — Release Compatibility (Phase F)

**Verified:** 2026-11-15/16 by source diff (`75eba50^ → dcfd7df`), live API probes (8080/8095/8096), and **runtime rehearsals** of the old backend against both v2 and v3 databases.
**Evidence:** rehearsal logs `rehearsal/uvicorn-prod*.log`, route-diff outputs in session evidence.

## 1. API compatibility (backend ↔ frontend)

Route inventory diff of `backend/app/main.py` between the production commit's application code and M2.5:

| Direction | Routes |
|---|---|
| **Added in M2.5** | `POST /build/compatibility/check` · `GET /metrics` · `GET /release` |
| **Removed** | none |
| Unchanged paths | `/`, `/health`, `/ready`, `/auth/*`, `/hardware`, `/hardware/facets`, `/hardware/{id}`, `/hardware/{id}/benchmarks`, `/hardware/{id}/provenance`, `/hardware/recommend`, `/comparison/*`, `/build/chat`, `/build/conversations*` |

Behavioral notes on shared routes:
- `/hardware`: same signature and `X-Total-Count` semantics.
- `/hardware/facets`: same response shape; M2.5 improvement — a facet list no longer applies its own dimension filter to itself (manufacturer options stay complete under an active type filter). Additive/beneficial; same schema.
- `/build/conversations*`: request/response schema unchanged; `owner_id` semantics unchanged.
- `/release` 404 in prod is explained by its absence at 75eba50 (pre-existing, not a regression).

**Frontend endpoints** (from `frontend/src` grep): all routes served by the M2.5 backend; the only M2.5-only call is `/build/compatibility/check` (new feature). No frontend calls were removed.

## 2. Database schema compatibility

- v2 → v3 is **additive-only** (4 new spec tables + `field_provenance` CHECK widening via table rebuild; provenance rows preserved 39,440/39,440).
- Production code at 75eba50 defines **no** ORM models for the new tables, never calls `create_all`/`init_db` at startup, and its entrypoint only seeds a *missing* DB from a template. Therefore the old backend **ignores the v3 tables entirely**.
- **Proven by rehearsal (Strategy A viability):** old code (worktree at `75eba50^`) started against the **v3-migrated** rehearsal DB → `/ready` 200 `tracked-version-3`, catalog + facets + conversation create/reset all 200. The old backend runs cleanly on the v3 schema.
- **Proven by rehearsal (Strategy B viability):** old code against the pristine **v2** backup copy → `/ready` 200 `tracked-version-2`, catalog OK, conversation create 200.

## 3. Compatibility rules version

- M2.5 reports `rules_version: M2.5-RULES-v1` on `/build/compatibility/check` (verified live), with the seven-rule set (cpu-motherboard-socket, ram×3, storage, psu-build-wattage, gpu-motherboard-slot) and documented semantics: PSU two-tier floor (`INCOMPATIBLE` below floor(sum(TDP)×1.3+0.5), `UNKNOWN` at/above), GPU-slot rule `UNKNOWN` whenever slots>0, aggregate precedence `INCOMPATIBLE > UNKNOWN > COMPATIBLE` (live-verified: 450 W PSU + 425 W floor → INCOMPATIBLE; all-unknown → UNKNOWN).
- Old backend has no compatibility endpoint at all — no version skew possible there.

## 4. Catalog facets & categories/slots

- Six hardware categories confirmed end-to-end on 8096: facets `CPU 3501 / GPU 1879 / RAM 3 / STORAGE 2 / MOTHERBOARD 2 / PSU 2`; DOM capture showed six tabs, six build-slot cards, six Browse buttons (incident UI-2511 closed as reviewer error — see `UI_2511_DISCREPANCY_INVESTIGATION.md`).
- Six Build Planner slots (`BUILD_SLOTS`) with per-slot specs, provenance, and the PSU/GPU advisory semantics above.

## 5. AI context (compatibility digest)

- M2.5 `BuildContext` gains an **optional** `compatibility` digest (`BuildCompatibilityDigest | None`); frontend omits the key when no digest exists (test-asserted).
- **Version-skew risk found:** old backend `BuildContext` uses `extra="forbid"` and lacks the field → a **new-frontend + old-backend** mix would 422 on `/build/chat` whenever a digest is sent. This makes frontend/backend **atomic replacement the required cutover shape** (see §7). The reverse mix (old FE + new BE) works but ships stale UX.

## 6. Existing production data compatibility

- Conversations: 7 rows, schema unchanged → M2.5 reads them unchanged (staging copy proved: conversations 1–7 intact through v3 migration and app startup).
- Users: 0 rows; users table exists in both schemas (v2 migration added it; prod ORM models it in `auth.py`).
- Build state: build slots are request-time state (no persisted build tables) — nothing to migrate.
- Fixture ids used for verification on staging copies: CPU 705 (i9-13900K, FCLGA1700, 125 W), GPU 3723/5119 (RTX 4090, 450 W→floor breach), MB 5386/5387, PSU 5388 (750 W)/5389 (450 W).

## 7. Browser cache & static assets

- Nginx config byte-identical between prod and M2.5: HTML `no-cache` (ETag revalidation), `/assets/` immutable 1y, hashed filenames (`index-DG6KnBNx.js` prod vs `index-B5U1PO0u.js` M2.5). A cutover swaps the shell; browsers revalidate `index.html` immediately and fetch the new hashed assets — no stale-shell path (no service worker in either build). UI-2511 proved the cache story empirically.

## 8. Release metadata

- M2.5 `/api/release`: version, SHA, built_at populated; digest null (see Security Review S-2 / Provenance §5).
- Old backend lacks `/api/release` — cutover adds the diagnostic surface.

## 9. Conclusion

Backend/frontend/database are mutually compatible at `dcfd7df`; the only skew risk is the new-FE/old-BE mix, eliminated by an **atomic compose replacement** of both services in one window. Rollback to the old V3 images after migration is **proven viable** (old code runs on v3 DB, ignoring new tables); rollback with DB restore to v2 is also proven. No old-image rollback assumption was left unverified.
