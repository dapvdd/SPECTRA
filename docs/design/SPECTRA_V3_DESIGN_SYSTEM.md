# SPECTRA V3 — Neural Spectrum · Design System

**Status:** DESIGN_SPEC_READY · **Phase:** Design-only · **File:** `docs/design/SPECTRA_V3_DESIGN_SYSTEM.md`

---

## Philosophy

One token set (`--spectra-*`) consumed by **both themes** through semantic layers. Raw palette lives in theme-variable blocks only; everything else references semantic tokens. No per-screen hex, no theme drift.

Dark is the primary identity (`:root` default, no-JS fallback). Light is a deliberately composed counterpart (`:root[data-theme="light"]`), never an inversion. Loading pattern matches the current app (`index.html` boot script + `theme.js`).

---

## 1. Color Foundation — Dark theme

| Token | Value | Role | Contrast vs canvas |
|---|---|---|---|
| `--spectra-obsidian` | `#0B0A14` | page canvas | — |
| `--spectra-void` | `#080710` | deepest sink / sunken | — |
| `--spectra-canvas` | `#0F0E1A` | app shell | — |
| `--spectra-surface` | `#141120` | raised surface | — |
| `--spectra-elevated` | `#201A30` | floating / modal | — |
| `--spectra-overlay` | `#2A2440` | drawer / popover | — |
| `--spectra-inset` | `#0C0B18` | recessed well | — |
| `--spectra-text` | `#F5F3FF` | primary text | 17.9:1 |
| `--spectra-text-muted` | `#A39AB8` | secondary text | 7.4:1 |
| `--spectra-text-faint` | `#8B82A3` | tertiary / label | 5.5:1 |
| `--spectra-ink-inverse` | `#0B0A14` | ink for saturated fills | vs fills ≥6.7:1 |
| `--spectra-primary` | `#A78BFA` | active / selection / CTA | 7.2:1 |
| `--spectra-primary-soft` | `#C4B5FD` | highlight / hover edge | 10.7:1 |
| `--spectra-primary-deep` | `#7C6BD4` | pressed / deep focus | 4.2:1 |
| `--spectra-signal` | `#67E8F9` | verified / live / correct | 13.6:1 |
| `--spectra-text-plain` | `#F5F3FF` | on-signal ink | 1.0 (chip bg) |

## 2. Color Foundation — Light theme

| Token | Value | Role | Contrast vs canvas |
|---|---|---|---|
| `--spectra-obsidian` | `#F8F7FC` | page canvas | — |
| `--spectra-void` | `#F1EEF7` | deepest sink / sunken | — |
| `--spectra-canvas` | `#F8F7FC` | app shell | — |
| `--spectra-surface` | `#FFFFFF` | raised surface | — |
| `--spectra-elevated` | `#FFFFFF` | floating / modal (+shadow) | — |
| `--spectra-overlay` | `#FFFFFF` | drawer / popover | — |
| `--spectra-inset` | `#F1EEF7` | recessed well | — |
| `--spectra-text` | `#20172F` | primary text | 16.1:1 |
| `--spectra-text-muted` | `#746A85` | secondary text | 4.8:1 |
| `--spectra-text-faint` | `#5D526E` | tertiary / label | 7.0:1 |
| `--spectra-ink-inverse` | `#FFFFFF` | ink for saturated fills | vs fills ≥5.0:1 |
| `--spectra-primary` | `#7955D4` | active / selection / CTA | 4.9:1 |
| `--spectra-primary-soft` | `#B49AF2` | highlight / hover edge | 2.4:1 (non-text) |
| `--spectra-primary-deep` | `#5E3FB5` | pressed / deep focus | 6.5:1 |
| `--spectra-signal` | `#0E7490` | verified / live / correct | 5.0:1 |

**ONLY use `--spectra-Elevated`/`--spectra-Overlay` in light = white** with the V3 elevation shadows to separate modal from canvas.

## 3. Semantic layers (both themes)

| Semantic token | Dark value | Light value | Used for |
|---|---|---|---|
| `--spectra-surface-app` | canvas | canvas | page background (already in use) |
| `--spectra-surface-raised` | surface | surface | cards, tiles |
| `--spectra-surface-sunken` | void | void | wells, meter tracks |
| `--spectra-surface-inset` | inset | inset | code, readouts |
| `--spectra-border-subtle` | `#1E1B2E` | `#E6E2F0` | default separators |
| `--spectra-border-default` | `#282440` | `#D5CFE4` | card/input boundaries |
| `--spectra-border-strong` | `#352F52` | `#B9B0CD` | emphasized, 3:1 boundaries |
| `--spectra-focus-ring` | `3px solid #C4B5FD` | `3px solid #5E3FB5` | keyboard focus (offset 3px) |
| `--spectra-text-primary` | text | text | primary copy (already in use) |
| `--spectra-text-secondary` | text-muted | text-muted | secondary copy (already in use) |
| `--spectra-text-muted` | text-faint | text-faint | tertiary/labels |
| `--spectra-accent` | primary | primary | active, primary CTA |
| `--spectra-accent-soft` | primary-soft | primary-soft | hover edges, chip accents |
| `--spectra-accent-contrast` | `#0B0A14` | `#FFFFFF` | text on accent fill |
| `--spectra-success` | `#34D399` | `#15803D` | verified / good |
| `--spectra-warning` | `#FBBF24` | `#B45309` | caution / uncertainty |
| `--spectra-error` | `#F87171` | `#C13515` | errors / veto |
| `--spectra-info` | `#7DD3FC` | `#0369A1` | neutral info |

## 4. Status & state tokens

| State | Dark | Light | Notes |
|---|---|---|---|
| hover (chromeless) | `var(--spectra-primary-soft)` text, bg `rgba(167,139,250,0.08)` | `var(--spectra-primary)` text, bg `rgba(121,85,212,0.06)` | text-identifiable, not color-only |
| active/pressed | `var(--spectra-primary)` + inset hairline | `var(--spectra-primary-deep)` + inset hairline | never scale/translate layout |
| disabled | text `#5A5268` (≤40% opacity allowed), bg transparent | text `#9C94AC`, bg transparent | `disabled` semantics + cursor not-allowed |
| selected | `bg rgba(167,139,250,0.14)`, hairline-strong | `bg rgba(121,85,212,0.10)`, hairline-strong | violet signal reserved here |
| focus | `outline: var(--spectra-focus-ring)`, offset 3px | same ring, deep violet | every interactive node |

## 5. Typography

| Role | Family | Weight | Sizes |
|---|---|---|---|
| Display / H1 | Plus Jakarta Sans | 700 | clamp(2.75rem, 6.4vw, 5.5rem), tracking -0.035em |
| H2 | Plus Jakarta Sans | 700 | clamp(1.55rem, 2.6vw, 2.05rem), tracking -0.02em |
| H3 | Plus Jakarta Sans | 650 | 1.35rem, tracking -0.02em |
| Section label (eyebrow) | Plus Jakarta Sans | 600 | 0.6875rem, uppercase, tracking 0.1em |
| Body | Inter | 400/500 | 1rem / 0.875rem, line-height 1.55 |
| Technical value | JetBrains Mono | 400/600 | 0.8125rem–1rem |
| Tabular numerals | JetBrains Mono `font-variant-numeric: tabular-nums` | — | all numeric readouts |

**Responsive:** existing clamp scale preserved. Line-height 1.55 body, 1.15 headings. Truncation: single-line with `ellipsis` + `title` attr; never 2-line orphan ellipsis on cards. Numeric columns use tabular figures so scores align vertically.

## 6. Spacing

Preserve the V2 scale: 0.25 / 0.375 / 0.5 / 0.75 / 1 / 1.25 / 1.5 / 2 / 3 / 4 / 5 / 7rem. Section rhythm: 5rem desktop / 3rem mobile. `--shell-gutter: 4rem` retained; `--shell-width: 1180px` → proposal `1240px` (roadmap).

## 7. Radius & elevation

| Token | Value | Role |
|---|---|---|
| `--spectra-radius-sm/md/lg/xl/pill` | 4 / 6 / 8 / 10 / 999px | preserved (instrument-like, never pillowy) |
| `--spectra-elevation-card` | dark: `0 1px 0 rgba(170,180,194,.03)`; light: `0 1px 2px rgba(16,32,48,.05)` | flat objects |
| `--spectra-elevation-float` | dark: `0 8px 24px rgba(0,0,0,.45)`; light: `0 8px 20px rgba(31,23,48,.12)` | hover/raised |
| `--spectra-elevation-focus` | dark: `0 0 0 1px, 0 4px 24px rgba(167,139,250,.28)`; light: `0 0 0 1px, 0 4px 18px rgba(121,85,212,.22)` | ambient glow on active element |

## 8. Charts & data visualization

V3 uses **no external chart library** — charts are hand-built SVG/CSS to match the instrument aesthetic (current app has zero chart deps; verified).

| Chart | Palette | Rule |
|---|---|---|
| Benchmark bars | `success`/`muted` fill vs `surface-inset` track | bar grows to real value via `transform: scaleX` |
| Comparison distributions | primary (winner) vs surface hairline (loser) | only meaningful deltas highlighted |
| Facet counts | text / primary-soft | numeric only, no pie unless distribution is a top-tier question |
| Provenance (verified/uncertain/excluded) | success / warning / error | exact status colors, no invention |

**Glow rules:** charts may use a faint `primary` glow only on the active/settled element; never animate data bars continuously; bars animate width once on settle, then static.

## 9. Glow & atmosphere

- Canvas atmosphere: a radial `rgba(121,85,212,0.10)` wash at 84% -8% (dark) / `rgba(121,85,212,0.05)` (light) + faint dot grid. Inherited from V2's atmosphere block, re-hued to violet.
- Ambient glow animation: a slow 12s drift on the atmosphere layer, `opacity 0.06–0.10`, **only** under `prefers-reduced-motion: no-preference`. Never glows dense data regions.

## 10. Icons

- Migrate to a single line-icon set with consistent 1.5px stroke (proposal: Phosphor, `@phosphor-icons/react`) OR keep current inline SVGs — decision gated to roadmap Phase A. Rule: one stroke weight per hierarchy; decorative icons `aria-hidden`; icon controls get accessible labels.
- No emoji as structural icons (existing rule, carried forward).

## 11. Accessibility contract

- Every text token ≥ 4.5:1 in both themes (validated, see tables above).
- Every interactive node has `:focus-visible` ring (inherited from V2's index.css). Modal/drawer focus-trap + Escape + `aria-modal` retained.
- `prefers-reduced-motion`: all animations flatline (V2 already does this — carried).
- Color is never the only indicator: states pair color with text/icon/glyph.
- Touch targets ≥ 44×44px (desktop ≥ 32px where space-constrained).

---

*Component inventory and hierarchy live in `SPECTRA_V3_IMPLEMENTATION_ROADMAP.md` §Inventory; page layout in `SPECTRA_V3_PAGE_BLUEPRINTS.md`; motion timing in `SPECTRA_V3_MOTION_SPEC.md`.*
