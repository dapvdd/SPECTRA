# SPECTRA V3 — Neural Spectrum · Page Blueprints

**Status:** DESIGN_SPEC_READY · **Phase:** Design-only · **File:** `docs/design/SPECTRA_V3_PAGE_BLUEPRINTS.md`

**Legend:** ✅ shipped surface (redesign scope) · 🚧 proposal (not a current feature — must not be built until approved) · ⚪ intentionally absent (do not create).

---

## 0. Verified current app surface (audit basis)

The current app is a **single-page React app** (`frontend/src/App.jsx`, ~2,400 lines, one monolith component) with **no router**; views are conditional sections driven by local state (`catalog` list, `detailView`, `compareList`, build config). Navigation is an anchor/nav bar to in-page sections. There is **no separate Settings page, no Overview landing, and no Recommendations page** today:

| Existing surface | Where |
|---|---|
| Catalog — hardware list with type/manufacturer filters, search, "load more" | main page section (`#catalog`) |
| Hardware detail — CPU/GPU specs, benchmarks, performance, provenance, sources | `detailView` panel |
| Comparison — CPU client-side compare + GPU backend `/comparison/gpu` | `#comparison` section |
| Suitability / recommendation display | cards + `/hardware/recommend` (API exists) |
| Build config + build chat (conversations persisted) | `#build` section |
| Hardware chat / AI sections | chat panels |
| About | `#about` footer section |

**Backend endpoints already exist** for catalog facets, detail, comparison (GPU), suitability, recommend, provenance, sources, build conversations, chat, auth/status.

---

## 1. Overview (🚧 proposal — new surface)

> **Proposal, not a current feature.** The app has no landing/overview page today; the catalog is the landing. This blueprint proposes an editorial overview ABOVE the catalog, gated behind roadmap sign-off.

**Intention:** a calm, signal-first entry that surfaces "SPECTRA is a verified hardware-intelligence instrument" without walls of copy.

**Composition (editorial, whitespace-led):**
- **Hero band** — one sentence of product voice + ambient violet glow. No stock imagery; pure type + a thin signal-trace motif (existing `spectra-signal-trace` motif reused).
- **Live system readout strip** — three compact instrumentation readouts, mono numerics: catalog size (from `GET /hardware` total count), verified-benchmark count, sources count (`GET /sources`). Each labeled, tabular numbers.
- **Jump-in tiles** — 4 editorial links into the real product: Catalog, Compare, Build, Ask. Tiles are hairline-bordered, hover = `primary-soft` glow, not purple-gradient cards.

**Redesign scope:** none (new). **Cost:** low (composes existing API readouts).

---

## 2. Hardware Catalog (✅ redesign scope)

**Current:** list + type/manufacturer filters + search + facets + load-more.

**V3 composition:**
- **Sticky command header** — search + facets accessible from `GET /hardware/facets`; segmented type control (All/CPU/GPU) as animated toggle (see motion spec).
- **Editorial grid** — asymmetric: first card is the "featured" larger tile (highest evidence score), remaining cards compact. Hairline dividers, whitespace-led; no heavy card chrome.
- **HardwareCard** — name (Jakarta Sans 600), one-line primary spec (mono), quality badge. Compact.
- **Facet rail** (progressive disclosure) — collapsible, mono counts, not a side-panel maze.
- **Skeleton & empty states** — compact, with exact text; never oversized empty zones.

**Key V3 moves:** fewer stacked cards, more editorial grid; animated filter transitions; mono readouts for counts.

---

## 3. CPU / GPU Detail (✅ redesign scope)

**Current:** `detailView` with specs, performance, benchmarks, provenance, sources, decision support, and fit modal.

**V3 composition:**
- **Detail masthead** — name (display), type/segment tags, quality badge, compact key-spec readout row (mono). Whitespace-led; no hero-card.
- **Performance section** — benchmark bars (instrument meter) with value settle animation; `unavailable` state honest (already well done in V2 — preserved).
- **Decision support** — suitability stars (existing `SuitabilityCard`), evidence-quality score breakdown (band + signals from `benchmark_quality_service`), provenance verified/uncertain/excluded chips.
- **Sources & provenance** — technical mono list with license status colors; expandable.
- **Hardware fit modal** — preserved pattern, V3 styling (drawer, see motion spec).

**Key V3 moves:** readout-row masthead; quality band as primary trust signal; no new sections beyond what data supports.

---

## 4. Comparison (✅ redesign scope)

**Current:** CPU client-side compare; GPU backend `/comparison/gpu`; comparison table + insights + decision summary + AI explanation (CPU only) + suitability comparison.

**V3 composition:**
- **Participant slots** — "A / B" selection with swap; slot letters preserved (existing pattern).
- **Decision summary** — winner callout with `primary` glow (winner) vs muted loser; "unavailable"/tie states styled as neutral, never green/red by default (honest).
- **Spec table** — the current horizontal table retained; V3 restyles: mono values, tabular figures, per-cell direction markers; sticky header.
- **Insights + evidence** — compact fact cards; benchmark evidence separated from spec evidence (existing behavior preserved).
- **AI explanation** — unchanged trigger flow; V3 surface (inline panel).

**Key V3 moves:** winner-vs-loser hierarchy via glow, not card borders; sticky comparison header; keep both CPU (client) + GPU (server) paths identical in layout to protect parity.

---

## 5. Recommendations (🚧 proposal — new surface; API exists)

> **Proposal.** A `recommend` API already exists (`GET /hardware/recommend`, ranked candidates + `filter_reason`), but the current UI shows it inline as suitability cards, not as a dedicated view.

**V3 composition (proposal):**
- **Prompt row** — workload tabs (gaming/workstation/productivity/content_creation/ai_ml) + type (CPU/GPU) + optional budget_max (currently no-op — show as "coming with price data", honest).
- **Ranked list** — each candidate: name, suitability stars, evidence band, rationale lines (already present in API payload).
- **Empty state** — shows `filter_reason` verbatim (e.g., "no candidates passed evidence threshold") instead of an empty box.
- **Budget affordance** — because `budget_max` accepts but does nothing, V3 presents it **disabled** with a tooltip "price data not available" — honest, per design rules.

**Redesign scope:** new. **API:** none needed (uses existing).

---

## 6. Builds (✅ redesign scope; ⚪ no new features)

**Current:** build config (CPU+GPU slots, use case, resolution), compatibility, build chat with persisted conversations.

**V3 composition:**
- **Slot layout** — two editorial columns (CPU / GPU) with hairline dividers and slot labels; selection opens the catalog/fit modal.
- **Compatibility checklist** — current `buildCompatibility.js` readout restyled as a compact checked/unchecked instrument list.
- **Build chat** — preserved conversation/evidence/analysis panels; V3 dark/light + mono tokens.

**Key V3 moves:** no structural feature change; restyle only. **Do not** invent part-picker or pricing features.

---

## 7. Settings (🚧 proposal — new surface)

> **Proposal.** The app has theme preference (`theme.js`) but no settings page. This proposes a minimal settings surface — not a feature-build.

**V3 composition (proposal):**
- **Appearance** — theme segmented control (System / Dark / Light) using the existing `THEME_PREFERENCES`; renders directly to the current `theme.js` state with no new persistence.
- **Data transparency** — read-only section: sources, licence statuses, "no sample/variance in quality score" note (links to `SCORING_METHODOLOGY.md` §7).
- **About / version** — currently a `#about` anchor; consolidate.

**Redesign scope:** new, minimal. **Constraint:** no new backend, no new auth surface.

---

## 8. Cross-view design decisions

- **Navigation proposal** (roadmap, not now): convert anchor nav to a slim persistent top/left rail with view switching; V3 scopes this as a **proposal** because the current single-page flow must not break.
- **Progressive disclosure** — facets, sources, provenance, and build evidence collapse by default; expanded surfaces reveal mono detail.
- **Copy discipline** — every headline is ≤ 6 words; every label is a noun phrase; no new paragraphs beyond the Overview hero's single sentence.

---

*Motion for each listed interaction is in `SPECTRA_V3_MOTION_SPEC.md`; build order and risks in `SPECTRA_V3_IMPLEMENTATION_ROADMAP.md`.*
