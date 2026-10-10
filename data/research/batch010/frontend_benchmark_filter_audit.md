# Batch 010 — Frontend Benchmark Filter Readiness Audit

Date: 2026-10-10

## 1. Scope

Determines whether the application can already filter benchmark results by
benchmark suite/source, CPU/GPU identity, metric/score type, or test
configuration — and whether any small, non-speculative UI/API change is
justified now.

## 2. Current behaviour (verified from source)

### Backend
- `GET /hardware/{hardware_id}/benchmarks` (`backend/app/main.py`) returns all
  `benchmark_results` for the hardware via
  `benchmark_service.get_benchmarks_for_hardware`, ordered by `id`. The
  response (`BenchmarkResultResponse`) includes `id`, `hardware_id`,
  `benchmark_name`, `score`, `unit`, `test_type`, `recorded_at`, and a nested
  `source {id, name, url}`.
- **No query-parameter filters** (suite/source/metric/type) exist on the API;
  hardware identity is fixed by the path parameter. The schema stores all
  needed filter dimensions (`benchmark_name`, `test_type`, `unit`,
  `source_id`), so server-side filtering would be trivially possible but is
  not currently exposed.

### Frontend
- `frontend/src/App.jsx` fetches `/hardware/{id}/benchmarks`, validates the
  payload (`validateBenchmarkPayload`), and stores per-hardware benchmark
  states.
- `frontend/src/performance.js` is the single filter point:
  - `GEEKBENCH_NAME = "Geekbench 7"`, `GEEKBENCH_UNIT = "points"`,
    `GEEKBENCH_TEST_TYPES = {"single-core": "single_core",
    "multi-core": "multi_core"}`;
  - `normalizeBenchmarkResults` keeps only records matching those values and
    a finite positive score; everything else is dropped;
  - `getPerformanceState` returns `available`/`partial`/`unavailable` based on
    whether both Geekbench test types are present;
  - `getBenchmarkComparisonData` hard-codes the two Geekbench 7 comparison
    metrics (`BENCHMARK_COMPARISON_METRICS`), and the comparison UI is titled
    "Geekbench 7 scores".
- CPU vs GPU identity: the benchmark API is per-hardware, and the UI loads it
  per catalog item, so CPU vs GPU identity is already inherent to which
  hardware record is shown. There is no client-side suite filter control and
  no resolution/settings notion (the schema has no such column).

## 3. Answers

| Filter dimension | Already available? | How |
|---|---|---|
| Benchmark suite/source | Partially (data level) | Backend returns all + source; frontend hard-filters to Geekbench 7. No user control. |
| CPU or GPU identity | Yes | Per-hardware endpoint + per-item UI. |
| Benchmark metric / score type | Yes (fixed set) | `test_type` single-core/multi-core mapped to two metric keys. |
| Test configuration (resolution, settings, preset) | No | No such column/support exists anywhere; not applicable to Geekbench 7 data. |

## 4. Conclusion and decision

- The **data and schema fully support** source/suite/test-type filtering; the
  frontend already applies a client-side filter (Geekbench 7). The hard-coded
  filter in `performance.js` (and the "Geekbench 7 scores" comparison title)
  would hide any future benchmark source that IS imported — that is a readiness
  limitation worth noting, not a defect against the current dataset.
- Adding a user-facing suite/source filter now is **not justified**: the
  database contains exactly one benchmark family (Geekbench 7), so a filter
  control would always return a single, fixed selection and add UI without
  meaningful results. This matches the task instruction to defer UI rather
  than build speculative functionality.

**No frontend change is made in this batch.** Documented prerequisites before
any future benchmark-source UI:

1. Import/permission of an additional benchmark dataset (e.g. permissioned
   gaming benchmarks) — the data and its licence must exist first.
2. Backend: expose optional query filters on the benchmark endpoint
   (`source_id`, `benchmark_name`, `test_type`) — small, additive, and
   supported by the current schema; do this at the same time as (1).
3. Frontend: lift the Geekbench hard-filter into filterable/parameterised
   selection in `performance.js`, and generalise the comparison title, only
   after (1) and (2).

This keeps the batch scoped to benchmark-provenance and identifier integrity,
with the frontend work correctly deferred behind data + schema.

## 5. Files inspected

- `backend/app/main.py` (`GET /hardware/{id}/benchmarks`)
- `backend/app/services/benchmark_service.py`
- `backend/app/schemas/benchmark.py`
- `frontend/src/App.jsx` (benchmark loading, comparison panels)
- `frontend/src/performance.js` (normalization/filtering)
- `frontend/src/api.js` (API base URL helper)