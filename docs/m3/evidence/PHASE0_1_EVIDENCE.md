# M3 Evidence — Phase 0/1 (2026-11-16)

## Baseline verification
- origin/main verified: `5074211` (matches mission "last reported main")
- Worktree: `C:\Users\user\spectra-m3`, branch `feat/m3-catalog-expansion`
- Production (read-only): 5,389 hardware (3,501 CPU / 1,879 GPU / 9 new-cat),
  schema v3, 39,503 field_provenance, 11 sources, all containers up

## Commands + results (Phase 0/1)
- `python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect=...deployment_config...`
  → **1274 passed, 2 skipped, 2 deselected** (CI-parity flags; includes 18 new
  Phase 1 tests: 18 identity + 9 migration v4, with runner pins updated 1,2,3→1,2,3,4)
- Baseline check before M3 changes (stash): same suites green after DB init;
  the 18 failures initially seen were environmental (worktree had no dev DB —
  CI runs `seed_ci_dev_db`-equivalent init; not a code regression)
- Production audit: docker exec read-only URI-mode SQLite (script deleted after)
- Migration v4: applies additively on v3 copy; re-run no-op; NULL keys allowed;
  duplicate non-NULL keys rejected; legacy rows untouched

## Files (Phase 0/1)
- docs/m3/M3_PRD.md, M3_BASELINE_AUDIT.md, M3_SOURCE_FEASIBILITY.md,
  M3_SOURCE_REGISTRY.md, M3_DATA_CONTRACT.md, M3_IDENTITY_RULES.md
- backend/app/identity/{__init__,canonical,manufacturer_aliases,test_canonical}.py
- backend/app/migrations/test_migration_v4.py + runner.py (v4 appended)
- backend/app/test_migration_runner.py (pins updated for v4)
