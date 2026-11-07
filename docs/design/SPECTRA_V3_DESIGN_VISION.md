# SPECTRA V3 — Neural Spectrum · Fluid Premium

**Design Vision**

| | |
|---|---|
| **Status** | DESIGN_SPEC_READY |
| **Phase** | Design-only — no implementation in this phase |
| **Date** | 2026-11-07 |
| **Owner** | Design Systems / Frontend (SPECTRA) |
| **Applies to** | `frontend/` (React 19 + Vite) — backend/API untouched |

---

## 1. Mission

SPECTRA V3 repositions the product from a **functional hardware-comparison
tool** into a **premium hardware-intelligence instrument** — the kind of
surface an enthusiast or engineer trusts to make a confident build decision.

The design language is **"Neural Spectrum"**: information is treated as a
signal stream over a calm, deep canvas; hierarchy is built with **whitespace,
weight, and hairlines** rather than stacked boxes; interaction is **fluid and
precise** rather than decorative or bouncy. Everything renders as
**deterministic instrumentation** — we show what the verified data says, and
nothing else.

Dark is the identity. Light is a designed counterpart, never an inversion.

## 2. Positioning statement

> SPECTRA is a focused way to inspect hardware specifications and compare
> verified performance data **without filling gaps with estimates** [existing
> product voice, preserved]. In V3 it reads like precision engineering
> instrumentation: calm, luminous, decisive — with every visual moment
> traceable to real benchmark/provenance evidence.

## 3. Design principles

1. **Evidence over decoration.** Every chart, badge, and confidence label
   maps to a verified backend signal (benchmark, provenance, licence). If a
   number can't be verified, we render an honest `unavailable` state — never a
   fabricated guess. V2's discipline is inherited and sharpened.
2. **Whitespace is the primary grid.** Editorial composition driven by
   generous whitespace and hairline separators, not card stacking. Containers
   recede; content leads.
3. **Instrument, not dashboard.** A narrow dark ladder, technical mono values,
   tabular numerals, labeled readouts. The UI can be information-dense **where
   the data demands it** and spacious **where hierarchy requires priority**.
4. **Motion is meaning.** Transitions convey state (loaded, compared,
   selected, settled) and spatial structure (you came from catalog → detail →
   comparison). Motion is fast, GPU-friendly, and fully disabled under
   `prefers-reduced-motion`.
5. **One source of truth for the language.** A single token set
   (`--spectra-*`) that both themes consume, mapped through semantic layers.
   No per-screen hard-coded hues anywhere in V3.
6. **Theme parity.** Dark and light each pass WCAG AA for all text; interaction
   states exist and are distinguishable in both.

## 4. What V3 feels like

| Sensory target | Expression |
|---|---|
| **Feel** | Calm, luminous, precise — ambient glow behind a quiet surface, never flashy |
| **Sound (metaphor)** | A soft synth pad, not a ringtone |
| **Texture** | Fine engineering paper with a faint dot grid; hairline separators; micro-glow on active elements |
| **Motion** | Fluid settling (instrument needle), not orchestral bounces |
| **Voice** | Compact, technical, confident ("Multi-core 16,347 · p90") — no filler paragraphs |
| **Density** | Data-dense where real, spacious where hierarchy needs it |

## 5. What V3 deliberately avoids

- Generic SaaS dashboard aesthetics (bulky cards, rounded shadows everywhere,
  icon-grid landing inside the app).
- Card nesting & boxy stacking as the default layout mechanism.
- Purple gradients on **every** component — Primary violet is used as a scarce,
  purposeful accent (active selection, primary CTA, focus of attention). Surface
  language is neutral violet-tinted gray.
- Unnecessary explanatory paragraphs — every sentence earns its place or is cut.
- Oversized empty sections — empty/success/unavailable states are compact and
  honest.
- Decorative charts without meaningful data — a chart must answer a comparison
  or distribution question the user asked.
- Fake benchmark scores or confidence claims — quality badges show real
  computed bands (`high/medium/low` + `no score` veto), never invented numbers.

## 6. Design language pillars

1. **Surface ladder** — a deliberate near-black (dark) / near-white (light)
   surface system. Hierarchy from hairlines + type weight, not surface-on-surface.
2. **The violet signal** — one primary hue (`#A78BFA` dark / `#7955D4` light)
   reserved for the *active decision moment*: primary action, selected state,
   focus, the comparison winner. Rarity is what makes it premium.
3. **The cyan signal** — `#67E8F9` (Signal) for *live/correctness* semantics:
   verified data, sensors, "ok", real-time state. Never decorative.
4. **Technical voice** — JetBrains Mono for every raw value, metric unit, ID,
   and provenance token, with tabular numerals so scores align vertically.
5. **Neural ambient glow** — a faint, slow-moving radial atmosphere on the
   canvas (and optional accent on the active element), at the threshold of
   visibility; respects reduced motion and never animates dense data regions.
6. **Editorial composition** — asymmetric, whitespace-led grids with a clear
   focal column per view; progressive disclosure keeps dense instrumentation
   approachable.

## 7. Strategic goals for V3 design work

1. **Truthful information architecture** — map the 7 views (Overview, Catalog,
   Detail, Comparison, Recommendations, Builds, Settings) onto what the current
   app supports, marking pure proposals explicitly (see
   `SPECTRA_V3_PAGE_BLUEPRINTS.md`).
2. **Design-system foundation** — ship the token set + core primitives so every
   future feature inherits the language without re-decision.
3. **Trust through transparency** — every benchmark/confidence surface shows
   its license & provenance status; design reinforces, never hides, data
   honesty.
4. **Protect the release candidate** — this phase introduces **no changes** to
   application code, API contracts, or the existing theme behavior. The release
   branch is not touched or merged.

## 8. Contrast & accessibility stance

- All body/muted text ≥ 4.5:1 in both themes (validated — see
  `SPECTRA_V3_DESIGN_SYSTEM.md` §Color).
- Borders/hairlines are decorative chrome; meaningful UI boundaries
  (inputs, interactive chips) get a 3:1 minimum via `BorderStrong` or the focus
  ring.
- Full keyboard operability, visible focus rings, `prefers-reduced-motion`
  support are inherited from V2's strong baseline and carried forward.

## 9. Success criteria (design-verify, before implementation)

| Criterion | Target |
|---|---|
| Contrast | 100% of text tokens ≥ 4.5:1 in both themes |
| Token purity | 0 hard-coded hues outside the token/theme blocks |
| Motion compliance | All animated properties transform/opacity; full reduced-motion fallbacks |
| Voice | No new explanatory paragraphs added; copy trimmed vs V2 |
| Truthfulness | No decorative chart accepted without a named data question |
| Parity | Catalog/Detail/Comparison/Builds workflows remain functional identical to current behavior |

---

*This document is the product-level intent. Tokens and implementation
mechanics live in `SPECTRA_V3_DESIGN_SYSTEM.md`; per-page composition in
`SPECTRA_V3_PAGE_BLUEPRINTS.md`; motion in `SPECTRA_V3_MOTION_SPEC.md`;
sequencing and risk in `SPECTRA_V3_IMPLEMENTATION_ROADMAP.md`.*
