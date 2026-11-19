# M3 Test Matrix

**Date**: 2026-11-18 (remediation revision; original 2026-11-17)
**Command parity**: every command below was run in the M3 worktree
(`C:\Users\user\spectra-m3`, branch `feat/m3-catalog-expansion`) with the
CI-parity flags. Backend: Python 3.13, pytest. Frontend: Node's built-in test
runner (`node --test`), not vitest.

## 1. Backend matrix

| Area | Test file(s) | Count | Status |
|---|---|---|---|
| M3 identity + canonical keys | `test_identity_*.py` (Phases 0-1) | (see full run) | pass |
| Migration v4 | `test_migration_runner.py` | (see full run) | pass |
| M3 validation rules (Phase 3) | `importers/test_m3_validation.py` | 26 | pass |
| M3 adapters (Phase 2) | `scripts/test_m3_adapters.py` | 8 | pass |
| Publisher + lifecycle (Phase 4) | `publishing/test_publisher.py` | (see full run) | pass |
| Pilot seed generator (Phase 5) | `scripts/test_m3_pilot_seed.py` | 9 | pass |
| Compatibility integration (Phase 6) | `services/test_m3_compatibility_integration.py` | (see full run) | pass |
| Provenance API + ops visibility (Phases 7-8) | `test_source_provenance_api.py` | 25 | pass |
| Auth-on ops matrix (Phase 8) | `test_auth_security.py` | 21 | pass |
| **Phase 9 security/perf** | `test_m3_security.py` | **18** | **pass** |

### Phase 9 test inventory (`backend/app/test_m3_security.py`)

| Class | Test | Pins |
|---|---|---|
| `TestOpsInjectionProbes` | `test_service_layer_refuses_unknown_table_names` | `_ops_rows` allow-list refuses non-ops tables (`OpsTableUnavailableError`) |
| | `test_limit_validation_rejects_hostile_values` | `limit=1 OR 1=1` / `;DROP` / `abc` / `0` / `-1` / `101` / `99999999` → 422, never executed |
| | `test_response_shape_cannot_be_widened_by_params` | response key sets fixed for both ops endpoints |
| | `test_ops_tables_survive_hostile_requests` | clean read still 200 after probes |
| `TestMalformedSpecValues` | 7 tests | string numbers, non-numeric strings, bools → explicit blockers; `None` stays absent; valid numbers pass; `validate_record` blocks with field name |
| `TestPublisherMalformedInput` | `test_malformed_record_rejected_batch_survives` | malformed row rejected with reason; valid row in same batch publishes; transaction survives |
| `TestAdaptersZeroNetworkIO` | `test_adapter_module_imports_no_network_libraries` | AST: no socket/httpx/requests/urllib/subprocess imports in `m3_adapters.py` |
| | `test_adapter_module_defines_no_io_functions` | AST: no `open`/`urlopen`/`socket`/... call sinks |
| | `test_map_record_works_with_network_disabled` | mapping + acquire succeed with `socket.socket` constructor raising |
| `TestQueryPerformanceEnvelope` | `test_catalog_list_query_count_is_constant_at_scale` | exactly 2 queries for `/hardware?limit=100` over 420 rows; X-Total-Count=420 |
| | `test_catalog_filtered_scan_stays_bounded` | exactly 2 queries with type+q+manufacturer filters |
| | `test_provenance_query_count_stays_bounded_for_new_categories` | ≤ 12 queries for RAM provenance with 30 provenance rows |

## 2. Exact commands and results

Backend (CI-parity, from the worktree root):

```
python -m pytest backend -q ^
  --ignore=backend/app/test_benchmark_matching.py ^
  --ignore=backend/app/importers/test_benchmark_cpu_import.py ^
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle ^
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking
```

- Phase 11 remediation final run: **1425 passed**, 2 skipped, 2 deselected
  (up from 1410 — +15 remediation tests for the strengthened evidence
  gate: Layer 3 adversarial cases + pilot provenance completeness).
- Targeted RED evidence: `python -m pytest backend/app/importers/test_m3_validation_evidence_gate.py -q`
  → first run 10 failed (adversarial cases absent), after GREEN +15 passed.

Frontend (unchanged by Phase 9; last full run in Phase 7):

```
cd frontend; cmd /c "npm test"    # node --test src/*.test.js → 680 passed
```

## 3. Failure / boundary coverage added in Phase 9

- Malformed data at every M3 boundary: adapter row (missing name/citation,
  invalid fields JSON — Phase 2 tests), spec value type (Phase 9), lifecycle
  gate (Phase 4), publisher batch mix (Phase 9), pre-v4 DB (Phase 8 503s),
  hostile query input (Phase 9 422s).
- Boundary values: `limit` 0 / 1 / 100 / 101 / -1 / huge; bool-as-int spec
  values; `None` vs empty-string fields.

## 4. Known gaps (honest)

1. Wall-clock latency budgets are not enforced (documented in
   M3_SECURITY_REVIEW.md §4).
2. Frontend has no new Phase 9 tests — Phase 9 scope is backend
   input/validation/SQL/network surfaces; frontend provenance UI was covered
   in Phase 7.
3. The malformed-value fix changes publisher rejection *messages* (from a
   crash to reasons); no downstream consumer parses rejection text, so no
   compatibility risk was identified.
