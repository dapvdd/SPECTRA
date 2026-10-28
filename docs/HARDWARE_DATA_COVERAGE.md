# SPECTRA Hardware Data Coverage

**Generated**: 2026-10-28
**Source of truth**: local copy of the deployed SQLite DB (`C:\Users\user\spectra-local\data\spectra.db`)

> Coverage is reported as **validated coverage**: a record counts as covered
> only when the relevant value is present and (where relevant) backed by
> provenance/evidence. Row counts alone are never presented as coverage.

---

## 1. Catalog size vs validated coverage

| Dataset | Rows | Truly validated rows | Notes |
|---|---|---:|---|
| hardware (total) | 5,380 | 5,360 | 20 rows have **no** provenance row at all |
| CPU | 3,501 | 3,501 | all have a `cpu_specifications` row |
| GPU | 1,879 | 1,825 | 54 provenance rows are `excluded`/`unmatched` (50 excluded + 4 unmatched) |
| CPU spec rows | 3,501 | 3,501 | field-level |
| GPU spec rows | 1,879 | 1,879 | field-level |
| Benchmark results | 1,040 | 1,040 | all `verified`, all Geekbench 7, all CPU |
| Hardware with ≥1 benchmark | 518 | 518 | only 518 of 5,380 records have any benchmark |
| Sources | 9 | 9 | licence statuses: 3 clear, 4 unknown, 1 restricted, 1 unresolved |
| Provenance rows | 36,946 | — | 34,523 high, 2,361 medium, 60 None, 2 rejected |

**"Comprehensive" never claimed**: 5,380 rows is *breadth of catalog*, not
completeness. Only ~9.6% of records (518) carry a benchmark; several hundred
spec fields are NULL; 20 hardware rows are completely unattributed.

## 2. CPU field coverage (of 3,501 CPU records)

| Field | Missing | Present | Coverage % |
|---|---:|---:|---:|
| cores | 5 | 3,496 | 99.9% |
| threads | 461 | 3,040 | 86.8% |
| base_clock_ghz | 229 | 3,272 | 93.5% |
| boost_clock_ghz | 1,076 | 2,425 | 69.3% |
| tdp_w | 277 | 3,224 | 92.1% |
| process_node_nm | 1,028 | 2,473 | 70.6% |
| socket | 190 | 3,311 | 94.6% |
| architecture (hardware) | — | — | ~95% (see provenance) |

A "fully complete" CPU (all 7 fields present) is **about 2,425 / 3,501 ≈ 69%** —
bounded by the weakest field (boost clock).

## 3. GPU field coverage (of 1,879 GPU records)

| Field | Missing | Present | Coverage % |
|---|---:|---:|---:|
| memory_gb | 341 | 1,538 | 81.9% |
| memory_type | 0 | 1,879 | 100.0% |
| core_clock_mhz | 4 | 1,875 | 99.8% |
| boost_clock_mhz | 755 | 1,124 | 59.8% |
| vram_bandwidth_gbps | 341 | 1,538 | 81.9% |
| memory_bus_width_bits | 436 | 1,443 | 76.8% |
| tdp_w | 204 | 1,675 | 89.1% |
| interface | 1,030 | 849 | 45.2% |
| length_mm | 1,113 | 766 | 40.8% |

GPU physical dimensions and interface are the weakest fields (≈40–45% present).

## 4. Provenance coverage

| Granularity | Verified | Uncertain | Excluded | Unmatched |
|---|---:|---:|---:|---:|
| hardware fields | 3,642 | 0 | 8 | 0 |
| CPU spec fields | 19,515 | 0 | 0 | 0 |
| GPU spec fields | 12,687 | 0 | 50 | 4 |
| benchmark records | 1,040 | 0 | 0 | 0 |

- Hardware with **any** provenance: **5,360 / 5,380 (99.6%)**.
- Benchmark results with provenance: **1,040 / 1,040 (100%)**.
- 20 hardware records have no provenance row — reported as `unattributed`,
  never guessed.

## 5. Source licensing (verified from DB + batch016)

| Source | License status | License | Retrieved |
|---|---:|---:|---|
| PassMark CPU catalog (benchmark-cpus.csv) | restricted | commercial | 2026-10-10 |
| Geekbench Browser - Geekbench 7 CPU | unknown | review needed | — |
| TechPowerUp GPU Database | restricted | commercial | 2026-10-10 |
| GPU Ark GPU specs & benchmarks | clear | CC BY 4.0 | — |
| Wikipedia (English) | clear | CC BY-SA 4.0 | — |
| Intel ARK (via Wayback) | unknown | review needed | — |
| Unknown (artifact) | unresolved | — | — |
| Intel ARK (intel-cpus.csv snapshot) | unknown | review needed | 2026-10-10 |
| AMD product specs (amd-cpus.csv snapshot) | unknown | review needed | 2026-10-10 |

Even for `unknown`/`restricted`-status sources, the data is already in the DB
with explicit provenance; the licence flags are required honesty.

## 6. Benchmark dataset

- **All 1,040 results are Geekbench 7**, split single/multi-core, all CPU.
- No GPU benchmark results — deliberate, documented.

## 7. What is missing entirely (planned categories)

No records for: desktop CPU form factor split, mobile CPUs, RAM, SSDs, HDDs,
motherboards, power supplies, cooling systems, laptop models, monitors.

**Note on the 3,501 "CPU" records**: they include desktop and mobile models and
some server parts (EPYC/Xeon). The catalog currently has no `segment` column,
so it cannot honor the mission constraint "do not confuse laptop GPU and
desktop GPU" at the data layer — only by convention in the importer. Fixing
this is a priority in the audit.
