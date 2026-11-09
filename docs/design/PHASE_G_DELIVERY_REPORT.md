# SPECTRA V3 — Phase G: Premium Catalog & Interaction Polish — Delivery Report

**Status:** READY_FOR_PREMIUM_VISUAL_REVIEW · **Branch:** `feat/spectra-v3-phase-g-premium-polish` · **Date:** 2026-11-09
**Base:** Phase F HEAD `264e826a1931d49606926e8b730740e55b81c152` (verified == origin at session start; report format follows `docs/design/SPECTRA_V3_PHASE_F_REPORT.md`)

**Working-model limitation (stated up front):** this report is written by a text-only
working model. **It cannot view PNG screenshots** — aesthetic approval is a human step.
Every visual claim below is backed by structural DOM metrics, live probes, and the
committed evidence manifests under `docs/design/evidence/phase-g/`.

---

## 1. IMPLEMENTATION

Phase G refines the Phase F catalog into a premium, readable, information-dense
surface. No backend files were touched (`git diff 264e826..HEAD --stat -- backend/`
is empty); no API contracts changed; no new dependencies; no new animation/UI
libraries; all changes are token-driven CSS + JSX/logic in the existing layering.

### Commits (in order)

| Commit | Task | Scope |
|---|---|---|
| `bf7c9bd` | G1 | Catalog information architecture: availability-driven spec rows |
| `80c25ab` | G2 | Interaction polish + row-action semantics + mobile CSS fix |
| `7fba980` | G3 | Stable type facet counts + toolbar hierarchy polish |
| `f93a639` | G4 | Selected-state identity across catalog, detail, build, comparison |
| `0e0f693` | G5 | Typography floor coverage, copy de-dup, **GPU comparison crash fix** |
| `f975446` | G6 | Responsive and accessibility fixes (44-check suite) |
| `293098c` | G7 | Visual evidence + manifest + 390px spec wrap fix |
| `920ff37` | G8 | Drop dead `retryCardSpecs` left by the G1 row rebuild |

### Key code changes

| Area | File | Change |
|---|---|---|
| Row specs | `frontend/src/hardwareCard.js` | New `getCatalogRowSpecs()`: max 3 *available* specs in usefulness order, honest `"Not listed"` markers; `getHardwareCardPrimarySpecs`/`getGpuPrimarySpecRows` deleted |
| Rows | `frontend/src/App.jsx` (~4085–4240) | Row markup rebuilt; nested retry button removed; aria-labels added; `.comparison-header-type` kicker renders from JSX |
| Facets | `frontend/src/catalog.js` + App.jsx | `mergeTypeFacetCounts()` + dedicated `typeFacetCountsState`: type facets merge (last-known kept), manufacturer facets still replace |
| CSS | `frontend/src/experience.css` (+296 lines) | G1 row grid, G2 interaction states, G4 selected identity, G5 320/390 spec fixes — all appended as new sections (loads last, governs) |
| CSS | `frontend/src/spectra.css` (+9/−2) | Micro-label floor list extended (4 selectors); `.comparison-header-type` added to label families |
| Scripts | `frontend/scripts/` | `capture_phase_g.py` (evidence), `smoke_interactions_g.py` (11 checks), `verify_responsive_g6.py` (44 checks), `verify_g5_copy.py`, `verify_facets.py`, `audit_typography_g5.py` |

## 2. CATALOG ROW TRANSFORMATION (G1)

| Problem at Phase F baseline | Fix |
|---|---|
| Fixed 4-slot GPU spec rows repeated `N/A` / "No spec data" when data was missing | `getCatalogRowSpecs()` renders only *available* specs (probe: boost_clock null on 40% of 1,879 GPUs; memory_gb null 18%; every GPU has ≥2 non-null), capped at 3 in usefulness order |
| CPU rows showed fake spec strips | CPU rows show architecture / release_date identity only when the list payload actually carries it (present on 712/3,501 arch, 214 dates); otherwise the row is identity + manufacturer |
| "No spec data" as a euphemism | Honest **"Not listed"** per missing value at lower prominence — never a fabricated placeholder |
| 0.62rem microtext identity | Row/slot name at 1.08rem; mono labels at the token floor; values keep tabular numerals and refuse to clip |

Real-data examples committed in evidence: GPU `i752 Graphics` (2 non-null specs —
the missing-data case renders 2 honest rows), GPU `FireStream 9170` (9 non-null —
renders 3 most-useful rows), CPU `AMD Athlon Gold 7220C` (id 1).

## 3. INTERACTION & ROW SEMANTICS (G2)

Fixed via the new `smoke_interactions_g.py` suite (TDD):

- **Invalid HTML removed:** the retry button no longer nests inside the main row
  `<button>` (interactive-inside-interactive).
- **Accessible names:** compare/build row buttons carry aria-labels
  (`Compare <name>`, `Add <name> to build`).
- **Compare toggles OFF:** the button claimed `aria-pressed` but the handler was
  add-only; it now removes a selected row (smoke: `compare toggle removes a
  selected row`).
- Hover illumination, focus rings, press settle, refined skeletons — CSS only,
  every animation inside `@media (prefers-reduced-motion: no-preference)`.
- **Mobile fix:** the G1 `max-width:1180px` override broke 390px stacking;
  re-scoped to `min-width:861px and max-width:1180px`.

## 4. TOOLBAR & FACET STABILITY (G3)

**Confirmed defect (live probe):** `/hardware/facets?type=X` returns only type X in
its `types` array, so when a type filter was active the *other* type's hero
quick-path count vanished (Phase F screenshot symptom). Frontend-only fix:
`mergeTypeFacetCounts(prev, next)` keeps last-known counts for types absent from a
fresh response; App.jsx keeps a dedicated `typeFacetCountsState` (manufacturer
facets still replace wholesale — that behavior was correct).

Verified live with `verify_facets.py`: All → GPU → CPU → All keeps a stable
**3,501 CPU / 1,879 GPU** across every transition. Unit tests lock the merge
helper. Toolbar hierarchy: type filter primary, compact command bar, result
readout without duplicated copy (see §6).

## 5. SELECTED-STATE IDENTITY (G4)

CSS-only coherence pass over the four surfaces:

- Catalog row / build slot / comparison header share one name voice (1.08rem).
- Comparison slot indexes normalized to the 2xs label floor with the blue-soft token.
- The one-selected comparison instruction carries the quiet accent wash so the
  half-filled state reads as intentional.
- Reuses existing `HardwareVisual` primitives; no artwork duplication; verified
  in both themes via the committed evidence matrix.

## 6. TYPOGRAPHY, COPY, AND THE GPU CRASH FIX (G5)

- **Micro-label floor:** 4 sub-floor (0.66–0.68rem) label styles
  (`.benchmark-comparison-result`, `.source-license-tag`,
  `.benchmark-quality-badge`, `.suitability-confidence`) added to the
  `spectra.css` floor list. Letter-spacing was already governed by
  `--spectra-track-label` (0.1em) for the whole label family; dead App.css
  values left in place (cascade proven by computed-value probe).
- **Copy de-dup:** section-head "N shown" (misleading — it echoed the filtered
  server total, not the rendered count) → **Live/Updating** status; readout meta
  "All manufacturers" suppressed when unfiltered; "Sort page" → "Sort".
  `catalog.test.js` locks the new contract.
- **CRASH FIX (pre-existing at Phase F baseline, latent):** the GPU verdict
  effect called `requestGpuComparison` without importing it — the **first GPU
  comparison unmounted the whole app** (`ReferenceError`, React error boundary
  fallback, empty body). Phase 10 smoke never caught it because it always
  compared CPU-first. Fixed the import from `comparisonGpu.js`; smoke G now
  covers GPU-first compare (see §8 evidence). Before/after capture reproduces
  the baseline crash on the `before` side (§8).
- **Kicker correctness:** the hardcoded `::before{content:"CPU"}` mislabeled GPU
  comparisons as "CPU"; the kicker now renders from JSX as
  `.comparison-header-type` following `item.type` (verified live: GPU/GPU).
- **Latent dead code (found at G8):** G1's row rebuild orphaned
  `retryCardSpecs` in App.jsx (4th lint warning vs the known 3); removed in
  `920ff37`.

## 7. RESPONSIVE & ACCESSIBILITY (G6)

New `verify_responsive_g6.py` — **44/44 PASS** (dark+light × 1440/768/390/320):

- No page or card horizontal overflow at any viewport; catalog names not
  hard-truncated at 1440/768/390.
- Defects found & fixed:
  1. **320px:** the ≤560px 2-column spec grid left ~88px cells — narrower than a
     mono label + no-clip value. Single column under 380px.
  2. **390px GPU-filtered rows:** long GPU values ("System Shared") overflowed
     their 2-column cell. Values wrap under 480px (`overflow-wrap: anywhere`);
     desktop keeps the single-line instrument read.
- Touch targets ≥24px on toolbar controls below 1024; first Tab stop has visible
  focus; filter-button focus ring present (3px); zero console errors in all runs.
- `verify_a11y.py` unchanged and passing (all AA contrast pairs both themes;
  reduced-motion lands on final values).

## 8. VISUAL EVIDENCE (G7)

Harness: `frontend/scripts/capture_phase_g.py` (extends `capture_phase_f.py`).
States: catalog-default, catalog-gpu (missing-spec rows visible), row-hover,
row-focus, build-empty, detail-cpu, build-cpu, build-cpu-gpu, compare-empty,
compare-one, compare-two-cpu, compare-two-gpu, plus 320px spot-check — across
dark+light. Manifests record viewport, theme, filter state, selected ids,
per-shot DOM metrics, and console errors, and include the explicit
**PNG-inspection limitation note**.

- **After** (`docs/design/evidence/phase-g/after/`): **36 shots, 0 console
  errors, 0 overflow shots**. `compare-two-gpu` shows the table with
  kickers `["GPU","GPU"]` in both themes.
- **Before** (`docs/design/evidence/phase-g/before/`): 34 shots + **2 FAILED
  desktop-1440 entries** — these are the **baseline compare-two-gpu crash
  itself** (`requestGpuComparison is not defined`), reproduced by the capture
  flow on the unfixed baseline and recorded honestly in
  `before--manifest.json` (`known_baseline_failure`). The first before-run also
  surfaced a second trigger path: the build flow stores a CPU+GPU pair in
  sessionStorage, which the baseline reads as a loaded pair on reload and
  crashes the same way; the capture clears sessionStorage before the compare-GPU
  state so only the compare list drives it.
- Aesthetic judgment from PNGs is explicitly **not claimed** anywhere in this
  report; automation asserts structure only.

## 9. ENGINEERING VERIFICATION (G8)

| Gate | Result |
|---|---|
| Unit tests | **626/626** (621 baseline + 5 new facet/row contracts) |
| Production build | green — **122.72 kB CSS / 355.88 kB JS** (gzip 19.13/101.56) |
| Lint (oxlint) | exactly the **3 pre-existing** `set-state-in-effect` warnings; zero new |
| Interaction smoke (Phase 10) | **13/13** |
| Interaction smoke G | **11/11** (incl. GPU-first compare + kicker checks) |
| G5 copy probe | **G5-VERIFIED** |
| Typography audit | `g5_typography_probe.json` — **ISSUES: none** |
| Responsive/a11y G6 | **44/44** |
| A11y suite | PASS (contrast AA both themes; reduced-motion honored) |
| Console errors | 0 across all after-capture shots and all suites |
| Themes | dark + light captured and verified at every viewport |

## 10. DATA INTEGRITY & CONSTRAINT COMPLIANCE

- No backend/DB/API/deploy changes (`git diff 264e826..HEAD --stat -- backend/` empty).
- No new dependencies or animation/UI libraries; CSS is token-driven
  (`--spectra-*`) in both themes.
- No fabricated specs/benchmarks/imagery: rows render only API-returned values;
  missing values say "Not listed"; all visuals reuse the Phase F
  `aria-hidden` decorative SVG set.
- Behavior preserved: catalog/build/compare/chat/suitability/recommendation
  flows pass both smoke suites; hero quick-path counts now *stable* (bug fix),
  not redefined.
- `prefers-reduced-motion` preserved: all new animations gated; smoke verifies
  final-value landing.

## 11. RISKS & REMAINING LIMITATIONS

1. **Human visual review is the remaining gate.** All 70 committed PNGs
   (34+2 before, 36 after) are structural evidence; the working model cannot
   inspect them (stated above and in both manifests).
2. The baseline GPU-comparison crash also triggers via a persisted build pair
   (sessionStorage) on the *old* code; any user on the Phase F build who reloads
   with a stored CPU+GPU build loses the app until storage clears. Fixed on this
   branch; worth calling out in release notes.
3. The facet merge keeps last-known counts in-memory only (per plan: no API
   change); a hard reload refetches both counts — verified stable.
4. CPU architecture/release_date is sparsely populated in the list payload
   (712/3,501; 214/3,501) — rows degrade to identity+manufacturer honestly.
5. Known pre-existing lint warnings untouched (scope discipline).

## VERDICT

**READY_FOR_PREMIUM_VISUAL_REVIEW** — all engineering gates green (626 tests,
build, 3-warning lint, smoke 13+11, a11y, 44/44 responsive, 0 console errors,
both themes), before/after evidence committed with honest manifest records, the
Phase F GPU-comparison crash fixed and regression-covered. The only outstanding
gate is human aesthetic review of the committed PNGs, which automation cannot
perform by design.
