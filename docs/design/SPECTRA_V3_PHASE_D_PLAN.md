# SPECTRA V3 Phase D — Experience Reconstruction Plan

**Status:** IN_PROGRESS · **Branch:** `feat/spectra-v3-experience-reconstruction` (from main @ f0e377d) · **Date:** 2026-11-08

## Verified baseline (Phase 0 audit)

| Fact | Evidence |
|---|---|
| React 19 + Vite 8, plain JS, **no router**; all views are conditional sections in one `App()` (4,322 lines) | `frontend/src/App.jsx` |
| Two CSS layers: `App.css` (89.7 KB, V2 component styles) + `spectra.css` (46.6 KB, V3 tokens & partial overrides loaded last) | `frontend/src/` |
| Pure-logic modules fully unit-tested: **611 node tests pass**; build green; oxlint = 3 pre-existing warnings | run logs 2026-11-08 |
| Local dev DB was **empty**; full 5,380-record catalog lives in `data/spectra_staging.db`; disposable dev copy made at `data/spectra.db` (gitignored; staging untouched) | sqlite counts |
| Backend healthy on :8000; frontend dev on :5173 | `/health` → 200 |
| Baseline screenshots (10: home/detail/compare × dark/light @1440, home × tablet/mobile × both themes) — **0 console errors** | `docs/design/evidence/before/` |
| Measured V2 defects: **h1 = 88px**, **hero = 1017px on a 900px viewport (dominates on every page/viewport)**, catalog below the fold | baseline manifest |
| `GET /hardware/facets` returns **200** against the current backend — frontend request matches contract | baseline manifest API log |

## Measured weaknesses

1. Hero consumes a full viewport; 88px headline; catalog buried below fold.
2. Filters + api-status line bloat the hero; no sort control; type filter has no facet counts; no segment filter surface.
3. Box-heavy components: chrome-heavy cards, nested panels.
4. No skeleton states (spinner + text only), no animated filter/search feedback, no section transitions.
5. Detail masthead plain; provenance underused; comparison header not sticky.

## Root cause of the known facets 422 (Phase 9)

`GET /hardware/facets` is declared **before** `/hardware/{hardware_id:int}` in `backend/app/main.py` and the frontend request (`catalog.js:getHardwareFacetsUrl`) matches its contract exactly. **A deployed backend older than this route resolves `facets` against `/hardware/{hardware_id:int}`, failing int parsing → 422.** This is a deployment version mismatch, not a frontend defect. Local verification: 200. Documented as a deployment blocker; no masking, no contract change.

## Implementation milestones

| # | Milestone | Content |
|---|---|---|
| D1 | App shell & homepage | Compact hero (no 100vh, h1 ≤ ~3rem band), search promoted, filters moved to catalog head, CPU/GPU quick paths, compact api status, Signal readout retained |
| D2 | Catalog | Command bar (segmented type + sort + mono readout), editorial hairline cards with 2-spec previews, skeleton/empty/error states, facet counts |
| D3 | Hardware detail | Masthead readout strip, hairline section rules, quality badge in performance head, compact provenance list |
| D4 | Comparison | Sticky table header + participant identity, winner emphasis, restyled A/B pair (data & semantics unchanged) |
| D5 | Recommendation & build | Fit modal → drawer pattern, build workspace polish, honest empty/limit states |
| D6 | Motion | Section-swap entrances, filter/chip feedback, drawer transitions, staggered reveals (existing Phase C primitives), all transform/opacity, reduced-motion respected |
| D7 | Theme parity | Dark/light contrast verification (scripted ratio checks), glow/border/charts parity |
| D8 | Verification & report | After screenshots, full suite, build, lint, Playwright smoke + a11y checks, `SPECTRA_V3_PHASE_D_REPORT.md` |

## Constraints honored

- No API contract changes; no new recommendation features; no fabricated data; decorative illustrations only (no fake hardware photos).
- Pure logic modules keep passing; new logic (sort) = new pure module + tests.
- No router (documented decision); Settings/Overview proposals remain out of scope.
