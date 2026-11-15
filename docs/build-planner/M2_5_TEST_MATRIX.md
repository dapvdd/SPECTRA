# M2.5 Test Matrix — Unified Build Experience

Status: **GREEN** · Branch `feat/spectra-m2.5-unified-build-experience` · 2026-11-13
Base: `origin/main` @ `abb2548` (M2 delivery baseline: backend 1228 / frontend 664).

## Backend (pytest)

Full suite command (CI parity — four documented ignores/deselects, unchanged
since M2):

```
python -m pytest backend -q
  --ignore=backend/app/test_benchmark_matching.py
  --ignore=backend/app/importers/test_benchmark_cpu_import.py
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking
```

Result: **1247 passed, 2 skipped, 2 deselected** (M2 baseline 1228 → +19).

## M2.5 deltas by task (test-first: every row was written RED, then GREEN)

### Task 1 — PSU power semantics (commits `f8bf90e`, `8f86a1d`) — +8 backend

| Requirement | Test | File |
|---|---|---|
| Wattage at TDP reference → UNKNOWN, never COMPATIBLE | `test_wattage_at_tdp_reference_is_unknown_not_compatible` | test_compatibility_rules.py |
| Below the reference floor → INCOMPATIBLE | `test_grossly_insufficient_wattage_is_incompatible` (125+250=375 W → ref 488 W vs 450 W) | ″ |
| UNKNOWN explanation labeled non-authoritative + listed TDP | `test_unknown_explanation_is_non_authoritative_and_tdp_labeled` (also bans "draw"/"covers") | ″ |
| INCOMPATIBLE explanation names the floor honestly | `test_incompatible_explanation_labels_tdp_reference` | ″ |
| Connector gaps declared, never silently skipped | `test_missing_connector_info_is_declared` | ″ |
| No CPU/GPU → NOT_APPLICABLE | `test_no_cpu_or_gpu_is_not_applicable` | ″ |
| API-level PSU floor | `test_insufficient_psu_tdp_reference_is_incompatible` | test_build_compatibility_api.py |
| Registry metadata obeys the wording ban | `test_registry_descriptions_avoid_measured_power_language` (`8f86a1d`) | test_compatibility_rules.py |

`rules_version` assertion updated to `M2.5-RULES-v1` inside
`test_build_compatibility_api.py` (existing expectation updated, documented).

### Task 2 — Category-aware filters + Compare gating (commit `3873b6d`) — +2 backend, +4 frontend

| Requirement | Test | File |
|---|---|---|
| Manufacturer facets self-exclude their own filter | `test_manufacturer_facet_excludes_its_own_filter` | test_catalog_v31_categories.py |
| Type facets self-exclude their own filter | `test_type_facet_excludes_its_own_filter` | ″ |
| Options derive from live facets, "All" first | `manufacturer options derive from live facet data, All first` | catalog.test.js |
| No facet data → `["All"]` fallback | `manufacturer options fall back to All when no facet data` | ″ |
| Stale selection resets to "All" | `manufacturer filter resets when the selection leaves the option set` | ″ |
| Compare supported for CPU/GPU only | `comparison support matrix covers only CPU and GPU` | ″ |

### Task 3 — Unified six-slot summary (commit `ad652d9`) — +3 frontend

| Requirement | Test | File |
|---|---|---|
| Completeness counts selected slots of 6 | `six-slot build summary counts selected slots out of six` | buildConfig.test.js |
| Relationship label derives from populated slots | `build relationship label derives from populated slots` | ″ |
| Raw constants humanized (Storage/Motherboard) | `build slot display names humanize raw type constants` | ″ |

### Task 4 — Honest, deduplicated Intelligence (commit `ce65b87`) — +5 frontend

| Requirement | Test | File |
|---|---|---|
| Measured-power gap appears once, not in two lists | `the measured-power gap appears once, not in two lists` | buildIntelligence.test.js |
| Coverage figure single-sourced | `the specification coverage figure is single-sourced` | ″ |
| Gaps never claim compatibility data is missing | `data gaps never claim compatibility data is missing` | ″ |
| Platform gap reflects selected slots | `platform gap reflects selected slots instead of a blanket claim` | ″ |
| TDP disclaimer deduplicated | `power disclaimers appear at most once outside the power notice` | ″ |

### Task 5 — Compatibility digest in chat context (commit `672109f`) — +12 backend, +11 frontend

| Requirement | Test | File |
|---|---|---|
| Context without digest validates unchanged | `test_context_without_digest_validates_unchanged` | test_build_chat_context.py |
| Bounded digest accepted | `test_context_accepts_bounded_digest` | ″ |
| >7 rule results rejected | `test_context_rejects_unbounded_rule_results` | ″ |
| Unknown aggregate state rejected | `test_digest_rejects_unknown_aggregate_state` | ″ |
| Over-long strings rejected | `test_digest_rejects_unbounded_strings` | ″ |
| Rule state must be a verdict | `test_digest_rule_state_must_be_a_compatibility_state` | ″ |
| Prompt payload carries the digest | `test_prompt_payload_includes_digest_when_supplied` | ″ |
| Absent digest serializes as `compatibility: null` | `test_prompt_payload_keeps_digest_key_null_when_absent` | ″ |
| Rule 14 in prompt: names INCOMPATIBLE, forbids "ready" claims | `test_prompt_names_incompatible_builds_and_forbids_ready_claims` | ″ |
| `unresolved` reaches the payload | `test_unresolved_checks_are_prompt_payload_members` | ″ |
| API accepts a digest and answers | `test_api_accepts_digest_and_returns_answer` | ″ |
| Malformed digest → 422 | `test_api_rejects_malformed_digest_with_422` | ″ |
| Digest withheld while loading / failed | `the compatibility digest is withheld while the check is loading`, `…when the check failed` | buildChat.test.js |
| Settled check → bounded digest | `a settled compatibility state becomes a bounded digest` | ″ |
| NOT_APPLICABLE rules dropped | `the digest drops rules whose state is not a compatibility verdict` | ″ |
| Bounds enforced client-side | `the digest never exceeds the bounded rule-result and unresolved counts`, `the digest truncates over-long explanations and unresolved text` | ″ |
| Slot map sanity | `the digest keeps only positive integer slot ids` | ″ |
| Unresolved fallback text | `the digest falls back to the rule explanation when no field is named` | ″ |
| Payload transport | `the chat payload carries the compatibility digest inside the build context`, `the chat payload omits the compatibility key when no digest is supplied` | ″ |
| App wiring (source assertion) | `App wires the settled compatibility check into every build chat request` | ″ |

### Task 6 — Hardening (commit `aebc688`) — +9 frontend

| Requirement | Test | File |
|---|---|---|
| Non-CPU/GPU slots never restore chat | `restore ignores slots that are not part of the chat identity` | buildHardening.test.js |
| Restore resolves pair + token | `restore resolves the CPU+GPU pair and the chat token from the snapshot` | ″ |
| Restore waits for the other slot | `restore waits until the other slot detail is present` | ″ |
| **Stale-closure regression** (F6) | `restore pairs a late CPU with the GPU already in the snapshot (stale-closure regression)` | ″ |
| Empty build has no selection (F7) | `an empty build has no selected component`, `any positive slot id counts as a selection` | ″ |
| Ref mirror, not render closure | `the build detail restore reads a live ref mirror, not the render-scope state` | ″ |
| Empty build never POSTs | `the compatibility effect short-circuits an empty build` | ″ |
| Casing (F8) | `build slot prose never leaks the raw uppercase slot constants` | ″ |

### Task 7 — Reading order (commit `9489197`) — +2 frontend (source assertions)

| Requirement | Test | File |
|---|---|---|
| DOM reading order locked | `the build workspace reads overview, compatibility, configuration, detail, intelligence, assistant` | buildHardening.test.js |
| Dissolved wrappers absent | `the dissolved workspace wrappers are gone from the build markup` | ″ |

## Frontend (node --test)

`npm test -- --run` → **697 passed, 0 failed** (M2 baseline 664 → +33; plus
`npm run lint` passes with pre-existing-style warnings only, and
`npm run build` ✓).

Per-file counts (full M2.5 branch): buildChat 60, buildConfig 68,
buildCompatibility 23, buildHardening 11, catalog 34, buildSlots 16,
buildIntelligence 64 — the seven files touched by M2.5.

## Browser evidence (DOM assertions, not pixel reads)

`docs/design/evidence/m2-5/dom-checks.json` — **43/43 passed** against a
disposable preview (backend :8010 + temp DB, vite preview :4180; production and
staging never contacted). Coverage: six-slot counts, per-state chips
(empty/A/B/C), rule-row composition (5 compatible + 2 unknown for build A),
wording bans (`draw`/`covers`/ready-claims absent), PSU non-authoritative
label, Missing-lines for unknown-heavy build C, section reading-order offsets
increasing, dissolved wrappers absent, four category detail views free of
CPU-only fields, mobile 390px with zero horizontal overflow, dark theme applied
(`data-theme="dark"`). 15 PNGs captured for human review.

## Regression

- Backend: 1247 passed (baseline 1228 + 19 new).
- Frontend: 697 passed (baseline 664 + 33 new).
- Existing expectations updated deliberately: `rules_version` →
  `M2.5-RULES-v1`; PSU-state expectations under the two-tier policy; legacy
  "CPU + GPU configuration" strings. **No test deleted.**
- The four documented backend ignores/deselects are environment-gated tests
  (local gitignored DBs / deployment cycles), unchanged from the M2 contract.
