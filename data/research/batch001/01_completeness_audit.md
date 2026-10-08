# A. Data Completeness Audit

Read-only audit of `data/spectra.db` (2026-10-08). All figures produced by direct SQL
(`mode=ro`); "present" = non-NULL and non-blank.

## 1. Dataset shape

| Table | Rows |
|---|---|
| hardware | 5,239 (CPU 3,360 / GPU 1,879) |
| cpu_specifications | 3,360 (1 per CPU, no orphans) |
| gpu_specifications | 1,879 (1 per GPU, no orphans) |
| benchmark_results | 1,040 |
| sources | 3 |
| external_identifiers | 3,575 |

Manufacturers — CPU: Intel 2,694 / AMD 666. GPU: NVIDIA 876 / ATI 106 / AMD (Radeon, 722) + Intel iGPUs (175) fill the remainder.

## 2. `hardware` metadata

| Field | Present | Rate | CPU | GPU |
|---|---|---|---|---|
| name / manufacturer / type | 5,239 | 100 % | ✓ | ✓ |
| `release_date` | 837 | 16.0 % | **0 / 3,360 (0 %)** | 837 / 1,879 (44.6 %) |
| `architecture` | 1,879 | 35.9 % | **0 / 3,360 (0 %)** | 1,879 / 1,879 (100 %) |

Two findings dominate the whole audit:

- **No CPU in the database has a `release_date` or an `architecture`.**
- GPU `release_date` is missing on 1,042 cards (mostly pre-2015 boards that were imported from sources other than the TechPowerUp snapshot).

## 3. CPU specification fields (3,360 rows)

| Field | Present | Rate | Missing |
|---|---|---|---|
| `cores` | 3,355 | 99.9 % | 5 |
| `socket` | 3,238 | 96.4 % | 122 |
| `base_clock_ghz` | 3,120 | 92.9 % | 240 |
| `tdp_w` | 3,072 | 91.4 % | 288 |
| `threads` | 2,899 | 86.3 % | 461 |
| `process_node_nm` | 2,345 | 69.8 % | 1,015 |
| `boost_clock_ghz` | 2,284 | 68.0 % | 1,076 |

Notable structural patterns:

- **Every AMD CPU (666/666) has `process_node_nm = NULL`** — all 2,345 populated rows are Intel parts (2,345 of 2,694 Intel CPUs; 349 Intel parts are missing it too). For CPUs the field is effectively Intel-only today.
- **12th/13th-gen Intel desktop parts are missing `base_clock_ghz` and `tdp_w`** (the source that populated older Intel rows stopped exposing these columns for newer generations). Examples: i5-12400F, i5-13400F, i9-13900K/i9-13900KS all have NULL base clock and NULL TDP while their boost clocks (4.4 / 4.6 / 5.8 / 6.0 GHz) are populated.
- `boost_clock_ghz` NULLs (1,076): Intel 999, AMD 77. The Intel cluster is dominated by parts that genuinely have **no turbo boost** (e.g. locked low-end chips such as Core i3-8100, Pentium G4560) plus rows the source left incomplete; the AMD cluster is mostly low-power/OEM and very old parts (Phenom/Turion-era).
- `threads` NULLs (461): Intel 399, AMD 62. `cores` is missing on only 5 rows (e.g. `1045T`, `2800+`).

## 4. GPU specification fields (1,879 rows)

| Field | Present | Rate | Missing |
|---|---|---|---|
| `memory_type` | 1,879 | 100 % | 0 |
| `tdp_w` | 1,675 | 89.1 % | 204 |
| `memory_gb` | 1,538 | 81.9 % | 341 |
| `vram_bandwidth_gbps` | 1,538 | 81.9 % | 341 |
| `boost_clock_mhz` | 1,110 | 59.1 % | 769 |
| `interface` | 849 | 45.2 % | 1,030 |
| `core_clock_mhz` | 769 | 40.9 % | **1,110** |
| `length_mm` | 766 | 40.8 % | 1,113 |

Root cause of the `core_clock_mhz` gap (verified during this audit): the importer mapped
TechPowerUp's column `Clock Speeds__GPU Clock` to `core_clock_mhz`. In the current raw
snapshot that column is **empty for every modern card**, while the adjacent
`Clock Speeds__Base Clock` column is populated for **all 1,110 rows that are missing
`core_clock_mhz`**. Where a card does have `core_clock_mhz` today (802 of 899
name-matched rows), it equals the raw file's `GPU Clock` value — i.e. the two columns are
the same concept ("reference/base clock") exposed under different names across the source
file generations.

## 5. Benchmark coverage

| Metric | Value |
|---|---|
| benchmark rows | 1,040 |
| Distinct benchmark / unit / test_type tuples | 1: `Geekbench 7` / `points` / `single-core` (520 rows) and `multi-core` (520 rows) |
| CPUs with ≥ 1 benchmark | 518 / 3,360 = **15.4 %** |
| GPUs with ≥ 1 benchmark | **0 / 1,879 = 0 %** |
| Gaming benchmarks of any kind | **0 rows** |

The UI's Performance tab shows four cards (`cpu`, `single_core`, `multi_core`, `gaming`);
only `single_core`/`multi_core` can ever be produced, so two cards are permanently
"NO DATA" and the GPU comparison benchmark panel is a hardcoded empty state.

## 6. Fill analysis against the already-approved raw source

`data/raw/gpu_1986-2026.csv` (TechPowerUp snapshot, the project's existing `source_id 3`):

| Missing field | Rows missing | Fillable from raw snapshot |
|---|---|---|
| `core_clock_mhz` | 1,110 | **1,110 (100 %)** — from `Clock Speeds__Base Clock` |
| `memory_gb` | 341 | **341 (100 %)** — needs MB→GB normalization |
| `release_date` (GPU) | 1,042 | 40 |
| `interface` | 1,030 | 0 |
| `length_mm` | 1,113 | 0 (reference-card length is simply not in the snapshot for these rows) |

This means the largest single GPU gap is **not a research problem but a mapping problem**.
Batch 001 still researched 44 popular cards manually (with per-value sources and NVIDIA
official cross-checks) as required, but the developer may prefer a separate, reviewed bulk
migration for the remaining ~1,066 cards using the same column mapping.

## 7. Existing data spot-checks performed during this audit

- 10 popular CPUs compared field-by-field against the Wikipedia desktop tables used for
  research (base, boost, TDP, cores, threads): **no contradictions found**; the only
  differences were the intended NULLs (12th/13th-gen base/TDP).
- 16 NVIDIA GPUs: official NVIDIA product-page base *and* boost clocks vs the stored/raw
  values: **all match within GHz-rounding (≤ 10 MHz)**.
- 97 of 899 name-matched GPUs have a stored `core_clock_mhz` that matches *neither* raw
  column (older IGP/mobile rows such as `Radeon HD 6310 IGP`). This is a pre-existing
  inconsistency outside batch 001's scope — flagged in `06_risks_and_open_questions.md`.

## 8. Source inventory

| source_id | Name | Used for |
|---|---|---|
| 1 | PassMark CPU benchmark catalog | external_identifiers (3,175 ids), not used in this batch |
| 2 | Geekbench Browser – Geekbench 7 | 1,040 benchmark rows |
| 3 | TechPowerUp GPU Database (`gpu_1986-2026.csv`) | GPU specs incl. every `core_clock_mhz` today and all 44 proposed values |
