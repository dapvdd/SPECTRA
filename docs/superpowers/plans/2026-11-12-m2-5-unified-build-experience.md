# M2.5 Unified Build Experience — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native inline execution — mission directive is autonomous execution). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the six independent Build Planner slots into one coherent, trustworthy PC build experience (power-claim correctness first, then catalog filtering, unified workspace copy, intelligence restructuring, AI context, hardening, polish).

**Architecture:** Backend rule semantics change in `compatibility_rules.py` (PSU rule becomes two-tier: documented hard constraint → INCOMPATIBLE; TDP-headroom adequacy → UNKNOWN with labeled advisory). Frontend changes are pure-function-first (`buildConfig.js`, `buildIntelligence.js`, `catalog.js`) with App.jsx consuming them; chat context extends the existing `BuildContext` schema additively. No schema migrations; no new dependencies.

**Tech Stack:** FastAPI + SQLAlchemy + pytest (backend); React + Vite + node:test frontend tests.

**Spec:** mission brief (M2.5 sections 0–15) + `docs/design/M2_5_PRODUCT_AUDIT.md` (findings F1–F12 with file:line evidence; each task below cites its findings).

## Global Constraints

- Do NOT merge to main, deploy, migrate prod, touch existing M2 staging containers/DB/images, delete worktrees, force-push.
- Existing M2 staging (`:8095`) must remain running and unmodified for comparison.
- No new runtime dependencies without demonstrated need.
- Never fabricate benchmarks/prices/measured power; never claim pixel inspection of PNGs.
- RULES_VERSION bumps `M2-RULES-v1` → `M2.5-RULES-v1` (semantics change must be visible to API consumers).
- Backend CI-parity: `python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking`
- Frontend: `npm test -- --run` + `npm run build` in `frontend/`.
- Every behavioral change lands TDD: failing test first, minimal implementation, full suite green, commit.

## Review Focus

1. **TDP is not draw** — any new copy/tests must never equate TDP sums with measured power; pinned by Task 1 wording tests.
2. **Empty build → no network call** — empty slot map must not POST; pinned by Task 3 lifecycle test.
3. **Incompatible build must not reach chat as neutral context** — compatibility digest carries INCOMPATIBLE + unresolved; pinned by Task 5 tests.
4. **Manufacturer filter semantics on type switch** — stale selection must reset; pinned by Task 2 test.
5. **Chat token still ignores RAM/Storage/Motherboard/PSU for conversation identity** (M2 invariant, commit 196ca75) — pinned by Task 5 regression test.

---

### Task 1: PSU power-semantics correction (P0, audit F3)

**Files:**
- Modify: `backend/app/services/compatibility_rules.py` (rule_psu_build_wattage, PSU_HEADROOM_FRACTION area)
- Modify: `backend/app/services/compatibility_model.py` (RULES_VERSION bump)
- Test: `backend/app/services/test_compatibility_rules.py` (TestPsuBuildWattage)
- Test: `backend/app/test_build_compatibility_api.py` (full-build state expectations)

**Interfaces:**
- Produces: `rule_psu_build_wattage(psu, build, *, ids)` — same signature. New states: wattage >= TDP-derived reference → **UNKNOWN** (advisory); wattage < TDP-derived reference → **INCOMPATIBLE** (hard headroom-floor constraint); missing wattage/TDP → UNKNOWN; no CPU/GPU → NOT_APPLICABLE. New module constant `PSU_TDP_REFERENCE_FRACTION = 0.3` replacing `PSU_HEADROOM_FRACTION` semantics (kept number, renamed role). Explanations must: never use the bare word "draw"; label the figure "listed TDP total"; label the headroom math "non-authoritative estimate"; and name connector fields as missing information.

- [ ] **Step 1: Rewrite failing tests** in TestPsuBuildWattage (see M2_5_POWER_SEMANTICS.md for exact semantics): sufficient-TDP case → UNKNOWN with "non-authoritative" in explanation and no "covers"/"draw" claim; grossly-insufficient case (450W vs 488W+ required) → INCOMPATIBLE; missing wattage → UNKNOWN; missing TDP → UNKNOWN; connector-note guard retained.
- [ ] **Step 2: Run** `python -m pytest backend/app/services/test_compatibility_rules.py -q` → expected FAIL (COMPATIBLE ≠ UNKNOWN).
- [ ] **Step 3: Implement** two-tier rule + explanation strings + RULES_VERSION bump.
- [ ] **Step 4: Run rules tests → PASS.** Then fix API-level expectations in `test_build_compatibility_api.py` (full build aggregate UNKNOWN remains; `psu-build-wattage` state expectation changes to UNKNOWN; add TDP-reference INCOMPATIBLE API case) → run file → PASS.
- [ ] **Step 5: Full backend CI-parity suite → PASS** (expect wording-pinned failures only in M2 files; fix deliberately).
- [ ] **Step 6: Commit** `feat(planner): PSU rule honest power semantics (M2.5 Task 1)`.

### Task 2: Category-aware catalog filtering (P1, audit F4+F5)

**Files:**
- Modify: `frontend/src/catalog.js` (manufacturer option derivation), `frontend/src/App.jsx` (facets fetch + filter reset + Compare gating)
- Test: `frontend/src/catalog.test.js` (option derivation), `frontend/src/comparisonDecision.test.js` (support matrix)

**Interfaces:**
- Produces: `deriveManufacturerOptions(facetsManufacturers, typeFilter)` → ordered `["All", ...names]` from facet data only (never invented); `isComparisonSupported(type)` → true only for CPU/GPU; App.jsx fetches `/hardware/facets?type=` when typeFilter changes, replaces static MANUFACTURER_FILTERS render, resets `manufacturerFilter` to "All" when current selection is not in the new option set, and hides Compare actions for unsupported categories.
- [ ] Step 1: failing tests (options-from-facets; reset-on-type-change; unsupported-compare hidden).
- [ ] Step 2: verify RED. Step 3: implement. Step 4: verify GREEN + full frontend suite. Step 5: commit `feat(catalog): category-aware manufacturer filters + honest Compare support (M2.5 Task 2)`.

### Task 3: Unified six-slot build workspace (P1, audit F1+F2)

**Files:**
- Modify: `frontend/src/buildConfig.js` (six-slot summary + relationshipLabel), `frontend/src/App.jsx` (workspace headings, "Change Storage" casing F8-adjacent)
- Test: `frontend/src/buildConfig.test.js`

**Interfaces:**
- Produces: `getBuildSummaryLabel(config)` → e.g. "4 of 6 components selected" / "Six-component configuration"; `relationshipLabel` derived from populated slots ("CPU + GPU configuration" removed); populated-slot completeness "of 6".
- [ ] failing tests → RED → implement → GREEN → full suite → commit `feat(planner): unified six-slot build summary + workspace copy (M2.5 Task 3)`.

### Task 4: Build Intelligence restructuring (P1, audit F10+F2)

**Files:**
- Modify: `frontend/src/buildIntelligence.js`, `frontend/src/App.jsx` (panel sections, progressive disclosure)
- Test: `frontend/src/buildIntelligence.test.js`

**Interfaces:**
- Produces: explicit CPU/GPU performance scope label; six-slot completeness separate from CPU/GPU intelligence scope; `COMMERCIAL_GAP` corrected (compatibility data exists — drop the false clause); `PLATFORM_GAP` computed from selected slots instead of blanket claim; power disclaimer deduplicated (one LISTED_TDP_NOTICE in facts note; considerations reference it once); benchmark-coverage message single-source.
- [ ] failing tests → RED → implement → GREEN → full suite → commit `feat(planner): honest, deduplicated Build Intelligence panels (M2.5 Task 4)`.

### Task 5: Context-aware AI assistant (P1, audit F9)

**Files:**
- Modify: `backend/app/schemas/build_chat.py` (optional compatibility digest + six-slot summary fields), `backend/app/services/build_chat_service.py` (prompt + context assembly), `frontend/src/buildChat.js` (send digest), `frontend/src/App.jsx` (wire digest)
- Test: `backend/app/test_build_chat_context.py` (new), `backend/app/test_build_chat_evidence.py` (regression), `frontend/src/buildChat.test.js`

**Interfaces:**
- Produces: `BuildContext.compatibility` (optional): `{aggregate_state, incompatible_rules: [{rule_id, explanation}], unresolved: [str]}` — built server-side only from stored facts; prompt names incompatibilities and forbids "ready to build" claims when INCOMPATIBLE; provider-absence fallback unchanged; chat token semantics for CPU/GPU unchanged (196ca75 invariant) with digest freshness tied to the same token.
- [ ] failing schema/service tests → RED → implement → GREEN → full suites → commit `feat(chat): verified six-component compatibility context for build chat (M2.5 Task 5)`.

### Task 6: State, accessibility & microcopy hardening (P2, audit F6+F7+F8)

**Files:**
- Modify: `frontend/src/App.jsx` (ref-mirror fix, compat fetch empty short-circuit, aria fix, casing map), `frontend/src/buildSlots` state helpers as needed
- Test: `frontend/src/appState.test.js` or new focused test file

**Interfaces:**
- Produces: `buildDetailStateRef` mirror read by `restoreBuildConversationForSlot` (stale-closure fix F6); empty-build compat fetch short-circuit (F7); dangling `aria-labelledby` resolved (F8); per-slot "Change Storage" casing map.
- [ ] failing tests → RED → implement → GREEN → full suite → commit `fix(planner): stale-closure restore, compat fetch hygiene, a11y labels (M2.5 Task 6)`.

### Task 7: Neural-luxury visual polish (P2, audit §7)

**Files:**
- Modify: `frontend/src/App.css` (spacing/hierarchy in build workspace only), `frontend/src/App.jsx` (section ordering per spec hierarchy)
- Test: none (visual; covered by browser acceptance + existing snapshot-free suites)

- [ ] Apply section hierarchy (Overview → Compatibility → Configuration → Detail → Intelligence → Assistant), density/spacing tokens only, empty-state copy, mobile nav check. No new identity, no glow additions.
- [ ] `npm run build` + full frontend suite green → commit `style(planner): build workspace hierarchy + density polish (M2.5 Task 7)`.

### Task 8: Docs, evidence, delivery report

**Files:**
- Create: `docs/design/M2_5_UX_DECISIONS.md`, `docs/build-planner/M2_5_POWER_SEMANTICS.md`, `docs/build-planner/M2_5_AI_CONTEXT_CONTRACT.md`, `docs/build-planner/M2_5_TEST_MATRIX.md`, `docs/release/M2_5_DELIVERY_REPORT.md`
- Screenshots: `docs/design/evidence/m2-5/` via a capture script adapted from `capture_m2_preview.py` against a disposable local preview (vite preview + disposable DB copy; production/staging untouched)

- [ ] Write docs; capture desktop/mobile/dark/light/empty/full/incompatible/unknown screenshots; commit `docs(planner): M2.5 delivery evidence and reports`.

## Final gates

- Backend CI-parity suite green; frontend suite green; vite build OK.
- Browser acceptance vs local preview (DOM assertions; pixel review disclosed as limitation).
- Independent review pass (backend correctness, frontend regression, security, hardware-domain, visual).
- Prod + M2 staging untouched (verify container IDs before/after).
