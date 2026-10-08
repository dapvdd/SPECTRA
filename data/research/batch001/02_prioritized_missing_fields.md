# B. Prioritized Missing-Field Analysis

Which gaps have the largest *practical* impact on SPECTRA's comparison and build
intelligence. Impact = (does the field actually drive a comparison/build signal today?)
× (how often it is missing) × (how much code reads it).

Verified against the codebase (read-only):

- The live comparison logic is the **frontend**: `frontend/src/comparison.js` (7 CPU + 6 GPU
  winner metrics, no weights; each metric counts one win) and `comparisonDecision.js`.
- Governor for missing values in the UI: `comparison.js:148-157` requires `value > 0`;
  NULL → the metric is shown as *unavailable* and excluded from the win tally.
- The **only formula** on a spec field is the listed-TDP sum in
  `frontend/src/buildConfig.js:228-237` (`calculateListedTdpSum`), which returns `NULL`
  if *either* CPU or GPU TDP is missing → the whole power block renders "Not available".
- Build-intelligence "metadata coverage" (`buildIntelligence.js:179-198`) counts
  `architecture` **and** `release_date` together for the metadata signal. Because **all
  CPUs are missing both**, that signal can never become `available` for any CPU.
- Benchmark coverage is CPU-only and Geekbench-7-only (`performance.js:24-29,94-96`).
  The `gaming` performance card and the GPU comparison benchmark panel are structurally
  empty (frontend allow-list; see `07_gaming_benchmark_source_review.md`).
- The backend `comparison_service.compare_cpus` is dead code (no route) and would raise
  `TypeError` on NULL columns; not a live risk today.

## CPU — ranked

| Rank | Field | Missing | Why it matters |
|---|---|---|---|
| 1 | `hardware.architecture` | **0 % populated (3,360)** | Together with release_date it gates CPU metadata "availability" forever; also display value. Zero-cost to fill (family-level fact, first-class sources). |
| 1 | `hardware.release_date` | **0 % populated (3,360)** | Same metadata gate; also a user-facing comparison display row. |
| 2 | `boost_clock_ghz` | 32.0 % (1,076) | 1 of 7 CPU winner metrics; missing on ~1/3 of rows → frequent "unavailable" in comparisons. Note: for no-turbo parts NULL is *correct*. |
| 3 | `tdp_w` | 8.6 % (288) | 1 of 7 winner metrics AND the only field in a formula — one NULL kills the entire build power block. |
| 4 | `process_node_nm` | 30.2 % (1,015; **all 666 AMD**) | Options-weighting/display; drags build coverage even though it never decides a comparison. |
| 5 | `threads` | 13.7 % (461) | 1 of 7 winner metrics. |
| 6 | `base_clock_ghz` | 7.1 % (240) | 1 of 7 winner metrics (cluster = 12th/13th-gen Intel). |
| 7 | `socket` | 3.6 % (122) | Display + coverage only (explicitly forbidden from compatibility claims). |
| — | CPU benchmark coverage | **84.6 % of CPUs have none** | 2 of 7 winner metrics (`single_core`, `multi_core`) unavailable on 2,842 CPUs — the single highest-value expansion, but it is a *benchmark-ingestion* task, not a spec task. |

## GPU — ranked

| Rank | Field | Missing | Why it matters |
|---|---|---|---|
| 1 | `core_clock_mhz` | **59.1 % (1,110)** | 1 of 6 GPU winner metrics; almost always "unavailable" today (only 41 % of GPUs can even participate). Bulk-fillable from the existing raw source (see audit §6). |
| 2 | `tdp_w` | 10.9 % (204) | 1 of 6 winners + the TDP-sum formula. |
| 3 | `memory_gb` | 18.1 % (341) | 1 of 6 winners; also a build-chat fact and card primary spec. Bulk-fillable from raw source. |
| 4 | `vram_bandwidth_gbps` | 18.1 % (341) | 1 of 6 winners. |
| 5 | `boost_clock_mhz` | 40.9 % (769) | 1 of 6 winners; card primary spec row. |
| 6 | `length_mm` | 59.2 % (1,113) | 1 of 6 winners (direction `lower`) — but inherently AIB-model dependent; should often stay NULL. |
| 7 | `interface` | 54.8 % (1,030) | Display + build-coverage only. |
| — | GPU gaming benchmarks | **0 % (0 rows)** | This was the requested special-priority gap. See `07_...md`: no legally clean bulk source found; **not** imported in this batch. |

## Fields SPECTRA's schema cannot store yet (asked for in the brief)

These are real gaps but require a **schema change + code change** (out of scope here — no
DB/application modification allowed):

- CPU: `cache`, `integrated_gpu` (iGPU model) — no columns exist.
- GPU: `memory_bus` (bus width), `cuda_cores` / `stream_processors`, `process_node_nm`,
  `release_date` exists but GPU `architecture` is already 100 %.
- Benchmark model is generic and could accept gaming rows, but `frontend/src/performance.js`
  hard-filters to `Geekbench 7`/`points`/`single|multi-core`, so gaming rows added to the DB
  would currently be stored-but-invisible until frontend changes ship.

## Recommended next steps (for the developer, not done by this batch)

1. Review & apply batch 001 (204 NULL-fill updates, 174 high confidence).
2. Bulk-map the remaining ~1,066 GPU `core_clock_mhz` (and 341 `memory_gb`) from the
   already-approved TechPowerUp raw snapshot, reusing the sprint18b normalizer's
   `parse_memory_gb` unit logic. This would lift GPU core-clock coverage from 41 % → 100 %
   in one reviewed migration.
3. Decide on a CPU benchmark expansion (PassMark already has 2,675 `intel_cpu_id`
   identifiers in `external_identifiers` — an easy join key if `benchmark-cpus.csv` is
   re-acquired with its license checked).
4. Separate ticket: gaming-benchmark ingestion + frontend rendering (see `07_...md`).