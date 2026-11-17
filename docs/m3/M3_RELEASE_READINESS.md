# M3 Release Readiness (Phase 11)

**Date**: 2026-11-17
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

Seven read-only scopes executed by independent reviewer agents; verdicts and
finding dispositions are consolidated in `M3_FINAL_DELIVERY.md` §reviews.

## 4. Gate checklist

| Gate | Criterion | Status |
|---|---|---|
| Deliverables | 14 docs + evidence | done (13 + final report at release) |
| Pilot | 400 verified records, idempotent, provenance-complete | PASS (scope 7 audit) |
| TDD | RED→GREEN→REGRESSION per phase | evidenced per phase |
| Safety | zero prod writes/staging mutations/main merges | held throughout |
| Compatibility | M2.5-RULES-v1 byte-unchanged, no false positives | PASS (scope 4) |
| Security | no Critical/High findings open | see consolidated verdict |

## 5. Residual risks for the merge reviewer

1. Same-source conflict detection gap + unwired conflict gate (scope 2,
   Medium ×2) — dispositions in the final report.
2. `lastVerifiedOn` includes non-verified records (scope 5, Medium).
3. v4 column rollback requires file-restore, not in-place downgrade (§2.3).
4. `data/spectra.db` in the worktree is an untracked pre-v4 dev artifact
   (has `owner_id`, no `schema_version`) — `upgrade()` on it fails loudly
   (`duplicate column name: owner_id`) rather than corrupting; production DB
   hygiene (tracked migrations, copy-first) unaffected.
