# M3 Release Readiness (Phase 11)

**Date**: 2026-11-18 (remediation revision; original 2026-11-17)
**Branch**: `feat/m3-catalog-expansion` (draft PR target; main untouched at
`5074211`; no merges, no force-push, no production writes at any point).

## 1. Deliverable inventory (mission §11 — 14 docs + evidence)

| # | Deliverable | File | Status |
|---|---|---|---|
| 1 | PRD / implementation contract | `docs/m3/M3_PRD.md` | done |
| 2 | Baseline audit | `docs/m3/M3_BASELINE_AUDIT.md` | done |
| 3 | Source feasibility (Gate 0) | `docs/m3/M3_SOURCE_FEASIBILITY.md` | done |
| 4 | Source registry | `docs/m3/M3_SOURCE_REGISTRY.md` | done |
| 5 | Data contract | `docs/m3/M3_DATA_CONTRACT.md` | done |
| 6 | Identity rules | `docs/m3/M3_IDENTITY_RULES.md` | done |
| 7 | Ingestion pipeline | `docs/m3/M3_INGESTION_PIPELINE.md` | done |
| 8 | Validation rules | `docs/m3/M3_VALIDATION_RULES.md` | done |
| 9 | Data quality report (pilot) | `docs/m3/M3_DATA_QUALITY_REPORT.md` | done |
| 10 | Compatibility impact | `docs/m3/M3_COMPATIBILITY_IMPACT.md` | done |
| 11 | UX implementation | `docs/m3/M3_UX_IMPLEMENTATION.md` | done |
| 12 | Ops visibility | `docs/m3/M3_OPS_VISIBILITY.md` | done |
| 13 | Security review | `docs/m3/M3_SECURITY_REVIEW.md` | done |
| 14 | Test matrix | `docs/m3/M3_TEST_MATRIX.md` | done |

Evidence: `docs/m3/evidence/PHASE{0_1,2_3_4,5,6,7,8,9}_EVIDENCE.md` (8 files).
The final delivery report (`M3_FINAL_DELIVERY.md`) closes the set at release
time (it summarizes this inventory and the verdict — created after review
results are consolidated).

## 2. Migration rehearsal (disposable copies only)

### 2.1 Pilot-shaped rehearsal (already evidenced in Phase 5)

- `_clone_schema` v1 baseline → `upgrade()` v1→v4 → `verify()` = verified
  v4; pilot import idempotent (re-import: published=0, skipped_existing=400;
  provenance total unchanged at 2,500).

### 2.2 Prod-scale rehearsal (this phase; 5,389 legacy rows, prod count)

Setup: fresh v1-baseline clone via `_clone_schema` in
`%TEMP%\opencode\m3_rehearsal_v1.db`, seeded with 5,389 synthetic legacy
hardware rows (the production row count; the real `data/spectra.db` was
**never** opened for writing — it was only hashed and copied read-only).

Results:

- `upgrade()` applied v1→v4 in **0.04 s** (seed 5,389 rows: 1.18 s).
- `verify()` → `verified`, version 4.
- Legacy-row safety: **0** legacy rows received values in any of the 5 new
  columns (`canonical_key`, `product_family`, `identity_status`,
  `record_status`, `superseded_by_id`) — structurally untouched, as
  contracted.
- `uq_hardware_canonical_key` partial unique index present; ops tables
  present; `PRAGMA foreign_key_check` → 0 violations; `integrity_check` → ok.

### 2.3 Rollback rehearsal

- `downgrade(target_version=1)` on the same clone: drops the index + the two
  ops tables, records version 1 — **status `downgraded`**, integrity ok,
  5,389 rows intact.
- **Honest limitation (documented, pre-existing design)**: SQLite <3.35
  cannot `DROP COLUMN`; v4's five hardware columns remain present (all-NULL
  for legacy rows) after a downgrade, by design (runner.py:599-603 — the
  runner's own comment calls this out). The documented rollback story is
  therefore: **restore the pre-migration file copy** (copy-first rehearsal
  makes this the primary path; the in-place downgrade is a convenience that
  removes the additive objects it safely can). A NULL column that no v3 code
  reads is harmless to v3 applications — this is the additive-migration
  property that makes forward-then-restore safe.

## 3. Independent review scopes (Phase 10)

Seven read-only scopes executed by independent reviewer agents. Verdicts:
**2 PASS** (scope 4 compatibility, scope 6 ops/security, scope 7 pilot data —
3 PASS counting the pilot audit), **4 CONCERNS** (scopes 1, 2, 3, 5), no
FAIL. Every Critical/High finding and both gate gaps were fixed in
`d02ba42` + `006e8fa` (dispositions in `M3_FINAL_DELIVERY.md` §reviews).

**Post-Phase-10 merge review (PR #6, 2026-11-18)** returned **HOLD — data
quality verification required**: the scope-7 "pilot data PASS" verdict was
itself wrong — the 400 pilot records were generated family×spec
combinations with family-level citations mislabeled as SKU-verified. The
HOLD is remediated: evidence gate strengthened to three-layer contract,
honest pilot rebuilt, +16 adversarial regression tests, assertion
persisted to DB. **READY_FOR_MERGE_REVIEW** (product decision 2026-11-18:
accept small verified pilot; 443 quarantined → M3.1). PR #6 marked ready
for review; merge and deploy are separate approvals.

## 4. Gate checklist

| Gate | Criterion | Status | Notes |
|---|---|---|---|
| Deliverables | 14 docs + evidence | PASS | |
| Pilot | 2 verified + 443 quarantined; 0 conflicts; 0 fabrications | **READY_FOR_MERGE_REVIEW** | Product decision 2026-11-18: accept the small genuinely verified pilot for M3 Core; 443 quarantined variants → M3.1 Catalog Acquisition. Pre-remediation 400-target claim retracted; every verified field carries MPN + per-SKU citation + source_reference + match_method (SKU_AUDIT_MANIFEST). |
| TDD | RED→GREEN→REGRESSION per phase | PASS | 25 remediation regression tests (was 14): +11 Layer 3 adversarial cases (adversarial class in test_m3_validation_evidence_gate.py: fabricated MPN, family URL w/ unsupported variant, URL-syntax-only, missing locator, conflicting evidence, false verified w/o anchor, missing optional fields, dry-run/apply parity on Layer 3). |
| Safety | zero prod writes/staging mutations/main merges | PASS | remediation vendor-page fetches: manual, read-only, authorized public pages only |
| Compatibility | M2.5-RULES-v1 byte-unchanged, no false positives | PASS | |
| Security | no Critical/High findings open | PASS | 0 open; remediation did not introduce new vulnerabilities |
| **Merge-review HOLD** | evidence gate closes the 400-record data-quality finding | **FIXED** | commits `0a70cf5` (gate v1) + `63b0c2f` (honest pilot) + `3857de3`/`2031e6c` (strengthened: three-layer gate, source_reference + match_method required for 'verified', SKU_AUDIT_MANIFEST, +16 adversarial tests) + `f534be0` (gate assertion persisted to field_provenance) |

## 5. Residual risks for the merge reviewer

1. v4 column rollback requires file-restore, not in-place downgrade (§2.3;
   `downgrade()` now refuses the range with a precise reason — `006e8fa`).
2. `data/spectra.db` in the worktree is an untracked pre-v4 dev artifact
   (has `owner_id`, no `schema_version`) — `upgrade()` on it fails loudly
   (`duplicate column name: owner_id`) rather than corrupting; production DB
   hygiene (tracked migrations, copy-first) unaffected.
3. Stuck-'running' `ingestion_runs` rows on a killed process (scope 3,
   Medium — documented, unfixed; dev-only visibility impact).
4. Concurrent `batch_no` collision (scope 3, Low — safe rollback, unfixed).
5. Spec-column f-string interpolation in `_insert_record` (scope 3, Medium —
   fail-closed anyway: unknown columns abort the batch).
6. `q` LIKE wildcards + `sourceUrl` href allowlist (pre-existing Phase 1.3 /
   UX behavior, unchanged by M3).
7. ~~**Merge-review HOLD remediation (2026-11-18)**: pilot published set is
   now honestly small (2 confirmed SKUs; 443 quarantined variants pending
   per-SKU curation). The evidence gate and pipeline are correct, but the
   original 400-verified-record claim is retracted; see
   `M3_FINAL_DELIVERY.md` §1 (CONDITIONAL_REVIEW) and §4 (finding #12 +
   remediation evidence table). PR #6 stays draft until the curator
   substantiates the quarantined variants or the product accepts the small
   verified set.~~ **RESOLVED** — product decision recorded 2026-11-18:
   accept the small verified pilot; 443 quarantined → M3.1 Catalog
   Acquisition. PR #6 marked ready for review.
8. **Strengthened evidence gate (2026-11-18, `3857de3`)**: 'verified' now
   additionally requires source_reference (evidence locator) + allowed
   match_method (manual-curation | spec-table-row |
   manufacturer-declaration); embedded `_provenance` is forwarded to the
   gate in apply and dry-run (bypass closed). Curation throughput cost per
   record rises accordingly; the SKU_AUDIT_MANIFEST in
   `pilot_sku_verified.py` is the working example of the required shape.
9. **M3.2 final integration gate (2026-11-25)**: cumulative catalog is now
   64 verified-published rows (RAM 33 / MOTHERBOARD 13 / STORAGE 10 /
   PSU 8) across the M3 Core pilot + M3.1 + M3.2 manifests, all carrying
   verified provenance (395 rows; 1 documented 'uncertain' Wikipedia
   background row). Checkpoint durability + content fingerprint gate added
   (`09f30cf`/`0eeb3d2`/`efae97d`); lifecycle fields ride on every hardware
   API payload so the frontend verified chip renders on live data
   (`fa5a549`). Residual: no published CPU/GPU acquisition manifests yet,
   so CPU/GPU rule pairs (R1 socket paths) are exercised at unit level
   only; catalog growth continues to be evidence-gated.
