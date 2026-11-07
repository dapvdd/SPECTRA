# SPECTRA V3 — Neural Spectrum · Motion Spec

**Status:** DESIGN_SPEC_READY · **Phase:** Design-only · **File:** `docs/design/SPECTRA_V3_MOTION_SPEC.md`

---

## 0. Motion philosophy

Motion is **meaning**, not decoration. Every transition communicates a state or
a spatial relationship. Durations stay fast and instrument-like (120–420ms);
easing is a single, consistent out-curve; `transform`/`opacity` only; full
`prefers-reduced-motion` fallbacks.

**Existing V2 motion tokens (preserved as the base scale):**

| Token | Value | Use |
|---|---|---|
| `--spectra-motion-instant` | 120ms | micro-feedback: press, hover, focus |
| `--spectra-motion-fast` | 160ms | small state flips, badges, chips |
| `--spectra-motion-base` | 200ms | standard transitions |
| `--spectra-motion-slow` | 320ms | panels, drawers, theme cross-fade |
| `--spectra-motion-reveal` | 420ms | entrance / settle of grouped content |
| `--spectra-motion-ease` | `cubic-bezier(0.2,0,0.1,1)` | default (V2) |
| `--spectra-motion-ease-out` | `cubic-bezier(0.16,1,0.3,1)` | entrances / settle (V2) |

**New V3 additive tokens (proposal, roadmap Phase C):**

```css
:root {
  --spectra-motion-ease-amber: cubic-bezier(0.22, 0.61, 0.36, 1); /* ambient drift */
  --spectra-motion-glow-period: 12s;  /* ambient atmosphere cycle */
  --spectra-motion-stagger: 40ms;     /* per-item stagger step */
  --spectra-motion-max-stagger: 240ms;/* cap, keeps group settle < 420ms */
}
```

**GPU-friendly rule:** only `transform` (translate/scale) and `opacity` animate.
No `width`, `height`, `top`, `left`, `box-shadow` transitions in hot paths.
`will-change` used sparingly and removed after settle.

---

## 1. Ambient animated glow

| Property | Value |
|---|---|
| Target | canvas atmosphere layer (radial violet wash) |
| Animation | `opacity 0.06 → 0.10 → 0.06`, period 12s, `ease-amber` |
| Trigger | always-on, only when `no-preference` |
| Reduced motion | static at 0.08 opacity |
| Rule | never applied to dense data regions; never to the dot-grid texture |

```css
@media (prefers-reduced-motion: no-preference) {
  .spectra-atmosphere {
    animation: spectra-ambient-glow var(--spectra-motion-glow-period)
      var(--spectra-motion-ease-amber) infinite alternate;
  }
}
@keyframes spectra-ambient-glow {
  from { opacity: 0.06; }
  to   { opacity: 0.10; }
}
```

## 2. Page transitions

> **Constraint:** current app has no router; view changes are conditional-section
> swaps. V3 page transitions are therefore scoped to a **proposal** (Phase D,
> only if/when a router lands). No transition on the current swap pattern.

| Property | Value |
|---|---|
| Entry | fade + translateY(8px)→0, 320ms `ease-out` |
| Exit | fade 160ms `ease` |
| Reduced motion | instant swap, no fade |

## 3. Staggered content entrances

| Property | Value |
|---|---|
| Trigger | list/grid first appear (catalog load, build results) |
| Stagger step | 40ms, capped at 6 items (240ms) |
| Easing | `ease-out` |
| Animate | `opacity 0→1`, `translateY(6px)→0` |
| Reduced motion | all items visible immediately |
| Rule | never on virtualized/loading-delta rerenders; only on initial settle |

New items added to an already-settled list do NOT re-run the stagger (avoid
flicker); they fade in at `motion-fast`.

## 4. Hover states

| Element | Default | Hover | Duration |
|---|---|---|---|
| Card / tile | flat, hairline | `primary-soft` glow ring (`elevation-focus`) | 160ms |
| Link / chip | text color | `primary` text + underline hairline | 120ms |
| Icon button | muted | `primary-soft` stroke + faint bg | 120ms |
| Table row | — | bg `rgba(primary,0.05)` | 120ms |

Hover never scales/translates layout; only color/opacity/shadow. Compression of
touch targets: press = `opacity 0.7` + inset hairline, 120ms.

## 5. Tabs & filters

| Property | Value |
|---|---|
| Trigger | catalog type toggle (All/CPU/GPU), workload tabs |
| Animate | an underline/segment `transform: translateX` (sliding indicator) |
| Duration | 200ms `ease` |
| Active state | `primary` text + bg `rgba(primary,0.12)` |
| Reduced motion | instant indicator jump |
| Rule | indicator is a single animating element, not per-tab fade |

## 6. Data visualization transitions

| Property | Value |
|---|---|
| Bars (benchmark/comparison) | `transform: scaleX(0→1)` with `transform-origin: left`, 420ms `ease-out` on settle (V2 pattern preserved) |
| Growth trigger | only on first mount of the chart, not on every rerender |
| Value settle | mono number counts up via JS (300ms, throttled, framerate-safe) or fades in at `motion-reveal` |
| Reduced motion | bars appear at full width instantly; numbers shown without count-up |
| Rule | data regions animate once then **static**; never looping bars/spinners over data |

## 7. Theme switching

| Property | Value |
|---|---|
| Trigger | `data-theme` flip (system/dark/light) |
| Animation | 320ms cross-fade on background/color; optional 1-stage `View Transitions API` where supported |
| Reduced motion | instant flip (current V2 behavior retained) |
| Rule | no content reflow; `color-scheme` flips first (keeps form controls/scrollers honest) |

## 8. Modal & drawer

| Property | Value |
|---|---|
| Entry | scrim `opacity 0→1` (200ms) + panel `translateY(12px)→0` (320ms `ease-out`) |
| Exit | reverse, 160ms |
| Focus | trap on open, return on close (existing behavior) |
| Reduced motion | instant open/close scrim, no panel slide |

Drawer (HardwareFitModal) uses the same contract; a side-shelf `translateX`
override is acceptable for the fit modal only.

---

## 9. Trigger & intent table (quick reference)

| Intent | Duration | Easing | Props |
|---|---|---|---|
| Hover/press | 120ms | ease | color/opacity |
| State flip | 160ms | ease | opacity/color |
| Standard | 200ms | ease | transform/opacity |
| Panel/drawer/theme | 320ms | ease-out | transform/opacity |
| Group settle/stagger | 420ms | ease-out | transform/opacity |
| Ambient glow | 12s loop | ease-amber | opacity only |

## 10. Compliance checklist

- [ ] All animated props are `transform`/`opacity` (exceptions: box-shadow on
      single hover element, audited)
- [ ] No continuous animation in dense data regions
- [ ] `prefers-reduced-motion: reduce` flatlines everything (V2 already ships
      this blanket rule — preserved)
- [ ] Stagger capped, no re-stagger on delta updates
- [ ] Focus/tab/modal transitions never obscure focus

---

*Implementation order for these motion behaviors is in
`SPECTRA_V3_IMPLEMENTATION_ROADMAP.md` (Phase C).*
