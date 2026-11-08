# SPECTRA V3 — Phase E: Neural Luxury Report

**Status:** READY_FOR_PREMIUM_VISUAL_REVIEW · **Branch:** `feat/spectra-v3-neural-luxury` · **Date:** 2026-11-08
**Base:** Phase D HEAD `ec532ed` (branch `feat/spectra-v3-experience-reconstruction`)

---

## 1. Design rationale

Phase D delivered structure (compact hero, command bar, honest states) but rendered
flat: hairlines carried everything, depth was absent, and the identity leaned on text
statistics. Phase E applies the **70/20/10 mix** — quiet luxury (surface elevation,
editorial spacing, restrained type) carries the base; neural glow (cyan signal
tokens, interactive focus glow, trace pulse) marks live moments; signal accents
(gold winners, cyan interconnect) stay rare.

**Key principle kept from the foundation:** every new color derives from theme
tokens via `color-mix` inside the two theme blocks. Reference anchors
(#0C0915/#151022/#241B35/#A78BFA/#C4B5FD/#67E8F9/#F5F1FC dark; #F8F7FC/#FFFFFF/
#F0EBFA/#7150C2/#087F98/#20172F light) are documented at the token definitions —
the existing palette already sat within a shade of each, so tokens were **refined,
not forked**.

## 2. Actual component changes

| Area | Change |
|---|---|
| `experience.css` | +~340 lines: elevation ladder (`--spectra-elevation-1/2/3`), signal cyan family (`--spectra-cyan*`, dark #67E8F9 / light #087F98), interactive/soft glow tokens, ambient wash tokens, hardware visualization palette |
| `App.jsx` | `HeroHardwareArt` (decorative SVG die-and-substrate composition, aria-hidden, captioned "Circuit diagram · decorative"); headline → "Know your hardware. Beyond the specs."; spec-strip state machine (pending/failed/loaded-empty/identity); `retryCardSpecs` |
| Detail masthead | Action cluster → vertical instrument stack ≥860px; readout strip value step raised |
| Build slots | Elevation on hover; empty-slot invitation surfaces refined |
| Comparison | Empty state gains ambient signal wash + stronger headline; sticky identity column kept from Phase D |
| Sort honesty | Label "Sort page" + sr-only scope description (client-side page-local, server owns the list) |

**The "Loading…" defect (E3, fixed):** the JSX rendered "Loading…" whenever spec
rows were empty, conflating three cache states — `undefined` (in flight), `null`
(failed), `{}` (loaded, empty). GPUs with no spec data and failed fetches showed
"Loading…" forever; the default CPU page showed it never (CPU rows returned `[]`
immediately). Now each state renders honestly: skeleton dots → `Unavailable` +
Retry → `No spec data`; CPU rows show class/maker identity. Verified: CPU page
12/12 identity strips, 0 "Loading…"; GPU page 12/12 loaded, 0 pending/failed.

## 3. Screenshot evidence

- `docs/design/evidence/phase-e/before/` — Phase D after-state (10 PNGs + manifest)
- `docs/design/evidence/phase-e/after/` — Phase E (10 PNGs + manifest: home/detail/
  compare × dark/light @1440; home × tablet-768/mobile-390 × both themes)
- `docs/design/evidence/interaction-smoke.json` — 13/13 interaction results

| Metric | Phase D | Phase E |
|---|---|---|
| Hero height (desktop, dark) | 549px | 549px (centerpiece is ambient background, zero height cost) |
| Hero height (tablet / mobile) | 799 / 691px | 799 / 658px |
| h1 | 64px | 64px, new headline copy |
| Spec-strip honesty | false "Loading…" | 4 honest states + retry |
| Hardware visual centerpiece | none | decorative SVG composition |
| Console errors | 0 | 0 |

**Limitation (explicit):** the working model cannot view images. All verification is
programmatic (Playwright DOM metrics, console logs, API logs, computed styles);
the PNGs are captured for **human** visual review. No visual-quality claim is made
beyond the measured acceptance criteria.

## 4. Functionality preserved

Interaction smoke **13/13**: skip-link first tab stop, search narrows + clear
restores, CPU filter (facet counts), sort-newest (real 2026-dated records first),
detail open/readout/back, two-slot comparison fill, comparison table with winner
cells, fit-modal open + ESC close, zero page errors. All Phase D features (build
config, build chat, suitability, provenance, AI analysis) untouched; zero backend
diffs; API contracts unchanged (facets 200 ×12 in every run).

## 5. Quality

- **Unit tests:** 621/621 (`node --test src/*.test.js`) — coverage not reduced
- **Build:** green (109.13 kB CSS / 347.84 kB JS; +3.3 kB CSS vs Phase D)
- **Lint:** oxlint, 3 findings — the same 3 pre-existing warnings from Phase D baseline
- **Contrast (WCAG):** all 6 pairs PASS in both themes (body 17.93:1 dark / 16.08:1
  light; muted 5.45/6.99; nav 5.49/6.20; sort select 6.96/5.81)
- **Reduced motion:** entrance animations correctly disabled (`animationName: none`)
- **Overflow:** none at 390/768/1440 in either theme
- **Motion budget:** hover 140–200ms (`--spectra-motion-fast` 160ms), reveals
  320–420ms, ambient pulse 6s opacity-only, single `will-change` (drawer panel)

## 6. Data integrity

- No benchmark scores, confidence percentages, or hardware imagery fabricated; the
  centerpiece is original decorative SVG (documented in-code as aria-hidden art).
- GPU spec path verified healthy: 12/12 HTTP 200 when the GPU filter is active.
- `?type=All` confirmed invalid server-side (422 risk); frontend correctly omits
  `type` for "All" — smoke tests query `/hardware` bare.
- Staging DB never written; dev DB is a disposable copy (gitignored).

## 7. Known limitations

1. Visual quality claims rest on measured criteria; human screenshot review is the
   remaining gate (see §3 limitation).
2. Sort remains page-local by design; server-side sort would be an unauthorized
   backend contract change.
3. The deployed-environment facets 422 remains a **deployment version mismatch**
   (documented in the Phase D report §5.1); local backend returns 200.
4. Spec-strip retry is one level deep (no exponential backoff); acceptable for a
   user-triggered action.
5. Pre-existing lint warnings (`set-state-in-effect` ×3) untouched to avoid scope creep.

## 8. Deployment considerations

No backend changes; frontend-only diff. New tokens/keys are additive CSS — no
migration concerns. The nginx cache policy from `f0e377d` (hashed assets immutable)
covers the new build hashes. The facets 422 fix remains: **deploy the current
backend image**, no frontend action required.

## 9. Git

- Branch `feat/spectra-v3-neural-luxury` from Phase D HEAD `ec532ed`
- Commits (this phase): `1f6fe62` E1 tokens → `4206837` E2 centerpiece →
  `426dfa6` E3 spec-states + sort honesty → `59349e3` E4 masthead →
  `29f4c91` E5 build/comparison → `adef0ca` E6 evidence → final report commit
- Pushed only to `feat/spectra-v3-neural-luxury`; remote SHA verified equal to
  local HEAD at push time. No merge to main, no deploy.
