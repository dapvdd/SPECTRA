# Stage 4 — CPU/GPU Coverage Verification Report

**Tool**: `coverage_verification.py` (read-only, dev DB).
**Dev DB**: `C:\Users\user\spectra-local\data\dev\spectra_dev.db`

## Totals

| Dataset | Rows |
|---|---:|
| hardware | 5380 |
| cpu | 3501 |
| gpu | 1879 |
| cpu_specifications | 3501 |
| gpu_specifications | 1879 |
| benchmark_results | 1040 |

## Gap feasibility (fillable by a clear-licensed source?)

### `cpu_specifications`

| Field | Missing | Fillable | Reason |
|---|---|---:|---|
| cores | 5 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| threads | 461 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| base_clock_ghz | 229 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| boost_clock_ghz | 1076 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| tdp_w | 277 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| process_node_nm | 1028 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |
| socket | 190 | no | no clear-licensed CPU source (CPU sources are unknown/restricted license) - blocked |

### `gpu_specifications`

| Field | Missing | Fillable | Reason |
|---|---|---:|---|
| memory_gb | 341 | yes | clear-licensed adapter covers this field; NULL can be filled where the source has a value |
| memory_type | 0 | no | no clear-licensed adapter maps this field - blocked |
| core_clock_mhz | 4 | no | no clear-licensed adapter maps this field - blocked |
| boost_clock_mhz | 755 | yes | clear-licensed adapter covers this field; NULL can be filled where the source has a value |
| vram_bandwidth_gbps | 341 | no | no clear-licensed adapter maps this field - blocked |
| memory_bus_width_bits | 436 | no | no clear-licensed adapter maps this field - blocked |
| tdp_w | 204 | yes | clear-licensed adapter covers this field; NULL can be filled where the source has a value |
| interface | 1030 | no | no clear-licensed adapter maps this field - blocked |
| length_mm | 1113 | no | no clear-licensed adapter maps this field - blocked |

## Interpretation

- GPU gaps (`boost_clock_mhz`, `tdp_w`, `memory_gb`) are **fillable** by the clear-licensed GPU Ark adapter, but Batch 018 already applied the non-NULL GPU Ark values; remaining NULLs are rows where GPU Ark itself has no value (ark_null) — verified by `data/research/batch017/`. So current GPU NULLs are honest gaps, not recoverable from a clear source we already hold.
- CPU gaps are **blocked on license**: every candidate CPU spec source (Intel ARK, AMD CSV, Geekbench) is unknown/restricted, so none can feed the published catalog until re-approved.
