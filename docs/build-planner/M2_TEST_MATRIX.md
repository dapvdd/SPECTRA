# M2 Test Matrix — Build Planner Compatibility

Status: **GREEN** · Branch `feat/build-planner-m2-compatibility` · 2026-11-11

## Backend (pytest)

Full suite command (CI parity):

```
python -m pytest backend -q
  --ignore=backend/app/test_benchmark_matching.py
  --ignore=backend/app/importers/test_benchmark_cpu_import.py
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking
```

Result: **1228 passed, 2 skipped, 2 deselected** (M1 baseline: 1166 → +62).

Compatibility-specific tests (68 total):

### test_compatibility_model.py (15) — domain model
| Requirement | Test | Status |
|---|---|---|
| Exactly 3 compatibility states | `test_exactly_three_compatibility_states` | pass |
| NOT_APPLICABLE distinct from UNKNOWN | `test_not_applicable_is_distinct` | pass |
| UNKNOWN first-class | `test_unknown_is_first_class_state` | pass |
| Stable serialization | `test_serialization_is_stable` | pass |
| Result payload keys | `test_serialization_round_trip_keys` | pass |
| Immutability | `test_result_is_immutable` | pass |
| UNKNOWN reports missing fields | `test_unknown_result_reports_missing_information` | pass |
| All-compatible → COMPATIBLE | `test_all_compatible_aggregates_compatible` | pass |
| Any incompatible → INCOMPATIBLE | `test_any_incompatible_aggregates_incompatible` | pass |
| Unknown without incompatibility → UNKNOWN | `test_unknown_without_incompatibility_aggregates_unknown` | pass |
| NOT_APPLICABLE doesn't block | `test_not_applicable_rules_do_not_block_compatible` | pass |
| NOT_APPLICABLE + UNKNOWN → UNKNOWN | `test_not_applicable_with_unknown_still_unknown` | pass |
| No rules → UNKNOWN (never COMPATIBLE) | `test_no_rules_aggregates_unknown` | pass |
| Explanations surfaced | `test_aggregate_includes_explanations` | pass |
| Deterministic re-evaluation | `test_repeated_evaluation_is_deterministic` | pass |

### test_compatibility_rules.py (35) — rule functions (pure fixtures)
| Requirement | Tests | Status |
|---|---|---|
| CPU socket match / mismatch / missing | 3 tests (compat/inc/unknown) | pass |
| BIOS never claimed on match | `test_socket_match_does_not_claim_bios_support` (requires explicit disclaimer) | pass |
| RAM generation match/mismatch/missing | 4 tests | pass |
| Nominal speed never decides | `test_nominal_speed_never_decides` | pass |
| Capacity within/over/boundary/missing | 4 tests (boundary equal-max = compatible) | pass |
| Slots fit/over/missing | 3 tests | pass |
| Storage NVMe/SATA/HDD/missing | 6 tests | pass |
| M.2 keying not claimed | `test_m2_keying_is_not_claimed` | pass |
| PSU sufficient/insufficient/missing | 5 tests + connector note never claimed | pass |
| GPU slot presence/zero/missing interface | 3 tests | pass |
| Registry stable IDs, unique, ids echoed | 3 tests | pass |

### test_build_compatibility_api.py (12) — API contract
| Requirement | Test | Status |
|---|---|---|
| Full build verdict + rules_version | `test_full_compatible_build` | pass |
| Socket mismatch → INCOMPATIBLE w/ explanation | `test_incompatible_socket_build` | pass |
| Partial build never COMPATIBLE | `test_partial_build_is_not_compatible` | pass |
| Empty build → UNKNOWN | `test_empty_build_is_unknown` | pass |
| Partial evaluates only applicable rules | `test_cpu_plus_mobo_partial_evaluates_applicable_rules` | pass |
| Unknown ID → 404 (slot named) | `test_unknown_component_id_is_404` | pass |
| Wrong category → 422 | `test_wrong_category_id_is_422` | pass |
| Malformed body → 422 | `test_invalid_payload_shape_is_422` | pass |
| **No DB writes** (row counts unchanged) | `test_no_database_writes` | pass |
| Deterministic repeated calls | `test_deterministic_repeated_evaluation` | pass |
| Provenance surfaced in results | `test_provenance_reference_surfaced` | pass |
| Existing endpoint regression | `test_existing_hardware_endpoint_unchanged` | pass |

## Frontend (node --test)

`node --test src/*.test.js` → **663 passed, 0 failed** (M1 baseline 637 → +26).

### New: categoryDetail.test.js (10)
RAM view (no Cores/Threads/Socket), N/A for missing, storage interface+perf,
motherboard socket/chiset/expansion, PSU wattage/efficiency/connectors,
router fallback CPU for unknown type.

### New: buildSlots.test.js (16)
Six slots in order, init null ×6, per-slot set/reject/replace/clear,
summary prompts for all six + isComplete, action labels per category,
spec strips per category without CPU fields, slot detail requests independent,
unsupported slot rejection.

### Updated: buildConfig.test.js
Existing expectations extended to the 6-slot shape (init/summary/independence).

## Integration coverage
- Catalog → Build selection: existing flows preserved (BuildComponentCard
  shared for all six slots; `browseForBuildType` navigates to the type filter).
- Build → Compatibility API: `test_build_compatibility_api.py` (12) + frontend
  refresh effect keyed on slot-ids JSON.
- API → explanation rendering: `BuildCompatibilitySection` renders rule
  explanations, missing fields, provenance counts.
- Partial build → unknown state: covered backend + frontend (UNKNOWN chip).
- No unintended DB writes: `test_no_database_writes` counts rows before/after.

## Build
`npx vite build` → ✓ built (dist/assets/index-*.js, gzip ~102 kB).

## Regression
- Backend: 1228 passed (baseline 1166 + 62 new).
- Frontend: 663 passed (baseline 637 + 26 new).
- No existing test was deleted; only six expectations updated to the new
  six-slot state shape (documented above).
