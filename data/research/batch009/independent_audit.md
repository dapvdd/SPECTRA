# Batch 009 - Independent Audit

Date: 2026-10-10

## Database state
- Pre-load SHA-256: `0a53ba47e2a855e06790a0263611f120c247c82a0969c20edc4280bd92d6a917`
- Post-load SHA-256: `c0e843edece6a2999cf8376a782f1602262b092a6cf5f32cb4bce1763d10c3ce`
- Pre `PRAGMA quick_check`: ok
- Post `PRAGMA quick_check`: ok
- Post `PRAGMA foreign_key_check`: []

## Table count changes (must be additive only)
- `sources`: 7 -> 9
- `field_provenance`: 3382 -> 34809
- Unexpected changes: none

## Data values (must be unchanged)
- Changed data tables: none

## Sources (additive)
- `8` Intel ARK (intel-cpus.csv snapshot) (https://ark.intel.com/)
- `9` AMD product specifications (amd-cpus.csv snapshot) (https://www.amd.com/en/products/specifications/processors)
- Unexpected new sources: none

## Provenance table
- Total rows: 34809
- Distinct identity rows: 34809
- New rows in this load: 31427
- Removed provenance rows: 0
- New batch numbers: ['0']
- New statuses: ['verified']
- Orphan hardware references: 0
- Orphan source references: 0
- Invalid evidence statuses: 0
- Invalid table references: 0

### By evidence status
- excluded: 58
- unmatched: 4
- verified: 34747
### By source
- source 1: 546
- source 3: 12884
- source 4: 2573
- source 5: 757
- source 6: 2
- source 7: 6
- source 8: 16276
- source 9: 1765
### By batch_no
- batch 0: 31427
- batch 1: 210
- batch 2: 1066
- batch 3: 599
- batch 5: 64
- batch 6: 1443

## New-row verification (independent path)
- Cross-checked against reconciliation CSV + live cell value: 31427
- New rows whose live cell value mismatches evidenced value: none
- Verified claims without supporting evidence: none

## Sources
- `1` PassMark CPU benchmark catalog (benchmark-cpus.csv) (https://www.cpubenchmark.net/)
- `2` Geekbench Browser - Geekbench 7 CPU (https://browser.geekbench.com/)
- `3` TechPowerUp GPU Database (gpu_1986-2026.csv) (https://www.techpowerup.com/gpu-specs/)
- `4` GPU Ark GPU specifications & benchmarks dataset (https://gpuark.com/datasets/)
- `5` Wikipedia (English) (https://en.wikipedia.org/)
- `6` Intel ARK (archived via Wayback Machine) (https://ark.intel.com/)
- `7` Unknown (source not documented in artifact) ()
- `8` Intel ARK (intel-cpus.csv snapshot) (https://ark.intel.com/)
- `9` AMD product specifications (amd-cpus.csv snapshot) (https://www.amd.com/en/products/specifications/processors)

## Verdict: PASS
