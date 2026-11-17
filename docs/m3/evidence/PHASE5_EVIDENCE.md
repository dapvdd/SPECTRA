# M3 Evidence — Phase 5 pilot catalog (2026-11-17)

## TDD cycle
- RED: `backend/app/catalog/test_pilot_seed.py` written first — 3 failed
  (counts under target, citation-domain allowlist too narrow).
- GREEN: grids expanded with real families/SKU ladders (documented in
  `M3_DATA_QUALITY_REPORT.md` §5); duplicate canonical keys found by test
  were resolved in seed tables as distinct official SKUs.
- Result: 9/9 pass; globally unique keys; kit≠module pinned.

## Pilot execution (`python -m backend.app.scripts.run_m3_pilot`)
- Build pilot DB: `_clone_schema` + `upgrade` → applied [1,2,3,4], verify v4.
- Register 2 curated sources, deterministic dry-run (40 records/250 prov
  planned, nothing written).
- 16 bounded batches (10→25→50→100 × 4 categories): 400 published, 0
  rejected, 0 skipped on first pass; 2 500 provenance rows.
- Idempotency re-run: published=0, skipped_existing=400; provenance total
  unchanged (2 500).
- Final: 400 hardware (100/type), 400 unique canonical keys, FK checks 0
  violations across 6 relationships, integrity_check ok.
- `check_data_integrity --schema-only` on the pilot DB: PASS.

## Environmental fix (not a pilot bug)
- `_clone_schema` in `test_migration_runner.py` rebuilt
  `build_conversations` via `CREATE TABLE AS SELECT`, which drops the
  PRIMARY KEY — making `PRAGMA foreign_key_check` fail with "foreign key
  mismatch" on `build_messages` even when empty. Verified: production and
  the CI dev DB keep the PK (FK check clean); the pilot clone now rebuilds
  the table with an explicit PK (21 migration-runner tests still pass).

## Full-suite state at this point
- Full backend (CI-parity flags): **1351 passed, 2 skipped, 2 deselected**
  (adds 9 pilot-seed tests + 1 source_publication_date contract pin).

## Files
- backend/app/catalog/{__init__,pilot_seed_data,pilot_seed,test_pilot_seed}.py
- backend/app/scripts/run_m3_pilot.py (harness, dev-only, refuses nothing
  but writes only data/dev/m3_pilot.db)
- backend/app/test_migration_runner.py (_clone_schema PK fix)
- docs/m3/M3_DATA_QUALITY_REPORT.md + evidence/phase5_run_log.json
