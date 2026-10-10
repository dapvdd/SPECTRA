# SPECTRA Batch 012 — Final Report

Date: 2026-10-10

## 1. Initial checkpoint and working-tree state

- Branch `main`. Head at start: `4178659 feat(api): add benchmark query
  filters` (Batch 011) — verified via `git log`.
- Working tree: clean apart from known pre-existing untracked items
  (`.opencode/`, `data/backups/`, `data/raw/`, two legacy
  `data/spectra.db.bak-*` files, and the pre-existing untracked
  `data/research/batch001/09_independent_audit.md`).
- Database: `data/spectra.db`, SHA-256
  `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
  (matches the reported checkpoint). `PRAGMA quick_check` = `ok`,
  `PRAGMA foreign_key_check` = empty.
- Counts: hardware 5,239 (3,360 CPU / 1,879 GPU), cpu_specifications 3,360,
  gpu_specifications 1,879, benchmark_results 1,040, external_identifiers
  3,575, sources 9, field_provenance 35,849, build_conversations 4,
  build_messages 4 — all matching the reported state.
- Batch 011's final report and independent audit were inspected
  (`data/research/batch011/`).

## 2. Selected improvement: Evidence separation in comparison decision support

### Problem

The comparison decision support (`calculateComparisonInsights` in
`comparison.js`) counts benchmark wins and specification wins together,
reporting "CPU A leads in X of Y measurable metrics" without distinguishing
measured benchmark evidence from specification-based inference. This
misleads users about the strength of evidence when comparing CPUs that have
benchmark data.

### Solution

A new module `frontend/src/comparisonEvidence.js` partitions comparison
insights into two evidence groups — "Measured benchmarks" and
"Specifications" — and surfaces both in the decision support UI. The
`ComparisonDecisionSupport` component now renders each group separately,
making the distinction between measured and inferred evidence explicit.

### Files changed

**New:**
- `frontend/src/comparisonEvidence.js` — evidence separation logic.
- `frontend/src/comparisonEvidence.test.js` — 12 tests for the new module.

**Modified:**
- `frontend/src/comparisonDecision.js` — `buildComparisonDecisionSummary`
  now includes an `evidence` field with the partitioned groups.
- `frontend/src/comparisonDecision.test.js` — 3 new tests for the evidence
  field in the decision summary.
- `frontend/src/App.jsx` — `ComparisonDecisionSupport` component renders
  the evidence separation via a new `EvidenceGroup` sub-component.

### Design notes

- **No backend changes.** The feature is entirely frontend; the existing
  API already returns all necessary data.
- **No database changes.** No schema migration, no data mutation.
- **Backward compatible.** The existing `lead`, `measurableCount`,
  `tieCount`, `unavailableCount`, `canCompare`, `leadLines`, and
  `limitations` fields are preserved unchanged. The existing
  `ComparisonInsights` component, spec table, and benchmark bar chart are
  unchanged.
- **Honest missing-data handling.** When benchmark data is absent, the
  "Measured benchmarks" section shows "No data" rather than being omitted.
  When benchmark data is partial (one side has data, the other does not),
  the section shows an explicit note about partial coverage.
- **No fabricated data.** The evidence separation only reorganizes existing
  verified values. No performance is inferred from clock speed or core
  count alone.

## 3. Database hash and integrity

- **Unchanged**: `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
  (identical to the Batch 011 checkpoint). No database mutation was required
  or performed by this batch.
- `PRAGMA quick_check` = `ok`; `PRAGMA foreign_key_check` = empty.
- Benchmark rows: 1,040 (identical). GPU benchmark rows: 0 (identical).
- Hardware 1508 scores: 695.0 single-core, 2005.0 multi-core (identical).

## 4. Tests

- Backend: **626 passed**, 0 failed, 0 skipped, 2 pre-existing warnings
  (Starlette `httpx` deprecation; anyio `BlockingPortal` alias) — same two
  warnings as batches 008–011. No backend code change.
- Frontend: **535 passed**, 0 failed, 0 skipped, 0 todo (520 existing + 12
  new `comparisonEvidence` tests + 3 new `comparisonDecision` tests).
- Lint: clean (1 pre-existing warning in `App.jsx` unrelated to this change).
- Docker: not run (no Docker runtime validation claimed).

New-test coverage:
- Evidence separation with both sides having benchmark data.
- Evidence separation with neither side having benchmark data.
- Partial benchmark coverage detection.
- GPU comparison (no benchmark metrics, all spec).
- Missing/null spec values (unavailable, not measurable).
- Zero spec values (never measurable).
- Benchmark ties separated from spec ties.
- Benchmark coverage states (complete, partial, none).
- Benchmark loading state handled gracefully.
- Decision summary includes evidence field.
- Decision summary evidence is null for empty comparison.
- Decision summary evidence handles spec-only comparison.

## 5. Independent audit

`data/research/batch012/independent_audit.md` / `.json` / `.mjs` — verdict
**PASS**, via a separate verification path (direct function imports +
database queries, not the HTTP layer or the feature's own code paths). All
14 checks passed:

- Database SHA-256 unchanged.
- `quick_check` ok, `foreign_key_check` empty.
- Benchmark scores and count unchanged.
- Evidence separation logic correct for benchmark-present, benchmark-absent,
  and partial-coverage scenarios.
- Decision summary includes evidence field.
- No GPU benchmark data fabricated.
- `.opencode/` not tracked.
- `git diff --check` clean.
- No backend files changed.

## 6. Files changed

Implementation:
- `frontend/src/comparisonEvidence.js` (new)
- `frontend/src/comparisonDecision.js` (modified)
- `frontend/src/App.jsx` (modified)

Tests:
- `frontend/src/comparisonEvidence.test.js` (new)
- `frontend/src/comparisonDecision.test.js` (modified)

Research (new, `data/research/batch012/`):
- `product_audit.md`
- `acceptance_criteria.md`
- `final_report.md`
- `independent_audit.md`
- `independent_audit.json`
- `independent_audit.mjs`
- `db_state.py` (audit helper)

Live database: **no changes** (hash unchanged).

**Not staged:** `.opencode/`, `data/backups/`, `data/spectra.db.bak-*`,
`data/raw/`, and the pre-existing untracked
`data/research/batch001/09_independent_audit.md`.

## 7. `.opencode/` untouched

`.opencode/` was not modified, staged, or committed; it remains untracked with
its original contents.

## 8. Recommended Batch 013

1. **Frontend benchmark model** (only if licensed data is added): introduce a
   suite dimension in `performance.js` and use the `source_id` /
   `benchmark_name` / `test_type` API filters; do not add a suite selector
   while only one suite exists.
2. **Source metadata**: consider adding optional `description` / licence
   columns to `sources` (a schema change) so licence/attribution facts can
   live next to the source rather than only on `field_provenance`.
3. **Licensing**: if the user wants, send the drafted permission requests
   (TechPowerUp, PassMark, Primate Labs) and manually review Primate Labs /
   OpenBenchmarking terms from a browser.
4. **Gaming benchmarks**: still gated on a licensed dataset with adequate
   methodology; no import until then.
5. **Spec deltas in comparison table**: show magnitude of difference (e.g.,
   "+8 cores", "-0.4 GHz") in the spec table rows — a natural follow-up to
   this batch's evidence separation work.
