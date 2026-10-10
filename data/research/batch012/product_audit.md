# SPECTRA Batch 012 — Product Audit

Date: 2026-10-10

## 1. Repository state

- Branch `main`, head `4178659 feat(api): add benchmark query filters` (Batch 011).
- Working tree clean apart from known pre-existing untracked items (`.opencode/`,
  `data/backups/`, `data/raw/`, two legacy `data/spectra.db.bak-*` files, and the
  pre-existing untracked `data/research/batch001/09_independent_audit.md`).
- Database `data/spectra.db` SHA-256
  `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
  (matches the reported checkpoint). `PRAGMA quick_check` = `ok`,
  `PRAGMA foreign_key_check` = empty.
- Counts: hardware 5,239 (3,360 CPU / 1,879 GPU), cpu_specifications 3,360,
  gpu_specifications 1,879, benchmark_results 1,040, external_identifiers
  3,575, sources 9, field_provenance 35,849, build_conversations 4,
  build_messages 4 — all matching the reported state.

## 2. Existing product capabilities relevant to hardware comparison

### Frontend

- **Catalog** (`catalog.js`, `App.jsx`): search, type filter, manufacturer
  filter, paginated grid, per-card spec snippets for GPUs.
- **Hardware detail** (`detail.js`, `hardwareCard.js`, `App.jsx`): full spec
  grids (overview / key / technical for CPU; overview / memory / clocks /
  power & physical / interface for GPU), performance section with per-metric
  cards, hardware chat.
- **Comparison selection** (`appState.js`, `App.jsx`): two-slot A/B selection
  with type-conflict guard, selection summary bar, clear/remove actions.
- **Comparison decision support** (`comparisonDecision.js`, `App.jsx`):
  overview headline, availability status (complete / partial / unavailable),
  measurable/tied/unavailable counts, benchmark support label, lead groups
  ("X leads in N of M measurable metrics"), tied metrics list, data-availability
  notes.
- **Comparison insights** (`comparison.js`, `App.jsx`): per-metric winner,
  percentage difference, ties, unavailable metrics.
- **Benchmark comparison** (`performance.js`, `App.jsx`): Geekbench 7
  single-core / multi-core bar chart for CPU comparisons; explicit "No GPU
  benchmark data" panel for GPU comparisons.
- **Specification table** (`comparisonDecision.js`, `App.jsx`): side-by-side
  spec rows with winner highlighting, direction markers, informational rows.
- **AI analysis** (`comparisonExplanation.js`, `App.jsx`): generates a plain-
  language explanation from structured comparison facts via the backend
  explanation endpoint.
- **Build configuration** (`buildConfig.js`, `buildIntelligence.js`,
  `App.jsx`): CPU+GPU slot selection, build facts, build intelligence signals,
  build chat with conversation persistence.

### Backend

- `GET /hardware` — catalog with optional type/manufacturer filters.
- `GET /hardware/{id}` — full detail with specifications.
- `GET /hardware/{id}/benchmarks` — benchmark results with optional
  `source_id`, `benchmark_name`, `test_type` filters (Batch 011).
- `POST /comparison/explanation` — AI explanation from structured facts.
- `POST /hardware/chat` — hardware-scoped chat.
- `POST /build/chat`, `POST /build/conversation`,
  `POST /build/conversation/{id}/messages` — build chat and persistence.
- `services/comparison_service.py` — legacy CPU-only comparison (cores,
  threads, base/boost clock); not used by the frontend comparison workflow.

### Data reality (verified live)

- **Benchmark coverage is low**: 518 of 3,360 CPUs (15.4%) have benchmark
  data; 0 of 1,879 GPUs have benchmark data. 517 CPUs have exactly 2 records
  (single-core + multi-core); 1 CPU has 6 records.
- **Spec completeness varies**: CPUs — cores null 5, threads null 461,
  boost_clock null 1,076, tdp null 277. GPUs — memory_gb null 341,
  boost_clock null 755, tdp null 204.
- **Only one benchmark suite exists** (Geekbench 7); no gaming benchmark data.

## 3. Concrete friction and deficiencies

### D1. Measured benchmark evidence is conflated with specification-based
evidence in the comparison decision support.

`calculateComparisonInsights` (`comparison.js`) iterates over
`COMPARISON_METRICS`, which mixes two benchmark metrics (`multi_core`,
`single_core` — source `"benchmark"`) with five specification metrics (`cores`,
`threads`, `boost_clock_ghz`, `base_clock_ghz`, `tdp_w` — source
`"specification"`). Wins from both sources are counted into the same
`wins` object and the same `measurableCount`. The decision summary
(`buildComparisonDecisionSummary`) then reports "CPU A leads in X of Y
measurable metrics" without distinguishing that some wins are *measured*
benchmark results while others are *specification* comparisons.

This matters because a CPU that wins both benchmark metrics but loses four
spec metrics is reported as "loses" overall — yet the benchmark wins are
measured evidence and the spec wins are inference. A user comparing two CPUs
where both have benchmark data (the most decision-relevant scenario) cannot
tell measured performance apart from specification differences in the summary.

The `ComparisonInsights` component (`App.jsx`) lists each winning metric with
its label and percentage difference, but the labels ("Geekbench 7 Multi-Core"
vs "Cores") are the only hint that the evidence types differ. There is no
explicit separation.

### D2. No indication of benchmark coverage in the comparison workflow.

When a user compares two CPUs and neither has benchmark data (84.6% of CPU
pairs), the benchmark comparison section shows "NO DATA" and the decision
support shows "Benchmark support: NO DATA". This is accurate but does not
explain *why* — the user cannot tell whether benchmark data is missing because
it was not collected for these CPUs or because the comparison is between
hardware types that do not support benchmarks. The data-availability notes
(`buildComparisonAvailability`) list missing metric labels but do not
distinguish "benchmark data not collected for this hardware" from "spec value
missing".

### D3. Specification table does not show deltas.

The comparison spec table (`buildComparisonSpecRows`) shows raw values with
winner highlighting and a summary ("CPU A is higher"), but does not show the
magnitude of the difference. The insights section shows percentage differences
for measurable metrics, but the spec table — the primary side-by-side view —
does not. A user must mentally compute "24 cores vs 16 cores = +8 cores" or
"5.2 GHz vs 4.8 GHz = +0.4 GHz".

### D4. GPU comparison has no benchmark dimension.

GPU comparisons show "No GPU benchmark data" which is accurate (0 GPUs have
benchmark data), but the decision support does not explain that GPU benchmarks
are not collected at all, unlike CPU benchmarks which are collected for some
CPUs. The `buildComparisonAvailability` note "GPU benchmark scores are not
collected for these GPUs yet" is close but does not clarify the systemic
nature (no GPU benchmark data exists in the dataset).

## 4. Candidate improvements

### C1. Separate measured benchmark evidence from specification-based
evidence in the comparison decision support.

**What**: Partition the comparison insights into two evidence groups —
"Measured benchmarks" and "Specifications" — and surface both in the decision
support UI. Show benchmark wins separately from spec wins, with explicit
labels distinguishing measured from inferred evidence.

**User benefit**: Users can see at a glance whether a CPU leads on measured
benchmark performance or only on specifications. This directly supports
purchasing decisions by making the strength of evidence explicit.

**Complexity**: Frontend-only. New module `comparisonEvidence.js` to partition
insights by source; update `comparisonDecision.js` to include evidence summary;
update `App.jsx` `ComparisonDecisionSupport` to render the separation. No
backend or schema changes. Moderate complexity.

### C2. Show specification deltas in the comparison table.

**What**: Add delta columns or inline delta labels (e.g., "+8 cores",
"-0.4 GHz") to the spec table rows.

**User benefit**: Users can see the magnitude of specification differences
without mental arithmetic.

**Complexity**: Frontend-only. Update `buildComparisonSpecRows` to compute
deltas and `App.jsx` to render them. Low complexity. But the insights section
already shows percentage differences, so the marginal benefit is smaller.

### C3. Add benchmark coverage indicators to the comparison workflow.

**What**: Show a coverage indicator (e.g., "Benchmark data: 1 of 2 CPUs")
when benchmark data is available for only one side, and explain the systemic
lack of GPU benchmark data.

**User benefit**: Users understand whether missing benchmark data is expected
or exceptional.

**Complexity**: Frontend-only. Update `buildComparisonAvailability` and
`App.jsx`. Low complexity. But the existing availability tracking already
covers most of this; the marginal benefit is small.

### C4. Improve handling of incomplete or incomparable benchmark results.

**What**: When benchmark data is available for only one CPU, show a partial
comparison with an explicit note rather than just "NO DATA".

**User benefit**: Users can still see the available benchmark score for one
CPU even when the other has no data.

**Complexity**: Frontend-only. Update `getBenchmarkComparisonData` and
`App.jsx`. Low complexity. But the current behavior (showing "NO DATA" when
either side lacks data) is arguably more honest than showing a one-sided
comparison.

## 5. Selected candidate: C1 — Separate measured benchmark evidence from
specification-based evidence

**Why this offers the best practical value now**:

1. **It addresses the most decision-relevant scenario.** The only situation
   where measured performance data exists is when both CPUs have benchmark
   data. In that scenario, the current UI conflates measured and inferred
   evidence, which is the most misleading situation for a purchasing decision.

2. **It works with existing verified data.** No new data imports, no schema
   changes, no backend changes. The benchmark data already exists and is
   already displayed; this change only reorganizes how it is presented in the
   decision summary.

3. **It handles missing data honestly.** When benchmark data is absent, the
   "Measured benchmarks" section explicitly shows "No data" rather than
   silently dropping benchmark metrics from the count. When benchmark data is
   partial (one CPU has it, the other does not), the section shows the
   available data with an explicit note.

4. **It integrates into the existing workflow.** The change is confined to
   the comparison decision support section, which is already the primary
   decision-support surface. No new screens, no new routes, no new API calls.

5. **It can be implemented and verified in one batch.** The logic is a
   straightforward partition of existing insights by metric source. Tests can
   reuse existing fixtures and patterns.

## 6. Rejected alternatives

- **C2 (spec deltas)**: Nice-to-have but the insights section already shows
  percentage differences. The spec table is a secondary view. Lower marginal
  benefit.
- **C3 (coverage indicators)**: The existing availability tracking already
  covers most of this. The marginal benefit is small and the change would be
  mostly cosmetic.
- **C4 (incomplete benchmark handling)**: The current "NO DATA" behavior is
  arguably more honest than showing a one-sided comparison. Changing it could
  introduce misleading presentations.
- **Frontend benchmark suite generalization** (Batch 011 recommendation):
  Still blocked — only one benchmark suite exists, and the metric model lacks
  a suite dimension. No licensed second dataset is available.
- **Source metadata schema change** (Batch 011 recommendation): Would require
  a schema migration and is not a user-facing improvement.
- **Gaming benchmark import**: Blocked on licensing. No verified reuse
  permission for any gaming benchmark dataset.
