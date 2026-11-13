# M2.5 Product Experience Audit — Unified Build Experience

Date: 2026-11-12 · Branch `feat/spectra-m2.5-unified-build-experience` (from `origin/main` @ `abb2548`)
Method: read-only code audit (two parallel exploration passes + direct verification of every finding cited below). Line numbers refer to the branch baseline.

## Journey audited

Catalog → Hardware Detail → Add to Build → Six-slot Build Planner → Compatibility Check → Build Intelligence → AI Chat

## Findings

### F1 (P0-adjacent, copy truth) — Legacy "CPU + GPU configuration" labels
- `frontend/src/buildConfig.js:555` — `relationshipLabel: "CPU + GPU configuration"` hardcoded for every build state.
- `frontend/src/buildIntelligence.js:515-520` — `slotLabel` ternary produces "CPU + GPU configuration" / "CPU only · GPU slot empty" / "GPU only · CPU slot empty"; `:526` `populatedSlotCount` counts only CPU+GPU.
- `frontend/src/buildIntelligence.test.js:242` and `buildConfig.test.js:183` pin the legacy strings.
- User impact: a six-slot workspace self-describes as a 2-slot feature; slot completeness shown as "of 2" (F2). Root cause: M2 added four slots without updating summary vocabulary. Fix: derive labels from all six slots. Regression risk: low (string-level; update pinned tests deliberately). Acceptance: no "CPU + GPU configuration" copy anywhere; populated-slot count reads "of 6" (Task 3/4).

### F2 (P1) — "Populated slots … of 2" in six-slot workspace
- `frontend/src/App.jsx:2197-2198` — `<dt>Populated slots</dt><dd>{overview.populatedSlotCount} of 2</dd>`.
- Fix: show six-slot completeness (selected count / 6) sourced from `buildConfig` slot map, distinct from CPU/GPU intelligence scope (Task 4). Regression risk: low.

### F3 (P0) — PSU rule overclaims power semantics (Task 1)
- `backend/app/services/compatibility_rules.py:341-360` — `rule_psu_build_wattage` computes `required = floor(total_draw * 1.3 + 0.5)` from CPU/GPU `tdp_w` sums and returns **COMPATIBLE** when `wattage >= required`; explanation: `"PSU {wattage} W covers {total_draw} W draw ({parts}) plus 30% headroom (required >= {required} W). PSU connector requirements are not evaluated…"` — matches the mission's reported example ("PSU 450 W covers 45.0 W draw …").
- `PSU_HEADROOM_FRACTION = 0.3` at `:37` with comment admitting it is "intentionally simple and documented".
- Problems: (a) calls the TDP sum a "draw"; (b) treats headroom math as a validated PSU requirement; (c) full-build aggregate can read COMPATIBLE from TDP arithmetic alone; (d) connector fields (`pcie_8pin_count`, `pcie_12vhpwr`) exist in the PSU spec (`models/psu.py:53-61`) and are loaded into rule dicts (`compatibility_service.py:132-137` via generic column copy) but never evaluated.
- Tests pinning PSU: `test_compatibility_rules.py:266-275` (connector-note absence guard), plus state assertions; `test_build_compatibility_api.py:96-99` seeds PSU 750W/Gold; `:132` asserts `psu-build-wattage` COMPATIBLE for the full fixture build. Wording edits are safe; state expectations change deliberately (Task 1, TDD).
- Acceptance: no "covers … draw" claim; TDP arithmetic only as clearly-labeled non-authoritative advisory; missing-data → UNKNOWN; no full-PSU COMPATIBLE from TDP alone; connector gaps exposed.

### F4 (P1) — Hardcoded manufacturer filters not category-aware (Task 2)
- `frontend/src/catalog.js:16-22` — `MANUFACTURER_FILTERS = ["All","Intel","AMD","NVIDIA","ATI"]` static, derived from the CPU/GPU-era DB snapshot (comment `:11-15`).
- Effect: selecting RAM/STORAGE/MOTHERBOARD/PSU still shows Intel/AMD/NVIDIA/ATI — misleading for a PSU catalog of e.g. Corsair/Seasonic.
- Backend support exists: `GET /hardware/facets` (`backend/app/main.py:388-425`) returns manufacturer facets computed with the same WHERE clauses as the catalog query — data-derived options are feasible without inventing names.
- Manufacturer filter state on type change: `App.jsx` keeps `manufacturerFilter` independent of `typeFilter` (state declared side by side; no reset effect exists) → a stale "ATI" filter silently empties the RAM list. Fix: derive options from facets, reset-or-preserve deliberately, keep counts consistent (Task 2, TDD). Regression risk: medium (touches fetch flow) — gate behind unit tests for the option-derivation and reset logic.

### F5 (P1) — Compare actions for unsupported categories (Task 2)
- `frontend/src/comparisonDecision.js:29-37` — `CPU_TABLE_SPECS` (cores/threads/clocks/tdp/socket); `comparison.js` has `GPU_TABLE_SPECS`; the decision layer assumes `cpuA/cpuB` sides (`:14`).
- `App.jsx:4463` renders the Compare action without gating on category — RAM/PSU/… cards can present a Compare action whose path is CPU/GPU-shaped.
- Fix: explicit support matrix (CPU, GPU supported; others hidden or disabled with explanation). Backend comparison endpoints are `/comparison/gpu` + `/comparison/explanation` (`main.py:946,1004`) — CPU+GPU only. Acceptance: no clickable Compare for unsupported categories (Task 2).

### F6 (P1) — Stale closure in buildDetailState restore (Task 6)
- `frontend/src/App.jsx:3186-3210` — `restoreBuildConversationForSlot(type, detail)` reads `getBuildSlotDetail(buildDetailState, otherSlot)` from the render-scope state. `loadBuildSlotDetail` (`:3236-3271`) calls it inside a `.then()` after `setBuildDetailState(complete…)` — the `buildDetailState` referenced is the closure captured at the render that created the callback, not the state just updated. Rapid slot adds (CPU then GPU before CPU detail resolves) can restore the chat conversation against the stale other-slot detail (e.g. previous CPU). 
- Fix: read via a ref mirror (`buildDetailStateRef`) updated in the same effect that owns `buildDetailState`, or compute the other slot's detail from the same request payload flow. Regression tests in `appState`/component-level test pinning restore pairing (Task 6, TDD). Quality gate: no regressions in chat restore.

### F7 (P2) — Compatibility fetch lifecycle gaps (Task 6)
- `frontend/src/App.jsx:2854-2896` — effect refetches on `buildSlotIdsKey` change with AbortController + stale guard (good), but:
  - fires immediately for the **empty build** (`{}` → server UNKNOWN, zero rules) — one wasted POST per mount; empty state could short-circuit locally;
  - on error, previous `ruleResults` are wiped to `UNKNOWN` + error string (`:2887-2892`) — acceptable honesty, but the panel should distinguish "stale results + error" vs "checked, unknown" (Task 3/6 copy);
  - no debounce: rapid slot switching aborts in-flight requests (correct), so debounce is **not** needed; keep AbortController semantics (spec allows skipping debounce when it doesn't improve behavior — documented decision).
- Acceptance: no duplicate fetches, no stale overwrite, empty build does not hit the API, error recovery retried on next change.

### F8 (P2) — Dangling aria-labelledby target (Task 6)
- `frontend/src/App.jsx:1997` — an element references an `aria-labelledby` id that is not rendered (audit finding; slot cards themselves are correct at `.build-component-card[aria-labelledby=build-slot-*]`).
- Also `App.jsx:2090` — "Change {type}" built with raw `type` → "Change STORAGE" (uppercase type constant leaking into prose). Fix: per-slot display-name map ("Change Storage"). Acceptance: zero unresolved aria references (axe/DOM check), casing humanized.

### F9 (P1) — AI Chat context is CPU/GPU-only and cannot see incompatibility (Task 5)
- `backend/app/services/build_chat_service.py:14` — `_CHAT_PROMPT`: "You are SPECTRA AI, a concise build assistant for CPU + GPU configurations."
- `backend/app/schemas/build_chat.py:144-149` — `BuildContext` (extra="forbid") carries cpu/gpu ids+names only; no ram/storage/motherboard/psu, no compatibility results.
- Missing `GEMINI_API_KEY` → `ProviderUnavailableError` (`explanation_service.py:183-194`) → 503 (`main.py:1056-1057`); frontend `ChatView.jsx:13-22` maps errors to copy + "Could not get an answer." fallback (`:107`) — graceful-ish, but the planner must keep functioning (it does; chat is isolated).
- Frontend scoping fix from M2 (`restoreBuildConversationForSlot:3190-3192` returns early for non-CPU/GPU; `addToBuild:3295-3304` only CPU/GPU change the chat token) prevents the 4 new slots from corrupting chat identity.
- Fix (scoped, honest): extend `BuildContext` with an optional, minimal, **verified** six-slot summary + compatibility digest (aggregate state, incompatible rule ids with explanations, unresolved/missing list) built server-side from DB facts — never serialize whole records; prompt updated to name incompatible combinations and forbid "ready to build" claims when INCOMPATIBLE. Stale context: chat token already resets on CPU/GPU change (M2); extend token to include compatibility-affecting changes (spec decision doc). Graceful fallback preserved: provider absence must not break planner (already true; add test). Full contract in `docs/build-planner/M2_5_AI_CONTEXT_CONTRACT.md`. Acceptance: incompatible build → chat context names it; unknown checks listed; no fabrication; auth/ownership boundaries unchanged.

### F10 (P2) — buildIntelligence redundancy + legacy gaps (Task 4)
- String inventory (buildIntelligence.js): `LISTED_TDP_NOTICE` `:74-77` renders up to 3× (signal detail `:644`, App power notice `:2238`, facts note `:2412-2416`); `TDP_CONSIDERATION` `:90-91` is a 4th phrasing; `dataGaps` hardcodes `"No measured system power data."` `:1062` (5th variant).
- Coverage figure repeated 3×: interpretation `:828` ≈ known `:888` ≈ strengths `:961`.
- Legacy claims: `COMMERCIAL_GAP = "No price, value, or compatibility data."` `:87` — false in M2.5 (compatibility data exists); `PLATFORM_GAP = "No motherboard, power supply, cooling, or case data."` `:88-89` — motherboard/PSU data now exists when selected.
- Empty-state copy `:494-502` — "Select a CPU or a GPU…" ignores the other four slots (App.jsx:2174 same).
- Fix: restructure into Build Overview / Compatibility / Performance Evidence (CPU+GPU scope explicit) / Specification Coverage / Data Limitations; dedupe power disclaimer to one authoritative line + one advisory line; drop false gap claims when data exists; progressive disclosure via `<details>` for evidence lists (Task 4). Acceptance: no false "no compatibility data"; disclaimer appears once in facts + once in considerations max; scope labeled CPU/GPU explicitly.

### F11 (P2) — Empty/loading/error states
- Catalog/detail/compat/intelligence/chat fallbacks audited (App.jsx:2170-2176 intelligence empty is legacy CPU/GPU wording; compatibility empty-state = raw UNKNOWN banner with zero rules and no "nothing to check yet" copy at 2558-guard; chat transcript empty renders nothing `:1813-1815`). Fix under Tasks 3/4: honest empty states for six-slot semantics ("No compatibility checks apply yet — add components that interact").

### F12 (info) — Theme handling is correct
- `theme.js` tri-state system/dark/light with `data-theme` + `data-theme-preference`, FOUC boot script mirrored in `index.html:34-61`. No change needed beyond Task 7 polish; staging behavior (`prefers-color-scheme` respected) already verified in M2 browser acceptance.

## Non-defects (verified, deliberately preserved)

- TDP arithmetic in the PSU rule is not *wrong* as an advisory reference — only its labeling and COMPATIBLE authority are (F3).
- Manufacturer "ATI" rows are real legacy GPU records kept distinct for provenance (catalog.js comment) — the fix is data-derived options, not data edits.
- AbortController + stale-response protection in the compatibility effect is correct; do not rewrite.
- Auth/ownership on chat routes (`require_auth`, `main.py:1052,1070`) stays untouched.

## Severity summary

| ID | Severity | Task |
|---|---|---|
| F3 | P0 | Task 1 (power semantics) |
| F1, F2 | P1 copy | Tasks 3/4 |
| F4, F5 | P1 | Task 2 |
| F9 | P1 | Task 5 |
| F6 | P1 (functional bug) | Task 6 |
| F7, F8, F10, F11 | P2 | Tasks 4/6/7 |
