# SPECTRA Batch 012 — Acceptance Criteria

Date: 2026-10-10

## Selected improvement

Separate measured benchmark evidence from specification-based evidence in the
comparison decision support.

## Problem it solves

The current comparison decision support counts benchmark wins and
specification wins together, reporting "CPU A leads in X of Y measurable
metrics" without distinguishing measured benchmark evidence from
specification-based inference. This misleads users about the strength of
evidence when comparing CPUs that have benchmark data.

## Acceptance criteria

### AC1: Evidence separation logic

- A new function `buildComparisonEvidence(compareDetails, benchmarkStates)`
  partitions comparison insights into `benchmark` and `specification` groups.
- Each group contains: `wins` ({cpuA, cpuB}), `ties`, `measurableCount`,
  `metrics` (list of winning metric details), `tieDetails`.
- The partition is by metric `source` (`"benchmark"` vs `"specification"`).
- The function returns `null` for invalid input (not exactly 2 items).
- The function handles missing benchmark states (undefined/null) gracefully —
  benchmark metrics are reported as unavailable, not as spec wins.

### AC2: Decision summary includes evidence

- `buildComparisonDecisionSummary` includes an `evidence` field with the
  partitioned benchmark and specification groups.
- The existing `lead`, `measurableCount`, `tieCount`, `unavailableCount`,
  `canCompare`, `leadLines`, and `limitations` fields are preserved unchanged.
- The `benchmarkSupport` field is preserved unchanged.

### AC3: UI distinguishes measured from inferred evidence

- The `ComparisonDecisionSupport` component renders a "Measured benchmarks"
  section and a "Specifications" section separately when both have measurable
  metrics.
- Each section shows the number of wins per side and the list of winning
  metrics with their difference percentages.
- When benchmark data is unavailable, the "Measured benchmarks" section
  shows an explicit "No data" message rather than being omitted.
- When benchmark data is partial (one side has data, the other does not),
  the section shows an explicit note about partial coverage.
- The existing "Where each side leads" section is preserved but augmented
  with evidence-type labels (e.g., a "Benchmark" or "Spec" badge per metric).

### AC4: Missing and partial data handling

- When neither CPU has benchmark data, the evidence section shows
  "No measured benchmark data" and the spec section shows the spec wins.
- When only one CPU has benchmark data, the evidence section shows the
  available benchmark score for that CPU and notes that the other CPU has no
  data.
- When both CPUs have benchmark data, the evidence section shows the
  benchmark wins and the spec section shows the spec wins.
- Null, zero, and non-numeric spec values are never counted as measurable.
- Zero and null benchmark scores are never counted as measurable.

### AC5: Backward compatibility

- The existing `calculateComparisonInsights` function is unchanged.
- The existing `buildComparisonFacts` function is unchanged.
- The existing `buildComparisonAvailability` function is unchanged.
- The existing `buildComparisonLeadGroups` function is unchanged.
- The existing `ComparisonInsights` component behavior is preserved (it still
  shows the full insight list).
- The existing spec table is unchanged.
- The existing benchmark comparison bar chart is unchanged.
- No backend API changes.
- No database schema changes.

### AC6: Tests

- New tests for `buildComparisonEvidence` cover:
  - Both sides have benchmark data (benchmark and spec wins are separated).
  - Neither side has benchmark data (benchmark group is empty, spec group has
    wins).
  - Only one side has benchmark data (partial coverage).
  - Missing/null spec values (unavailable, not measurable).
  - Zero and null values (never measurable).
  - GPU comparison (no benchmark metrics, all spec).
  - Invalid input (null for non-pair).
- New tests for `buildComparisonDecisionSummary` verify the `evidence` field
  is present and correctly partitioned.
- All existing tests continue to pass.

### AC7: No fabricated data

- No performance is inferred from clock speed or core count alone.
- No estimate is presented as a measured benchmark.
- The evidence separation only reorganizes existing verified values.
- No new benchmark data is added.

## Representative test cases

1. **Both CPUs have benchmark data and full specs**: CPU A wins multi-core
   and single-core; CPU B wins cores and threads. Evidence: benchmark group
   has 2 wins for A; spec group has 2 wins for B.

2. **Neither CPU has benchmark data**: Both have full specs. Evidence:
   benchmark group is empty (0 measurable); spec group has wins.

3. **Only CPU A has benchmark data**: CPU A has single-core score; CPU B has
   no benchmark data. Evidence: benchmark group shows partial coverage note;
   spec group has wins.

4. **GPU comparison**: Both GPUs have specs. Evidence: benchmark group is
   empty (GPUs have no benchmark metrics); spec group has wins.

5. **Missing spec values**: CPU A has cores=null; CPU B has cores=16. Spec
   group: cores is unavailable, not a win for B.
