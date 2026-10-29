# Batch 017 — GPU Ark CC BY 4.0 Enrichment

**Date**: 2026-10-28
**Mission**: SPECTRA Operation Data Completeness, Phase 2 (GPU enrichment)
**Source**: GPU Ark GPU specifications & benchmarks dataset
**License**: CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/
**Attribution**: GPU Ark (2026). GPU specifications & benchmarks dataset. https://gpuark.com/datasets/

## Source provenance (verified)

| Property | Value |
|---|---|
| URL | https://gpuark.com/datasets/ |
| Dataset file | `gpuark-gpu-specs.csv` |
| SHA-256 | `bcaba010961cdeca4d2260028d7f27f2c18317e67ffbddec7a09d3dddfa9f734` |
| Retrieved | 2026-10-28 |
| Rows | 13,566 GPU records |
| Size | 3,383,295 bytes |
| License | CC BY 4.0 (confirmed via https://gpuark.com/datasets/) |

License card (translated, confirming CC BY 4.0):
> "Открытый датасет GPU — характеристики 13 566 видеокарт (1999–2025)
> CC BY 4.0 — используйте свободно с атрибуцией на gpuark.com."

## Schema mapping

GPU Ark `bus_interface` → `gpu_specifications.interface`
GPU Ark `bus_width`     → `gpu_specifications.memory_bus_width_bits`

GPU Ark fields not imported (no corresponding column in `gpu_specifications`):
`slug`, `arch_name`, `card_release_date`, `proc_foundry`, `proc_process_size`,
`proc_transistors`, `proc_die_size`, `cores`, `tensor_cores`, `rt_cores`,
`sm_count`, `memory_clock`, `fp16/32/64/bf16/tf32/int8_performance`,
`suggested_psu`, `slot_width`, `power_connectors`, `multi_gpu`,
`api_cuda`, `is_retail_board`, `gpi_value`.

## Validation findings (pre-apply dry-run)

| Finding | Count |
|---|---|
| Total GPU Ark candidates matched to SPECTRA | 993 |
| Valid to apply (non-empty source value) | 965 |
| Invalid: empty `bus_interface` in source | 28 |
| Same-name-to-multiple-interface conflicts | 0 |
| Duplicate hardware_id per field | 0 |

### 28 excluded records (empty `bus_interface` in source)

GPU Ark genuinely has no `bus_interface` for these records. These are
console/APU/SoC/embedded GPUs using custom memory interconnects, not PCIe:

- Wii U GPU, Xbox One/S/X GPU, Xbox Series S/X/S 6nm GPU
- PlayStation 4/4 Pro/4 Slim/5/5 Pro GPU
- Nintendo Switch (20nm/16nm/2) GPU
- Steam Deck / Steam Deck OLED GPU
- Ryzen Z1/Z1 Extreme, Z2/Z2 A/Z2 Extreme/Z2 Go GPU
- Atari VCS 400/800 GPU, Zhongshan Subor Z+ GPU, AeroBox GPU

**None fabricated** — source_value = '' (empty string in source) is a
documented absence, not an inference.

## Applied records

| Field | Applied | Before | After | Delta |
|---|---|---|---|---|
| `interface` | 938 | 849 (45.2%) | 1,787 (95.1%) | +938 |
| `memory_bus_width_bits` | 27 | 1,443 (76.8%) | 1,470 (78.2%) | +27 |

### Interface value distribution (938 records)

| Value | Count | Notes |
|---|---|---|
| IGP | 116 | Integrated GPU — no discrete bus |
| FSB | 19 | Front Side Bus — legacy Intel/AMD |
| PCI | 31 | Conventional PCI |
| QPI | 2 | Intel QuickPath Interconnect (server) |
| Ring Bus | 99 | Intel integrated GPU bus |
| Apple MPX | 1 | Apple MPX expansion module |
| MXM | 3 | Mobile PCI Express Module (generic) |
| MXM-II | 9 | MXM Version 2 |
| MXM-A (3.0) | 52 | MXM Type-A, Version 3.0 |
| MXM-A (3.1) | 1 | MXM Type-A, Version 3.1 |
| MXM-B (3.0) | 89 | MXM Type-B, Version 3.0 |
| MXM-HE | 2 | MXM High-End |
| AGP 2x | 1 | Accelerated Graphics Port 2x |
| AGP 4x | 3 | Accelerated Graphics Port 4x |
| PCIe 1.0 x1 | 1 | PCIe Gen 1 x1 lane |
| PCIe 1.0 x16 | 8 | PCIe Gen 1 x16 lane |
| PCIe 2.0 x1 | 1 | PCIe Gen 2 x1 lane |
| PCIe 2.0 x4 | 3 | PCIe Gen 2 x4 lanes |
| PCIe 2.0 x8 | 2 | PCIe Gen 2 x8 lanes |
| PCIe 2.0 x16 | 97 | PCIe Gen 2 x16 lanes |
| PCIe 3.0 x4 | 8 | PCIe Gen 3 x4 lanes |
| PCIe 3.0 x8 | 113 | PCIe Gen 3 x8 lanes |
| PCIe 3.0 x16 | 140 | PCIe Gen 3 x16 lanes |
| PCIe 4.0 x4 | 18 | PCIe Gen 4 x4 lanes |
| PCIe 4.0 x8 | 53 | PCIe Gen 4 x8 lanes |
| PCIe 4.0 x16 | 57 | PCIe Gen 4 x16 lanes |
| PCIe 5.0 x16 | 9 | PCIe Gen 5 x16 lanes |

### Bus width distribution (27 records — all HBM-equipped data-center GPUs)

| Value | Count | Examples |
|---|---|---|
| 5120.0 bits | 17 | A100 PCIe 40/80 GB, H100 PCIe 80/96 GB, H800 PCIe 80 GB |
| 6016.0 bits | 1 | H100 NVL (special form factor) |
| 6144.0 bits | 3 | DRIVE A100, GRID A100A/B |
| 8192.0 bits | 6 | Radeon Instinct MI250/MI250X, MI300, Data Center GPU Max |

## Conflict resolution

- **NULL-only guard**: Never overwrites an existing non-NULL value.
- **0 interface conflicts** across all 965 records (all GPU Ark values either
  matched existing values or filled NULLs).
- For 938 interface records, the DB value after apply equals the GPU Ark value.

## Provenance

- `source_id = 4` (GPU Ark GPU specifications & benchmarks dataset)
- `batch_no = 18`
- `confidence = medium` (normalized name matching)
- `evidence_status = verified`
- `match_method = normalized_name + vendor_prefix_stripped`
- `license_name = CC BY 4.0`
- `attribution = "GPU Ark (2026). GPU specifications & benchmarks dataset. https://gpuark.com/datasets/"`

## Integrity

- `PRAGMA quick_check`: `ok`
- `PRAGMA foreign_key_check`: 0 violations
- Re-running matcher on post-apply DB: 0 additional classifiable-but-NULL records

## Scripts

| File | Purpose |
|---|---|
| `gpu_ark_fetch.py` | Download and validate GPU Ark CSV |
| `gpu_ark_dryrun.py` | Deterministic matching and dry-run report |
| `batch017_apply.py` | Idempotent transaction-safe apply with provenance |
| `verify_apply.py` | Idempotency, coverage delta, spot-checks |
| `audit_invalid_records.py` | Classify the 28 excluded records |
| `verify_empty_cause.py` | Cross-check CSV source for empty values |
| `diagnose_warnings.py` | Investigate spot-check anomalies |

## Blockers resolved

- GPU `interface` field: was 45.2% covered → now 95.1% covered via GPU Ark
- GPU `memory_bus_width_bits` for data-center GPUs: 76.8% → 78.2%
- GPU Ark was independently fetched, SHA-256 verified, schema cross-checked

## Blockers not resolved (require separate authorization)

- GPU benchmarks: 0 GPU benchmark results (no source meeting all 4 criteria)
- GPU `boost_clock_mhz`: GPU Ark has many NULLs (integrated GPUs lack boost)
  — could be supplemented from other clear-licensed sources
- GPU `length_mm`: not in GPU Ark schema; TechPowerUp is restricted
- GPU `memory_gb` for IGPs: GPU Ark has nulls (unified memory systems)
- CPU spec enrichment: Intel ARK (source #6/#8) has unknown license status
