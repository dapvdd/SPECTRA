# SPECTRA Data Source Registry

**Generated**: 2026-10-29
**Maintained for**: Operation SPECTRA — Data Completeness
**Conventions**: A source is only used for bulk ingestion once its license status is
`clear` and provenance/attribution obligations are recorded. `unknown`/`restricted`
sources may be used for manual reference only.

## Source registry

| ID | Source | Canonical URL | License | Status | Retrieval | Notes |
|---|---|---|---|---|---|---|
| 1 | PassMark CPU benchmark catalog | — | commercial | **restricted** | 2026-10-10 | Bulk reuse requires permission; reference only |
| 2 | Geekbench Browser — Geekbench 7 CPU | — | review needed | **unknown** | — | Benchmarks present in DB with provenance |
| 3 | TechPowerUp GPU Database (`gpu_1986-2026.csv`) | techpowerup.com | commercial/restricted | **restricted** | 2026-10-10 | Bulk automated reuse requires permission |
| 4 | **GPU Ark GPU specifications & benchmarks** | https://gpuark.com/datasets/ | **CC BY 4.0** | **clear** ✅ | **2026-10-28** | Used for Batch 018 enrichment |
| 5 | Wikipedia (English) | en.wikipedia.org | CC BY-SA 4.0 | clear | — | |
| 6 | Intel ARK (via Wayback) | ark.intel.com | review needed | unknown | — | |
| 7 | Unknown (artifact not documented) | — | — | unresolved | — | Legacy placeholder |
| 8 | Intel ARK (`intel-cpus.csv` snapshot) | ark.intel.com | review needed | unknown | 2026-10-10 | |
| 9 | AMD product specs (`amd-cpus.csv` snapshot) | amd.com | review needed | unknown | 2026-10-10 | |
| 10 | Derived manufacturer naming conventions | n/a (internal classifier) | n/a | clear | 2026-10-28 | Segment classification; no external fetch |

## GPU Ark (source #4) — full registry record

| Property | Value |
|---|---|
| Name | GPU Ark GPU specifications & benchmarks dataset |
| Canonical URL | https://gpuark.com/datasets/ |
| Dataset file | `gpuark-gpu-specs.csv` |
| **SHA-256** | `bcaba010961cdeca4d2260028d7f27f2c18317e67ffbddec7a09d3dddfa9f734` |
| Size | 3,383,295 bytes |
| Rows | 13,566 GPU records |
| **Retrieval date** | 2026-10-28 |
| **License** | CC BY 4.0 (`cc-by-4.0`; confirmed live at dataset card, 2026-05-25 update) |
| License URL | https://creativecommons.org/licenses/by/4.0/ |
| **Attribution required** | "GPU Ark (2026). GPU specifications & benchmarks dataset. https://gpuark.com/datasets/" |
| Allowed usage | Use freely with attribution (CC BY 4.0); no share-alike |
| Redistribution | Permitted with attribution |
| Refresh mechanism | Dataset page states "обновлено 2026-05-25" (updated); poll `https://gpuark.com/datasets/` and re-verify SHA at each refresh |

### Available fields (GPU Ark schema, verified from CSV header)

`id`, `name`, `slug`, `vendor`, `manufacturer`, `arch_name`, `card_release_date`,
`proc_foundry`, `proc_process_size`, `proc_transistors`, `proc_die_size`, `cores`,
`tensor_cores`, `rt_cores`, `sm_count`, `base_clock`, `boost_clock`,
`memory_clock`, `ram`, `ram_type`, `bus_width`, `bus_interface`, `ram_bandwidth`,
`fp16/fp32/fp64/bf16/tf32/int8_performance`, `tdp`, `suggested_psu`, `slot_width`,
`power_connectors`, `multi_gpu`, `api_cuda`, `is_retail_board`, `gpi_value`

### Units & normalization rules (per dataset card)

- **ram**: stored in MB for pre-2018 cards (value ≥ 256 → MB), GB for newer.
  Batch 018 normalizes `ram_gb = value / 1024` when `value ≥ 256`, else `value`.
- **clocks / tdp / bus_width / bandwidth**: numeric (MHz / W / bits / GB/s).

### Data-quality warnings (per dataset card, verified)

- `vendor` is tagged for only ~2,360 of 13,566 cards (nvd/amd/int); the rest are
  OEM variants without chip-vendor tag. → Matching must not rely solely on vendor.
- `ram` unit inconsistency for old cards (MB vs GB).
- `fp16/bf16/int8` are sparse and not directly comparable across vendors
  (NVIDIA Ampere+ tensor numbers often shown with sparsity ×2).
- `card_release_date`: filter 1998..2025 (isolated artifacts).
- **`bus_interface` is empty for ~52 rows** (console/APU/embedded GPUs with
  unified memory) — no value to import; do not fabricate.

### SPECTRA mapping (Batch 018)

| GPU Ark field | SPECTRA target | Applied | Notes |
|---|---|---|---|
| `bus_interface` | `gpu_specifications.interface` | 938 | NULL-only guard; console/embedded empty values quarantined |
| `bus_width` | `gpu_specifications.memory_bus_width_bits` | 27 | data-center HBM GPUs |

### Priority & conflict rules

1. GPU Ark is preferred over TechPowerUp for fields both cover when the field is
   NULL in SPECTRA, because GPU Ark's license is `clear`.
2. A GPU Ark value only ever fills a NULL (never overwrites a non-NULL value).
3. `vendor` mismatch between GPU Ark and SPECTRA hard-excludes a candidate.
   AMD/ATI are treated as interchangeable vendors (same chip lineage).
4. Interface strings are stored verbatim (PCIe/AGP/MXM/IGP/Ring Bus/FSB)
   — they are preserved source terminology, not re-mapped to a narrow
   "PCIe" taxonomy.
