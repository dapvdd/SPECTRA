# Stage 5 — Workload Evidence Report

**Tool**: `workload_evidence.py` (read-only, dev DB).
**Scope**: how many hardware rows actually carry the evidence each
workload needs (benchmark family, key specs, verified provenance).

## Totals

| Dataset | Rows |
|---|---:|
| hardware | 5380 |
| cpu | 3501 |
| gpu | 1879 |
| benchmark_results | 1040 |

## Per workload evidence coverage

### CPU

| workload | total | benchmark_family | with_benchmark | spec_ok | provenance | unrated_boundary |
|---|---:|---:|---:|---:|---:|---:|
| gaming | 3501 | multi-core | 518 | 2851 | 3493 |  |
| workstation | 3501 | multi-core | 518 | 2851 | 3493 |  |
| productivity | 3501 | single-core | 518 | 2851 | 3493 |  |
| content_creation | 3501 | multi-core | 518 | 2851 | 3493 |  |
| ai_ml | 3501 | None | 0 | 2851 | 3493 | yes |

### GPU

| workload | total | benchmark_family | with_benchmark | spec_ok | provenance | unrated_boundary |
|---|---:|---:|---:|---:|---:|---:|
| gaming | 1879 | multi-core | 0 | 1535 | 1879 |  |
| workstation | 1879 | multi-core | 0 | 1535 | 1879 |  |
| productivity | 1879 | single-core | 0 | 1535 | 1879 |  |
| content_creation | 1879 | multi-core | 0 | 1535 | 1879 |  |
| ai_ml | 1879 | None | 0 | 1535 | 1879 | yes |

## Interpretation

- **CPU**: 518 of 3,501 (14.8%) have multi-core/single-core benchmark evidence, so gaming/workstation/productivity/content fall back to spec-based (2851 of 3501 have spec evidence). ai_ml is unrated for every CPU (no supported family).
- **GPU**: 0 benchmark rows -> 0% benchmark evidence across every workload; all are spec-based. ai_ml is unrated for every GPU.
- The ai_ml unrated boundary is *honest and consistent*: 0 of 0 AI/ML benchmark-eligible rows can ever be benchmark-driven because no supported family exists in the dataset.