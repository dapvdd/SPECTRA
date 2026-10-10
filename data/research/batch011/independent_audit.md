# Batch 011 - Independent Audit

Date: 2026-10-10

## Database state (no mutation expected)
- Live SHA-256: `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
- Batch 010 checkpoint SHA-256: `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
- Unchanged from checkpoint: True
- `PRAGMA quick_check`: ok
- `PRAGMA foreign_key_check`: []

## Full-table diff vs checkpoint
- Changed tables: none

## Row counts
- hardware: 5239
- cpu_specifications: 3360
- gpu_specifications: 1879
- benchmark_results: 1040
- external_identifiers: 3575
- sources: 9
- field_provenance: 35849
- build_conversations: 4
- build_messages: 4

## Benchmark results
- Geekbench 7 / multi-core: 520
- Geekbench 7 / single-core: 520

## External identifiers by source
- source 8: 2675
- source 9: 900

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

## Independent filter verification (live data, service path)
- no_filter_count: 2
- no_filter_ids: [1, 2]
- source_filter_count: 2
- name_filter_count: 2
- single_core_count: 1
- multi_core_count: 1
- contradiction_count: 0
- unknown_source_count: 0
- no_duplicates: True
- filters correct: True

## Verdict: PASS
