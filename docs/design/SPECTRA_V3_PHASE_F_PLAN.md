# SPECTRA Phase F — Implementation Plan (F0 output)

## Audit findings (root causes)

1. **Homepage overlap**: `HeroHardwareArt` is `position: absolute; inset: 0; z-index: -1`
   inside `.hero-content` — the die/substrate SVG renders *behind* the headline text
   (opacity 0.85). It is a background, not a centerpiece. `SignalReadout` occupies the
   second hero column with large type, competing with discovery. Composition is flat:
   hairlines only, no layered depth.
2. **Build**: `BuildComponentCard` empty state is text + dashed button, no illustration,
   no slot identity. Selected state is a text spec grid. Build Intelligence renders as
   text lists regardless of state (0/1/2 components). No workspace feel.
3. **Comparison**: empty state is one wide panel (`comparison-empty`) with a text index
   "01 — 02". Slots are not visually communicated; no empty→one→two visual progression.

**Architecture**: App.jsx (4109 lines) + App.css (legacy) → spectra.css (V1 tokens) →
experience.css (Phase D/E, governs last). Pure state modules (buildConfig.js,
buildIntelligence.js, comparison*.js) hold all logic — untouched by visual work.
Test harness: 621 unit tests (some assert App.jsx source strings in build-chat/markdown
areas only — no collision), 13 interaction smoke checks, capture_screens.py harness.

## Plan

- **F1** New `src/components/HardwareVisual.jsx` (+ section in experience.css):
  `ProcessorVisual`, `GraphicsVisual`, `HardwareSlotVisual`, wrapper `HardwareVisual`.
  Token-driven (`--spectra-vis-*`), aria-hidden decorative, both themes, original art.
- **F2** Hero: two in-flow zones (content | `HeroStage` centerpiece). SignalReadout moves
  below the hero grid as a full-width subordinate strip. No absolute art behind text.
- **F3** Build slots become hardware slots (art + status + action + data-state attr).
  Build Intelligence tiers: empty → guidance; one → component facts; both → full signals
  (existing pure logic unchanged). Keep class names used by check scripts.
- **F4** Comparison: two-slot empty workspace (A/B panels with art), one-selected identity
  panel, two-selected keeps semantic table + existing decision support. No scoring changes.
- **F5** Motion woven into F1–F4: data-state crossfades, entrance reveals, focus glow.
  transform/opacity only, reduced-motion guards.
- **F6** New capture script (build/compare states), DOM overlap + overflow + console
  checks at 1440/768/390 × dark/light, smoke 13, tests 621+, build, lint, contrast,
  reduced-motion verification.
- **F7** Report + evidence dirs + milestone commits + push (no merge, no deploy).

## Execution guardrails
- Preserve: `.build-component-empty`, `.build-component-select-button`,
  `.comparison-selection`, `.comparison-jump-link`, `.compare-button`,
  `.hardware-card-main`, `.comparison-table`, `.clear-search-icon` class names
  (smoke/capture scripts depend on them).
- No backend changes, no API contract changes, no new deps, no fabricated data.
