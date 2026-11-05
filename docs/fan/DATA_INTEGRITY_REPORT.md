# Stage 7 — Data Integrity Drill Report

**Tool**: `data_integrity_verify.py` (read-only, dev DB).
**Target**: `C:\Users\user\spectra-local\data\dev\spectra_dev.db`

**Verdict**: `PASS`

## Quick check

- `quick_check`: `ok` ✓ OK

## Referential integrity

- FK violations: `0` ✓ 0 — PASS

## Row-count floors

| Table | Rows | Minimum | Met? |
|---|---|---:|---:|---|
| hardware | 5380 | 4500 | ✓ |
| sources | 10 | 5 | ✓ |
| benchmark_results | 1040 | 800 | ✓ |
| field_provenance | 39440 | 1000 | ✓ |

## Curated counts (mission-relevant tables)

| Table | Rows |
|---|---:|
| hardware | 5380 |
| cpu_specifications | 3501 |
| gpu_specifications | 1879 |
| benchmark_results | 1040 |
| sources | 10 |
| field_provenance | 39440 |
| external_identifiers | 3575 |

## Schema presence

- Complete: `Yes`
- Tables: benchmark_results, build_conversations, build_messages, cpu_specifications, external_identifiers, field_provenance, gpu_specifications, hardware...

## Safety note

This drill is **read-only**: the target file is never written. A `FileNotFoundError` is raised if the path does not exist — the drill refuses to create an empty database by connecting to a missing path.