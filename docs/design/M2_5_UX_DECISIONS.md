# M2.5 UX Decisions — Unified Build Experience

Branch `feat/spectra-m2.5-unified-build-experience` · 2026-11-13
Source audit: `M2_5_PRODUCT_AUDIT.md` (F1–F12). This document records what was
decided, why, and what was deliberately **not** done.

## D1 · Six-slot vocabulary everywhere (F1, F2 — Tasks 3/4)

- `getBuildSummary` derives `selectedCount` / `totalSlotCount` (of **6**) and a
  slot-derived `relationshipLabel`: "Empty six-slot build" →
  `"CPU + GPU + RAM build"` → "Complete six-component build".
- **Deliberate exception:** `isComplete` keeps its CPU+GPU meaning. It gates
  chat-context readiness (M2 invariant from commit `196ca75`); the six-slot
  completeness story is told by `selectedCount`/`totalSlotCount`, never by
  `isComplete`. Mixing the two would re-couple chat identity to unrelated slots.
- `getBuildSlotDisplayName` humanizes raw constants (`STORAGE` → "Storage",
  `MOTHERBOARD` → "Motherboard") in prose and headings; unknown types fall back
  to the raw value so nothing renders as "undefined".

## D2 · Data-derived manufacturer filters (F4 — Task 2)

- `deriveManufacturerOptions(facetManufacturers)` — options come from
  `GET /hardware/facets`, which counts with the same WHERE clauses as the
  catalog query. **"All" always leads; no vendor name is ever invented.** The
  static CPU/GPU-era list (`["All","Intel","AMD","NVIDIA","ATI"]`) is deleted.
- `getNextManufacturerFilter(current, options)` — a selection that no longer
  exists in the new category's vendor set resets to "All" instead of silently
  yielding an empty catalog. The reset re-issues the narrowed query (fetch
  effects depend on `manufacturerFilter`).
- Facets **self-exclude their own dimension** backend-side, so the option list
  stays complete while a vendor is selected.

## D3 · Compare gating is honest (F5 — Task 2)

- `isComparisonSupported(type)` — CPU/GPU only, explicit support matrix in
  `comparisonDecision.js`. Unsupported categories render **no** Compare action
  (hidden, not disabled) — backend endpoints exist only for CPU and GPU, so any
  other Compare affordance would be a dead end dressed as a feature.

## D4 · One authoritative disclaimer, no false gap claims (F10 — Task 4)

- `LISTED_TDP_NOTICE` is the single TDP disclaimer; `TDP_CONSIDERATION` (a 4th
  phrasing) is gone. The facts panel note and the Intelligence notice share one
  source of truth instead of three divergent renderings.
- Coverage figure is single-sourced (`coverageValue`); `dataGaps` no longer
  hardcodes a fifth measured-power variant.
- `COMMERCIAL_GAP = "No verified price or value data."` — compatibility data
  **exists** (seven M2 rules run on the build), so the old
  "No price, value, or compatibility data." was a false claim and is dead.
- `platformGapLabel(platformSlots)` — the platform gap names only what is
  actually absent: motherboard/PSU entries drop out when those slots are
  selected ("No cooling or case data."); cooling and case are always listed —
  they are never recorded in this milestone.

## D5 · Context-aware AI chat that cannot ignore INCOMPATIBLE (F9 — Task 5)

- Six-component compatibility digest (bounded, pass-through) rides to the model;
  full contract in `M2_5_AI_CONTEXT_CONTRACT.md`.
- Prompt rule 14: when the aggregate or any rule reads INCOMPATIBLE, the
  assistant must name the failing checks and is forbidden from "ready to
  use"/"ready to build"; absent/null digest → "a compatibility check has not
  been supplied", never assumed-green.
- Chat unlock stays CPU+GPU (`buildChatChecklist` copy states this explicitly)
  — a six-slot gate would block chat on slots the assistant cannot reason
  about yet.

## D6 · Fetch and restore hygiene (F6, F7, F8 — Task 6)

- **Stale-closure fix:** `buildDetailStateRef` mirrors `buildDetailState`;
  `restoreBuildConversationForSlot` resolves the pair through
  `resolveBuildChatRestore` on the live ref. A GPU completing after the CPU no
  longer pairs against the render-scope snapshot from when the CPU request
  started.
- **Empty build never POSTs:** `hasSelectedBuildComponent` (any usable
  positive-integer slot id) short-circuits the compatibility fetch. The empty
  state is a **derived** `EMPTY_BUILD_COMPATIBILITY` (chip "Compatibility
  unknown", zero rule rows) — one wasted POST per mount gone, and stale rules
  can never display after slots change. Error paths clear `ruleResults` so a
  transport failure never leaves a green panel behind.
- **Debounce deliberately not added:** rapid slot switching already aborts
  in-flight requests via AbortController; a debounce would add latency without
  reducing requests. Recorded decision, not an omission.
- Dangling `aria-labelledby` resolved (`id="build-slot-<type>"` on the slot
  heading); "Change STORAGE" casing humanized.

## D7 · One vertical reading order (Task 7)

The M2 two-column workspace (configuration left, analysis right; context left,
conversation right) was flattened into one top-to-bottom sequence:

**Overview (`.build-head`) → Compatibility (`.build-compatibility`) →
Configuration (`.build-configuration`: summary strip + component cards +
context) → Detail (`.build-facts`) → Intelligence (`.build-column-intelligence`)
→ Assistant (`.build-conversation)`**

Why:

- The compatibility verdict is the build's most safety-relevant fact; it now
  precedes the configuration detail that feeds it.
- DOM order = reading order = keyboard/screen-reader order, with no grid
  column-hopping.
- Horizontal interest moves inside the sections (summary strip, component-card
  grid, facts grid) instead of a page-level split — the sequence is never
  interrupted on wide screens, and the `@media (max-width:1023px)` collapse
  rules die with the grids they patched.
- `.build-workspace` / `.build-lower` / `.build-column-configuration` are
  deleted from JSX and CSS (dead rules removed); `.build-conversation
  { min-width: 0 }` survives (it is load-bearing, not grid wiring). Guard
  tests lock both the order and the absence of the dissolved wrappers
  (`buildHardening.test.js`).
- The Intelligence section keeps its 2px accent left border as its identity;
  the wrapper owns the section rule + top gap, and the panel drops its own top
  padding so vertical rhythm matches the other sections.
- Spacing uses existing `--spectra-space-*` tokens only (`2xl` section gap, `xl`
  separator padding). **No new identity, no glow, no new colors.**

## D8 · What was deliberately not changed

- Theme handling (F12): tri-state system/dark/light is correct; untouched.
- "ATI" catalog rows: real legacy GPU records — the fix is data-derived filter
  options, not data edits.
- AbortController semantics in the compatibility effect: correct; preserved.
- Auth/ownership on chat routes: untouched.
- Cooling and case slots: still out of scope; the platform gap copy says so.
