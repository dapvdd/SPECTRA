# SPECTRA V3 — Phase F: Hardware Experience Report

**Status:** READY_FOR_PREMIUM_VISUAL_REVIEW · **Branch:** `feat/spectra-v3-hardware-experience` · **Date:** 2026-11-08
**Base:** Phase E HEAD `d36a14a` (branch `feat/spectra-v3-neural-luxury`)

---

## 1. IMPLEMENTATION

Phase F is a structural UI/UX reconstruction of the three core surfaces, built on a
new reusable hardware visualization system. No backend files were touched
(`git diff d36a14a..HEAD --stat -- backend/` is empty); no API contracts changed;
no new dependencies; no 3D libraries.

### Components added

| Component | File | Role |
|---|---|---|
| `ProcessorVisual` | `frontend/src/components/HardwareVisual.jsx` | Original stylized CPU package SVG: pin matrix, substrate, die window with die grid, capacitors, keying notch |
| `GraphicsVisual` | same | Original stylized GPU SVG: shroud, die + memory cluster, power connector, heatsink fins, bracket + display ports |
| `HardwareVisual` | same | Decorative wrapper (`aria-hidden`), optional honest caption, size variants |
| `HardwareSlotVisual` | same | Slot-sized rendering used inside build slots, comparison slots, and Build Intelligence empty state |
| `HeroStage` | `frontend/src/App.jsx` (replaces `HeroHardwareArt`) | Homepage centerpiece: substrate board + CPU package + graphics module + illuminated interconnect, in-flow |
| `capture_phase_f.py` | `frontend/scripts/` | Evidence harness: 7 states × 2 themes × 3 viewports with per-shot DOM metrics |

### Components modified

| Component | Change |
|---|---|
| Hero (App.jsx) | Two in-flow zones: content column + `HeroStage` column. `SignalReadout` moved out of the hero grid into a full-width subordinate band below it. New `hero-lede` supporting copy. |
| `BuildComponentCard` | Rebuilt as a hardware slot: `data-state` machine (`empty/loading/error/ready`), slot head (class + live status dot), `HardwareSlotVisual` identity art, state-honest content |
| `BuildIntelligenceSection` | Empty state gains a quiet visual anchor + concise guidance; 1-component and 2-component fact presentation preserved (pure logic untouched) |
| Comparison empty state | Rebuilt as an explicit two-slot workspace (A/B panels with art, status, actions, shared note) |
| `experience.css` | +~600 lines: Phase F tokens (`--spectra-vis-die-a/b`, `--spectra-vis-well`, `--spectra-vis-body-deep`, `--spectra-vis-shadow`), F1–F5 sections |

All new colors derive from theme tokens via `color-mix` inside the two theme blocks —
the Phase E token discipline is preserved. Violet remains primary; cyan stays a rare
signal accent (status dots, focus rings, interconnect traces); no new hues.

## 2. VISUAL TRANSFORMATION

| Problem (F0 audit root cause) | Fix |
|---|---|
| **Homepage overlap** — `HeroHardwareArt` was `position:absolute; inset:0; z-index:-1` inside `.hero-content`, rendering *behind* the headline at opacity 0.85 | Deleted. `HeroStage` renders in-flow in its own grid column; the h1 and the scene are geometrically separated (`h1R=674 < stageL=796` at 1440px) |
| **Decorative chip lacked impact** | Full scene with layered depth: ambient halo → substrate → packages with die gradients → signal traces → drop-shadow elevation; one-time settle entrance |
| **Catalog statistics competed with content** | `SignalReadout` is now a subordinate band *below* the hero (hairline-separated, smaller type scale); real totals and manufacturer distribution kept, no duplication |
| **Build slots = two static form cards** | Slots are workspace surfaces: class + live status dot (cyan = selected), identity illustration, `data-state`-driven crossfade, Browse/Change/Clear actions |
| **Build Intelligence mostly explanatory text** | Empty state: visual anchor + one concise line. One component: identity + facts. Two: full verified signal set. Boundary statements kept verbatim |
| **Comparison empty state = one text panel** | Two explicit A/B slots with index, status, art, per-slot browse action, and one shared note |
| **No empty→populated transition** | Comparison: `comparison-empty` (2 slots) → instruction + selection badge (1) → semantic table + winner cells (2), with a one-time reveal on `comparison-content` |

## 3. SCREENSHOT EVIDENCE

All PNGs are committed for human visual review (the working model cannot view
images; every claim below is backed by the per-shot DOM metrics in
`docs/design/evidence/phase-f/after/after--manifest.json`).

**Before (18 + 10 shots):** `docs/design/evidence/phase-f/before/` — Phase E after-state
(home/detail/compare × themes × viewports, 0 console errors).

**After (18 shots, 0 console errors):** `docs/design/evidence/phase-f/after/`
(home × 2 themes × 3 viewports; build-empty / build-cpu / build-cpu-gpu /
compare-empty / compare-one / compare-two × 2 themes @1440).

Measured per-shot (all 18): `horizontalOverflow=false`, `h1StageOverlap=false`,
honest build states, comparison slots 01/02 present when empty, table + 2 winner
cells when two selected. Real catalog records used: CPU `AMD Athlon Gold 7220C`,
GPU `i752 Graphics`; comparison pair `AMD Athlon Gold 7220C` vs `AMD Athlon Silver 7120C`.

## 4. FUNCTIONALITY

- Interaction smoke **13/13** (`docs/design/evidence/interaction-smoke.json`): skip-link
  first tab stop, search narrow/clear, CPU filter facets, sort-newest, detail
  open/readout/back, two-slot comparison, comparison table with winner cells,
  fit-modal open/ESC, zero page errors.
- Build flow verified against live API: detail → Add to Build → slot `ready` with 7
  spec rows + Change/Clear; Build Intelligence headline `CPU AMD Athlon Gold 7220C`,
  facts (2 of 5 signals, 0 of 2 benchmark metrics, 1 of 2 slots).
- Comparison progression verified: empty → one (instruction + badge) → two (table,
  2 winner cells, A/B headers).
- Search, filters, sort, detail, fit modal, build chat, suitability, provenance: no
  regressions (smoke + 621 unit tests).

## 5. QUALITY

- **Unit tests:** 621/621 (`node --test src/*.test.js`).
- **Build:** green — 119.11 kB CSS / 355.10 kB JS (+5.6 kB CSS vs Phase E, from
  ~600 new lines of F1–F5 CSS).
- **Lint:** oxlint — the same 3 pre-existing `set-state-in-effect` warnings; zero new.
- **Contrast (WCAG):** all 6 pairs PASS in both themes (body 17.93:1 dark / 16.08:1
  light; muted 5.45/6.99; nav 5.49/6.20; eyebrow 7.37/5.45; sort 6.96/5.81).
- **Reduced motion:** entrance animations disabled (`animationName: none`); every
  Phase F animation (die settle, stage entrance, slot crossfade, comparison reveal,
  trace pulse, press feedback) sits inside `@media (prefers-reduced-motion: no-preference)`
  and animates only opacity/transform.
- **Overflow:** none at 1440/768/390 in either theme; no h1/scene overlap anywhere.
- **Console errors:** 0 across all 18 evidence captures and both interaction runs.

## 6. DATA INTEGRITY

- No benchmark scores, compatibility verdicts, or physical product imagery fabricated.
  All visuals are original abstract SVG, `aria-hidden`, captioned "decorative".
- Build Intelligence boundary statements preserved verbatim; no claims of
  motherboard compatibility, measured power, thermals, FPS, or balance were added.
- Comparison winner indicators come exclusively from the existing
  `comparisonDecision.js` logic — no scoring changes.
- Slot statuses ("Empty slot" / "Loading details" / "Details unavailable" /
  "Selected") reflect the real request state machine.

## 7. RISKS & REMAINING LIMITATIONS

1. **Visual quality claims rest on measured criteria**; human review of the 28
   committed PNGs is the remaining gate (A3 model limitation).
2. **Environment fix applied (dev only):** the disposable dev DB
   (`data/spectra.db`, gitignored) was missing the `build_conversations.owner_id`
   column — a **pre-existing** drift that broke build conversations with a 500 and
   surfaced as CORS-looking console errors during capture. The repo's own migration
   runner was applied (v1–v2, now `verified`); backup at
   `data/spectra.db.pre_phasef_bak`. Production DB untouched; deployment still
   needs the current backend image (documented since Phase D).
3. The comparison "one selected" state intentionally reuses the existing
   `comparison-selection` badge + instruction (Phase D pattern) rather than
   rendering a partial table — the second slot remains visually available.
4. Mobile (390px) hero height is 860px: the scene stacks below content at a compact
   17rem, but the page remains a scrolling document by design (no viewport-height
   claims, per the Phase D compact-hero rule).
5. Pre-existing lint warnings (`set-state-in-effect` ×3) untouched to avoid scope creep.

## 8. GIT

- Branch `feat/spectra-v3-hardware-experience` from Phase E HEAD `d36a14a`.
- Milestone commits: `8378eb0` F1+F2 (visual system + hero) → `8b181ba` F3 (build
  slots) → `7996816` F4 (comparison workspace) → `bda1859` F5 (motion) →
  `cbcab4a` F6 (evidence + gates) → F7 report (this commit).
- Pushed only to `origin/feat/spectra-v3-hardware-experience`; local and remote
  SHA verified equal after push. No merge to main, no deploy, no force-push.

## 9. DEPLOYMENT CONSIDERATIONS

- Frontend-only diff (plus dev-tooling scripts and docs); new tokens/keys are
  additive CSS — no migration concerns for the shipped bundle.
- The nginx hashed-asset cache policy already covers the new build hashes.
- Backend: nothing to deploy from this phase; the standing deployment item remains
  shipping the current backend image so `owner_id` (v2 auth schema) and the facets
  fix reach staging together.
