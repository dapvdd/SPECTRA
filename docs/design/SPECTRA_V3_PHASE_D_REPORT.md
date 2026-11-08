# SPECTRA V3 — Phase D: Complete Experience Reconstruction Report

**Status:** READY_FOR_VISUAL_REVIEW · **Branch:** `feat/spectra-v3-experience-reconstruction` · **Date:** 2026-11-08
**Baseline:** main @ `f0e377d` · **Plan:** `SPECTRA_V3_PHASE_D_PLAN.md`

---

## 1. Architectural changes

| Change | Detail |
|---|---|
| New experience layer | `frontend/src/experience.css` — loaded **after** `spectra.css`; extends V3 tokens (no hardcoded hues); owns compact hero, command bar, skeletons, readout strip, sticky comparison identity, drawer/view entrances |
| New pure module | `frontend/src/catalogSort.js` (+10 tests): name/date ordering, ISO-date validated, nulls last, name tiebreak, backend filtering untouched |
| Homepage recomposed | Hero is a band (`min-height: 0`, 549px @1440, was 1017px+); h1 64px (was 88px); search + CPU/GPU quick paths (live facet counts) replace the paragraph+filter block; filters moved onto the catalog head as a command bar with sort control |
| Catalog states | Skeleton record rows (6, aria-hidden, sr-only status) replace spinner+paragraph; empty/error states preserved |
| Detail masthead | `DetailReadoutStrip` renders key specs (CPU: cores/threads/clocks/TDP; GPU: VRAM/type/bandwidth/bus) as mono readouts; N/A values filtered out honestly |
| Comparison | Sticky first column (spec labels) during horizontal scroll; header backdrop; winner gold emphasis preserved; table semantics unchanged |
| Motion | Drawer slide-in (fit modal), view entrance settle, shimmer skeletons, ambient glow + stagger inherited from Phase C — all transform/opacity, full `prefers-reduced-motion` fallbacks (verified: `animationName: none`) |
| Out of scope (by design) | No router, no new recommendation features, no Settings/Overview proposals, zero backend changes |

## 2. Pages reconstructed

- **Homepage** (hero, quick paths, command bar, catalog grid, skeleton states)
- **Hardware detail** (CPU + GPU masthead readout strip; provenance/performance surfaces preserved)
- **Comparison** (sticky identity column, drawer-independent restyle)
- **Recommendation/build surfaces** (fit modal drawer transition; build workspace, suitability, and chat flows verified unchanged and functional)

## 3. Before/after evidence

All screenshots: `docs/design/evidence/before/` and `docs/design/evidence/after/` (10 PNGs each: home/detail/compare × dark/light @1440, home × tablet/mobile × both themes) + manifests with per-shot metrics and API logs.

| Metric (1440×900 dark) | Before | After |
|---|---|---|
| h1 font size | 88px | 64px |
| Hero height | 1017px (**dominates viewport**) | 549px (61%) |
| Hero dominates viewport (all viewports) | true | **false** (desktop 549px, tablet 799px, mobile 691px) |
| Sort control | none | 5 options |
| Type-filter facet counts | none | live counts |
| Skeleton loading state | none (spinner) | record rows |
| Console errors | 0 | 0 |

## 4. Test results

- **Unit:** 621/621 pass (`node --test src/*.test.js`, was 611; +10 catalogSort)
- **Lint:** oxlint — 3 warnings, all pre-existing at baseline (`set-state-in-effect` in App.jsx:3105, useRecommendation, useSuitability); no new findings
- **Build:** `vite build` green (102.89 kB CSS / 343.31 kB JS)
- **Interaction smoke:** 13/13 (`docs/design/evidence/interaction-smoke.json`): search, clear, CPU filter, sort-newest, detail open/readout/back, compare two slots, comparison table (2 winner cells), skip-link first tab stop, fit modal ESC, zero page errors
- **A11y:** WCAG contrast pairs PASS both themes (body 17.93:1/16.08:1, muted 5.45/6.99, nav 5.49/6.20, sort select 6.96/5.81); reduced-motion verified; no horizontal page overflow at 390/768/1440 in either theme
- **Backend:** untouched (0 diffs); `pytest` not re-run — out of Phase D scope

## 5. Remaining limitations

1. **`GET /hardware/facets` → 422 on the deployed environment is a deployment version mismatch, not a frontend defect.** The route is declared before `/hardware/{hardware_id:int}` in `backend/app/main.py` and the frontend request matches its contract exactly (`catalog.js:getHardwareFacetsUrl`). Locally it returns **200** (verified 12/12 times in this branch). On a backend older than this route, `facets` falls through to the int-typed detail route and fails validation → 422. **Resolution requires deploying a backend that includes the facets route** (or any backend ≥ Phase 1.3). No frontend masking was added — per mission instruction the failure is documented, and the UI already degrades gracefully (facet counts simply don't render).
2. No router: view transitions are single-entrance settles; shared-element transitions remain a proposal (per Motion spec §2).
3. Sort is client-side on the fetched catalog page (by design; backend still owns filtering/totals). Server-side sort would be a backend contract change — not authorized here.
4. Three pre-existing lint warnings (see §4) are untouched to avoid scope creep.
5. The reviewer should visually confirm screenshots (rendered verification here was programmatic: metrics, console, API logs — the reviewing model cannot view images).

## 6. Performance observations

- CSS 96.75 → 102.89 kB (+6.1 kB gzip +0.85 kB) for the full experience layer.
- JS +2.3 kB (catalogSort + view wiring).
- All new animations are transform/opacity only; ambient glow is opacity-only at 12s; skeletons animate opacity only; no continuous animation on data regions; `will-change` used once (drawer panel).
- Catalog interactions (search/filter/sort) are synchronous client operations over the already-loaded page; smoke test showed no perceptible delay at 12-card page size.

## 7. Deployment compatibility considerations

- `compose.yaml` builds `VITE_API_BASE_URL=/api` behind nginx — no frontend changes affect the deploy path; the new CSS/JS layers are hashed assets covered by the existing cache policy commit (`f0e377d`).
- **The facets 422 blocker (see §5.1) is resolved by deploying the current backend image, not by any frontend change.**
- No DB migrations, no production data touched. Local verification used a disposable copy of `data/spectra_staging.db` (gitignored); the staging DB was never written.

## 8. Git

- Branch `feat/spectra-v3-experience-reconstruction` from main @ `f0e377d`
- Commits: `6adab1c` (audit+plan+capture tooling) → `e4634bf` (homepage+catalog) → `e3fdaf1` (comparison+detail+drawer) → `84078d6` (sticky identity+verification scripts) → `eccab1d` (after evidence + compact small-viewports) → final report commit (this document)
- Pushed only to the feature branch; no merge, no deploy.
