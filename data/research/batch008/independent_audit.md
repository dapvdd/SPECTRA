# Batch 008 - Independent Audit

Date: 2026-10-09

## Database state
- Pre-migration SHA-256: `858a67256853a486af580ac8e5d5c193b4d1c97875b89f0f6fce28df0b2bc39c`
- Post-migration SHA-256: `0a53ba47e2a855e06790a0263611f120c247c82a0969c20edc4280bd92d6a917`
- Pre `PRAGMA quick_check`: ok
- Post `PRAGMA quick_check`: ok
- Post `PRAGMA foreign_key_check`: []

## Table count changes (must be additive only)
- `sources`: 3 -> 7
- `field_provenance`: None -> 3382
- Unexpected changes: none

## Specification values
- Changed values: none
- Unpermitted columns: none

## Provenance table
- Total rows: 3382
- Distinct identity rows: 3382
- Orphan hardware references: 0
- Invalid evidence statuses: 0

### By evidence status
- excluded: 58
- unmatched: 4
- verified: 3320

### By table
- cpu_specifications: 74
- gpu_specifications: 2617
- hardware: 691

## Sources
- `1` PassMark CPU benchmark catalog (benchmark-cpus.csv) (https://www.cpubenchmark.net/)
- `2` Geekbench Browser - Geekbench 7 CPU (https://browser.geekbench.com/)
- `3` TechPowerUp GPU Database (gpu_1986-2026.csv) (https://www.techpowerup.com/gpu-specs/)
- `4` GPU Ark GPU specifications & benchmarks dataset (https://gpuark.com/datasets/)
- `5` Wikipedia (English) (https://en.wikipedia.org/)
- `6` Intel ARK (archived via Wayback Machine) (https://ark.intel.com/)
- `7` Unknown (source not documented in artifact) ()

## Verdict: PASS
