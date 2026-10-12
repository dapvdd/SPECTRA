# 01 — Current-state audit (pre-change baseline)

Generated from the live database before any Batch 015 write, with the
reproducible script `_snapshot.py` (raw output: `_db_snapshot.json`).

## Environment

| Item | Value |
| --- | --- |
| Git `main` | `819018b` `feat(data): expand modern CPU catalog coverage` |
| Database | `data/spectra.db` (git-ignored `*.db`) |
| SHA-256 (before) | `401A3974586265804ED55F07A998ADFAFBC3DD7EB46F2F226E3A32E3EABD9035` |
| Size | 51,191,808 bytes |
| `PRAGMA integrity_check` | ok |
| `PRAGMA foreign_key_check` | 0 violations |

## Record counts (baseline)

| Table | Rows |
| --- | ---: |
| `hardware` | 5,380 |
| → `CPU` | 3,501 |
| → `GPU` | 1,879 |
| `cpu_specifications` | 3,501 |
| `gpu_specifications` | 1,879 |
| `benchmark_results` | 1,040 |
| `external_identifiers` | 3,575 |
| `field_provenance` | 36,946 |
| → specification (`benchmark_result_id IS NULL`) | 35,906 |
| → benchmark (`benchmark_result_id IS NOT NULL`) | 1,040 |
| `sources` | 9 |
| `build_conversations` | 5 |
| `build_messages` | 10 |

## Provenance baseline

- **Evidence status:** verified 36,884 · excluded 58 · unmatched 4.
- **By batch:** 0 → 32,467 (base import) plus batches 1, 2, 3, 5, 6 and 14
  (1,097 rows).
- **By source (`rows` / distinct hardware / distinct benchmarks):**
  - 8 · 16,276 / 2,659 / 0
  - 3 · 12,884 / 1,879 / 0
  - 4 · 2,573 / 1,666 / 0
  - 5 · 1,854 / 713 / 0
  - 9 · 1,765 / 404 / 0
  - 2 · 1,040 / 518 / 1,040
  - 1 · 546 / 306 / 0
  - 7 · 6 / 6 / 0
  - 6 · 2 / 2 / 0
- **Licence coverage:** `license_name` NULL 32,519 · `CC BY 4.0` 2,573 ·
  `CC BY-SA 4.0` 1,854.
- **Attribution fields:** `source_reference` NULL 264 · `attribution` NULL
  32,473.

## Benchmarks baseline

- 1,040 rows, all `Geekbench 7` (520 single-core + 520 multi-core), unit
  `points`, all attributed to source 2 (Geekbench Browser).
- Every benchmark row has benchmark provenance (1,040 of 1,040).

## Coverage gaps to report honestly

| Gap | Count |
| --- | ---: |
| CPUs with specifications but no specification provenance | 24 |
| GPUs with specifications but no specification provenance | 0 |
| Hardware rows with no provenance at all | 20 |
| Provenance rows referencing a missing source | 0 |
| Benchmarks without provenance | 0 |

## `sources` schema (baseline — insufficient for licence status)

```
id    INTEGER PRIMARY KEY
name  VARCHAR(200) NOT NULL
url   VARCHAR(500) NOT NULL
```

The registry stored only a name and URL. Redistribution status, publisher and
attribution obligations were not representable, and much of the provenance
carried no `license_name` at all. This is the motivation for the additive
change described in `03_design_and_migration.md`.
