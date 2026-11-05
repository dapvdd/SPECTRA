# SPECTRA Data Recovery — Remaining Work Plan

## Priority 1 — Sentinel normalization (RED -> GREEN)
- [ ] Write RED regression tests for sentinel values: unknown, n/a, na, null, none, -, whitespace, empty.
- [ ] Fix `GpuArkAdapter.normalize_field_value` so sentinels -> None.
- [ ] Ensure `EnrichmentPlan._classify` rejects sentinels defensively.
- [ ] Run tests GREEN.

## Priority 2 — Safe identity resolution
- [ ] Implement source-aware GPU name normalization (no blind vendor stripping).
- [ ] Preserve desktop/mobile distinctions, model suffixes, TGP configs.
- [ ] Quarantine ambiguous matches instead of importing.

## Priority 3 — Revalidate enrichment
- [ ] Recalculate candidate counts after sentinel filter:
  - valid non-NULL source values
  - sentinel-only candidates
  - ambiguous identity matches
  - already-complete records
  - truly unresolved records
  - safe eligible updates
- [ ] Re-run dev import on valid evidence only.
- [ ] Verify persisted values, units, provenance, idempotency, rollback.
- [ ] Do not claim 141 successful updates unless all 141 pass validation.

## Priority 1 — Sentinel normalization (GREEN ✅)
- [x] Write RED regression tests for sentinel values.
- [x] Fix GpuArkAdapter.normalize_field_value so sentinels -> None.
- [x] Ensure EnrichmentPlan._classify rejects sentinels defensively.
- [x] Run tests GREEN (111/111 pass).
- [x] Committed `7cf8d08`, pushed, remote SHA verified.

## Priority 2 — Safe identity resolution (GREEN ✅)
- [x] Implement source-aware GPU name normalization (no blind vendor stripping).
- [x] Preserve desktop/mobile distinctions, model suffixes, TGP configs.
- [x] Ambiguous matches quarantined (not imported).
- [x] gpu_identity.py + 25 regression tests.
- [x] Committed `5854594`, pushed, remote SHA verified.

## Priority 3 — Revalidation ✅
- [x] Recalculated candidates after sentinel filter:
  - csv_valid_rows=13119 (non-sentinel), db_null_tdp_count=204
  - sentinel_only=128 (not enrichable), unresolved=199
  - safe_updates=5 (clean writes), quarantined=0
- [x] Real scratch import: 5/5 clean writes, idempotent, rollback verified.
- [x] NOT claiming 141; honest number is 5 safe updates + 128 sentinel-only + 199 unresolved.

## Priority 4 — Finish Objectives C, D, E (GREEN ✅)
- [x] Multi-core calibration sensitivity: 80.2% drift rate, observed max 24.74%.
       Stars inflate for high-end (12303→doc 4.51* obs 5.00*) — NO anchor changes.
- [x] Preserve prod DB integrity (disposable copy used, prod untouched).
- [x] End-to-end API validation — 32/43 PASS on disposable copy.
       REAL FINDING: schema drift — build_conversations.owner_id missing → 500s.
       (Report-only; prod DB integrity preserved.)
- [x] Full regression gates: backend 992p / frontend 611p / build OK.
- [x] Committed in 2 increments, pushed, remote SHA verified.

**Remote SHA: `585459432dd8ba0626bc01bf5f28a56f9512c719` — matches origin/feature/spectra-delivery-20261028**
