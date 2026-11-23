# M3.1 Release Readiness

**Date**: 2026-11-23. Verdict and final evidence for `feat/m31-catalog-acquisition`.

## Verdict

**CONDITIONALLY READY (dev-published, draft PR)** — the acquisition pipeline is proven end-to-end with 49 verified SKUs published to an isolated dev DB through the fail-closed evidence gate; the catalog expansion is honest (394 candidates honestly UNRESOLVED, 0 fabrication). Production publication requires the owner's explicit rehearsed run; this branch delivers the pipeline, the verified data, and the evidence.

## Final test matrix (exact commands + results)

| Suite | Command | Result |
|---|---|---|
| Backend CI-parity | `python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking` (per CI yml line 69/77) | **1498 passed, 2 skipped, 2 deselected** (2026-11-23) |
| Acquisition units | `python -m pytest backend/app/catalog/acquisition/test_acquisition.py backend/app/catalog/acquisition/test_acquisition_adapters.py backend/tests/test_category_runner.py -q` | 72 passed |
| Frontend tests | `npm test -- --run` | **681 passed, 0 failed** (2026-11-23) |
| Frontend build | `npm run build` | built in 466ms, no errors |
| Frontend lint | `npx oxlint src` | 4 pre-existing set-state-in-effect warnings (identical set on `main` — branch touches no frontend file) |
| Evidence-gate regression | included in backend suite (`test_m3_validation_evidence_gate.py`, `test_pilot_seed_evidence_gate.py`) | green |
| Publisher transactional/idempotency | `test_publisher.py`, `test_acquisition.py` | green |
| Rehearsal integrity | `PRAGMA integrity_check` → ok; `foreign_key_check` → 0 violations | pass |

## Publication evidence

- `data/dev/m31_acquisition.db`: 49 hardware rows (RAM 32 / STORAGE 10 / PSU 7), 270 field_provenance rows, all `evidence_status='verified'`, every row carrying MPN + per-SKU URL + source_reference + match_method + access_date.
- Idempotency: re-run skipped_existing 49, published 0.
- `docs/m3/evidence/m31_run_log.json`: rehearsal step log.

## Merge-gate checklist

- [x] All M3 Core security/compatibility/publication guarantees preserved (no publisher changes; acquisition composes existing publisher).
- [x] Fail-closed evidence gate exercised end-to-end (49 verified records; 0 gate bypasses).
- [x] No production writes; publisher refuses `data/spectra.db` (structural pin).
- [x] No force-push; draft PR only.
- [x] Unknown optional fields NULL (no family-level inheritance).
- [x] Reimport idempotent; quarantined records never publish.
- [x] Source registry updated (`M3_SOURCE_REGISTRY.md` changelog 2026-11-23).
- [x] Delivery docs complete (ACQUISITION_REPORT, SKU_VERIFICATION_MANIFEST, DATA_QUALITY_REPORT, RESIDUAL_RISKS, evidence run log).

## What ships in the draft PR

1. Acquisition package (`backend/app/catalog/acquisition/`): manifest, resolver, pipeline, errors, wiki_rest, adapters, category_runner.
2. Research artifacts (`data/research/m31/`): candidate inventory, 3 verified-SKU manifests, research notes, resolution report, builder + rehearsal scripts.
3. Delivery docs (`docs/m3/M31_*.md`, evidence run log).
4. No changes to `data/spectra.db`, no production config, no frontend runtime changes.

## Outstanding before production publication (owner actions)

1. Owner-rehearsed publication to the production DB (explicitly chosen path; this branch only proves the rehearsal).
2. Optional: approve additional manufacturer sources (JSON APIs, per registry gate) to widen family coverage beyond Corsair/WD/Kingston.
