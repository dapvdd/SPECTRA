# SPECTRA V3 — Neural Spectrum · Implementation Roadmap

**Status:** DESIGN_SPEC_READY · **Phase:** Design-only · **File:** `docs/design/SPECTRA_V3_IMPLEMENTATION_ROADMAP.md`

---

## 0. Purpose

This document bridges the V3 design language (files above) to code. It records:
(1) a verified audit of the current frontend architecture, (2) the component
inventory the design touches, (3) migration risks, (4) acceptance criteria, and
(5) a phased implementation sequence. **No code changes are authorized by this
document; it is the plan for a future phase.**

---

## 1. Frontend architecture audit (verified 2026-11-07)

### 1.1 Stack

| Layer | Confirmed |
|---|---|
| Framework | React `^19.2.8` + Vite `^8.2.2` (`@vitejs/plugin-react`) |
| Language | Plain JS (ESM), no TypeScript |
| Router | **None** — single page; views are conditional sections in one component |
| Styling | **Plain CSS, no preprocessor/library**: `index.css` (1.3 KB) + `App.css` (89.6 KB) + `spectra.css` (43.6 KB) |
| Theme | Custom `data-theme` dark/light via `theme.js` + `index.html` boot script (no-JS dark fallback) |
| Testing (FE) | `node --test src/*.test.js` — extensive pure-function tests (`*.test.js`) |
| Charting | **None** — no external chart library; charts are CSS/SVG primitives |
| Animation | CSS keyframes + transitions only (V2 pattern); no JS animation lib |
| Lint | oxlint (`.oxlintrc.json`) |
| A11y base | Strong: skip-link, `:focus-visible` ring, `aria` states, `prefers-reduced-motion` blanket rule |

### 1.2 Code organization

```
frontend/src/
  App.jsx            ~2,400 lines — single monolith component; all views, state,
                     handlers, sections in one file
  App.css            component implementation (tokens, shell, catalog, detail,
                     performance, comparison, build, chat, responsive)
  spectra.css        V2 visual system: themes, type, space, radius, motion,
                     atmosphere, typography, primitives, motifs, data motion
  index.css          global reset, focus, scrollbars, color-scheme
  *.js               pure logic modules (catalog, comparison*, detail, buildConfig,
                     buildChat, buildConversation, provenance, performance,
                     signalProfile, suitabilityDisplay, hardwareChat, appState,
                     api, apiValidation, theme, markdown) — all unit-tested
  components/        only 5 reusable JSX: BenchmarkQualityBadge, ChatView,
                     HardwareFitModal, Markdown, SuitabilityCard
  hooks/             useRecommendation.js, useSuitability.js
```

### 1.3 Confirmed findings (not recommendations)

1. **Monolith App.jsx** (~2,400 lines) bundles catalog, detail, comparison, build, chat, nav, and about. This is the dominant technical constraint: any restyle must not require rewriting view wiring.
2. **No router** — no URL→view mapping; no deep links. V3 page-transition motion is therefore deferred (see Motion spec §2).
3. **Two parallel CSS layers** — `App.css` owns components, `spectra.css` owns themes/tokens. Token aliasing already exists (`--surface-*` → `--spectra-*`), so V3 re-hue is a **token-level swap**, low-risk.
4. **V2 already ships the foundation V3 needs**: dark default, light counterpart, hairline-first surfaces, reduced-motion blanket rule, focus ring, a narrow surface ladder, and mono technical voice. V3 is an **evolution of V2**, not a rewrite.
5. **No chart library** — meets "no decorative charts" by construction; V3 charts are extensions of existing primitives.
6. **Zero design-token drift** between themes is already enforced by the spectra.css rule "no hue literals below this line except inside a theme palette block" — V3 inherits and keeps this.
7. **Test asset is the pure-function layer** (`*.test.js` + node --test). Component/CSS changes are not unit-tested; regression safety for a restyle comes from the existing function tests + manual/visual pass.
8. **Accessibility baseline is strong** (skip-link, focus ring, aria-live, reduced-motion, semantic tables with captions). V3 must not regress it.

### 1.4 Confirmed gaps / debt (recommendations follow)

| Finding | Severity | Recommendation |
|---|---|---|
| Monolith App.jsx | High (maintainability) | Defer decomposition to a later phase; V3 restyle works within current structure via section components + tokens |
| No router | Medium | Optional Phase D proposal; not required for restyle |
| Fonts: V2 declared Inter but never loaded it (comment in spectra.css) | Low | Resolve font-loading honestly in Phase A (load Plus Jakarta Sans/Inter/JetBrains Mono or drop unused) |
| Charts hand-built | Low | Keep; extend primitives (no library) |
| No Settings/Overview/Recommendations pages | — | Blueprinted as proposals (see PAGE_BLUEPRINTS) — do not build without approval |

---

## 2. Component inventory (V3 touch map)

| Component | Current home | V3 change |
|---|---|---|
| `navbar` / nav-links | App.css shell | restyle; optional rail proposal (Phase D) |
| HardwareCard | App.jsx + `.hardware-card` | editorial grid variant, quality badge, mono spec |
| Detail masthead + readout rows | detail section | readout-row masthead |
| PerformanceSection / benchmark bars | `performance-section` | value-settle retained; V3 re-hue |
| SuitabilityCard | `components/SuitabilityCard.jsx` | band-driven trust visuals |
| BenchmarkQualityBadge | `components/BenchmarkQualityBadge.jsx` | **key V3 surface** — band (high/medium/low/no score) |
| ComparisonDecisionSupport / spec table | comparison section | winner glow vs muted; sticky header |
| ComparisonInsights / evidence | comparison + provenance | compact fact cards |
| BuildConfig slots + compatibility | build section | two-column editorial slots |
| BuildChat (evidence/analysis) | components/ChatView.jsx | V3 tokens only |
| HardwareFitModal | `components/HardwareFitModal.jsx` | drawer motion spec |
| Filters / segmented toggles | catalog section | animated segment (motion §5) |
| Provenance / sources lists | provenance.js | mono technical list, license colors |

**No new component hosts are required for the redesign; only for the proposal
surfaces (Overview/Recommendations/Settings).** That keeps risk low.

---

## 3. Migration risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Token re-hue breaks a V2 test/visual | Low | Med | Tokens are aliases; run FE `node --test` + manual visual pass per phase |
| Contrast regression in light theme | Low | High | Automated contrast check script (table in DESIGN_SYSTEM) is the acceptance gate |
| Monolith edit blast radius | High | High | Restyle in CSS-token layer first (low diff), component structure last; no App.jsx rewiring in early phases |
| Font loading change (drop-or-load) causes FOUT/shift | Med | Med | Load variable fonts with `font-display: swap` + fallback stack; measure CLS |
| Motion added to dense regions (perf) | Med | Med | Enforce transform/opacity-only rule + reduced-motion; audit with DevTools |
| Proposal surfaces built before approval | — | — | **Hard gate**: Overview/Recommendations/Settings are proposals only; no code until signed off |
| Release candidate / branch safety | — | — | V3 phase changes land on `main` after RC merges; **never touch or merge the release branch** in this design phase |

---

## 4. Acceptance criteria (per phase)

1. **Token purity:** 0 hex literals outside theme blocks (grep-gated).
2. **Contrast:** every text token ≥ 4.5:1 both themes (script-gated).
3. **Behavior parity:** existing FE `node --test` suite + backend suite stay green; comparison/build/detail flows functionally identical.
4. **Reduced motion:** blanket rule present; no enabled animation on `reduce`.
5. **No decorative data:** no new chart without a named data question.
6. **Voice discipline:** copy line-count does not increase vs current sections.
7. **RC protection:** release branch unchanged; no V3 code merged to it.

---

## 5. Phased implementation sequence (for a future, approved phase)

### Phase A — Token & theming foundation (lowest risk, highest leverage)
- Introduce the V3 palettes (dark + light) into `spectra.css` theme blocks;
  re-hue existing `--spectra-*` surfaces to the violet-neutral ladder.
- Add semantic tokens: borders, hover/active, focus, success/warning/error,
  charts, glow/elevation (see DESIGN_SYSTEM §3-4).
- Resolve font loading: load Plus Jakarta Sans + Inter + JetBrains Mono
  (`font-display: swap`) or drop unused declarations — with fallback stack.
- Gate: contrast script green; FE tests green; visual regression pass.

### Phase B — Primitives & surface restyle
- Restyle HairlineCard, HardwareCard, Badge, Segment control, readout row,
  table, drawer — all via tokens + a few component classes. No App.jsx rewiring.
- Bars/metadata settle retained; no dense-region animation yet.

### Phase C — Motion system
- Land `--spectra-motion-*` additive tokens; implement ambient glow (opacity
  only, 12s, reduced-motion static), staggered entrances (capped), animated
  segments, drawer/modal contract, theme cross-fade.
- Gate: DevTools animation audit (transform/opacity only).

### Phase D — Architecture (proposal, optional)
- Evaluate decomposition of App.jsx + router; only then unlock page-transition
  motion and deep links. **This is a proposal with its own gate.**

### Phase E — Proposal surfaces (each separately gated)
- Overview (readout strip + jump tiles), Recommendations (existing API), minimal
  Settings (theme + data transparency). Each is its own proposal; none ships
  without sign-off.

---

## 6. Files created by this design phase

| File | Contents |
|---|---|
| `docs/design/SPECTRA_V3_DESIGN_VISION.md` | Product intent, principles, positioning |
| `docs/design/SPECTRA_V3_DESIGN_SYSTEM.md` | Tokens (dark/light), typography, spacing, radius, elevation, states, charts, glow, icons, a11y contract |
| `docs/design/SPECTRA_V3_PAGE_BLUEPRINTS.md` | 7 views — ✅ redesign vs 🚧 proposal mapping |
| `docs/design/SPECTRA_V3_MOTION_SPEC.md` | Durations, easing, triggers, reduced-motion, GPU-friendly rules |
| `docs/design/SPECTRA_V3_IMPLEMENTATION_ROADMAP.md` | This file: architecture audit, inventory, risks, AC, phases |

No application code, no CSS, no API contract, and no production data were
changed. The release branch is untouched and unmerged.
