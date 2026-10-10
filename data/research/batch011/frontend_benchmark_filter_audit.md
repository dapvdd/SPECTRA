# Batch 011 — Frontend Benchmark Filter Audit

Date: 2026-10-10

## 1. Decision

**The existing Geekbench-7 filter in the frontend is retained deliberately;
no frontend code change is made in this batch.** The precise blocker is
documented below. The backend now exposes the optional filters the UI would
need (Workstream A), so the frontend work is correctly deferred behind a
second benchmark family and a suite-aware metric model, not behind missing API
capability.

## 2. Why the hard filter exists

`frontend/src/performance.js` maps a benchmark record to one of four metric
keys: `cpu`, `single_core`, `multi_core`, `gaming`. Only `single_core` and
`multi_core` are populated, and they are keyed by `test_type` alone:

```js
const GEEKBENCH_NAME = "Geekbench 7";
const GEEKBENCH_UNIT = "points";
const GEEKBENCH_TEST_TYPES = { "single-core": "single_core",
                               "multi-core": "multi_core" };
```

`normalizeBenchmarkResults` keeps only records whose `benchmark_name` is
`"Geekbench 7"`, `unit` is `"points"`, and `test_type` is one of the two test
types; if two records map to the same metric it keeps the earliest by `id`
(`isEarlierResult`). The metric keys therefore implicitly mean
*"Geekbench 7 single-core"* and *"Geekbench 7 multi-core"*, but they carry **no
suite dimension of their own**.

The filter is consumed by:
- `App.jsx` (performance panel, comparison panel "Geekbench 7 scores"),
- `comparison.js` (`getPerformanceState`),
- `buildIntelligence.js` (`normalizeBenchmarkResults` → "verified benchmark
  metrics").

## 3. Why removing it would be misleading

If the `benchmark_name === "Geekbench 7"` guard were removed while a second
suite existed, two different suites' `single-core` scores would both map to the
same `single_core` key and the code would silently keep one of them
(arbitrary lowest `id`) — comparing or displaying scores from unrelated
suites as if they were the same measurement. The response contract does carry
`source`, `benchmark_name`, `test_type`, but the *metric model* has no suite
key, so the metadata cannot be used safely without restructuring the metrics
to be suite-scoped (a real UI change), and the current dataset has exactly one
suite, so any suite-scoped UI would present a single fixed choice.

This matches the batch guardrail: *"If generalization would be misleading or
API metadata is insufficient, retain the existing UI filter and document the
precise blocker."* It also satisfies *"do not add UI filters that cannot return
distinct or meaningful results."*

## 4. What the frontend already does well

- It displays the source name for each record
  (`App.jsx`: `sourceName = result?.source?.name || result?.source_name`, shown
  as `Source: …`) and the benchmark name; empty/loading/error states are
  handled by the existing `getPerformanceState` conventions
  (`loading`/`error`/`unavailable`/`partial`/`available`).
- CPU vs GPU identity is inherent to the per-hardware API/load path.

## 5. Exact prerequisites before generalising the UI (dependency)

1. **Data**: at least a second benchmark family must be imported under a clear
   licence (see `final_report.md` licensing section; gaming benchmarks remain
   gated).
2. **Metric model**: `performance.js` must gain a suite dimension so metrics
   are keyed by `(benchmark_name/source, test_type)`, and
   `getBenchmarkComparisonData` / `BENCHMARK_COMPARISON_METRICS` must select a
   suite explicitly instead of assuming Geekbench 7.
3. **API**: use the new optional filters (`source_id`, `benchmark_name`,
   `test_type`) to request a specific suite/metric rather than fetching all
   rows and filtering client-side.
4. **UI**: only then add a suite/metric selector — and only if more than one
   suite actually returns results.

Until (1) exists, generalising (2)–(4) would change no observable behaviour and
would risk mislabeling; it is deferred.

## 6. Files inspected

- `frontend/src/performance.js` — hard filter / metric normalisation.
- `frontend/src/performance.test.js` — existing metric tests.
- `frontend/src/App.jsx` — benchmark loading, performance + comparison panels.
- `frontend/src/comparison.js`, `frontend/src/buildIntelligence.js` — filter
  consumers.
- `frontend/src/api.js` — API base URL helper.