# Batch 004 - Phase 1: Live Database Audit

Date: 2026-10-09

## Database
- DB file: data/spectra.db (950272 bytes)
- SQLite integrity: (will verify via quick_check in later phases)

## Tables (selected)
- hardware (5239 rows total)
- hardware.type='GPU': 1879
- gpu_specifications: 1879 rows (1:1 with GPU hardware)
- cpu_specifications: 1279 rows
- sources: 3
- external_identifiers: 3575
- benchmark_results: present

## GPU specifications schema (gpu_specifications)
Columns (from PRAGMA table_info):
1. id INTEGER PK
2. hardware_id INTEGER UNIQUE FK -> hardware(id)
3. memory_gb FLOAT (NULL allowed)
4. memory_type VARCHAR(50) (NULL allowed)
5. core_clock_mhz FLOAT (NULL allowed)
6. boost_clock_mhz FLOAT (NULL allowed)
7. vram_bandwidth_gbps FLOAT (NULL allowed)
8. tdp_w FLOAT (NULL allowed)
9. interface VARCHAR(50) (NULL allowed)
10. length_mm FLOAT (NULL allowed)

## Memory-related fields (as they exist)
- memory_gb: NULL=341, NONNULL=1538 (total 1879)
- memory_type: NULL=0, NONNULL=1879 (all non-NULL; many are "System Shared" for IGPs)
- vram_bandwidth_gbps: NULL=341, NONNULL=1538

## Bus width / bandwidth
- Memory bus width: NOT present as a column in gpu_specifications. Schema does not include bus width field.
- Memory bandwidth: represented as vram_bandwidth_gbps (FLOAT). Existing coverage 1538/1879 non-NULL.

## Core clock coverage
- core_clock_mhz: NULL=54
- boost_clock_mhz: NULL=769

## External identifiers
- total 3575; types: intel_cpu_id (2675), product_id_boxed (215), product_id_mpk (65), product_id_tray (620)
- No obvious GPU-specific external identifier types present.

## Existing local datasets (provenance)
- data/raw/gpu_1986-2026.csv (TechPowerUp style)
- data/raw/gpuark-gpu-specs.csv (CC BY 4.0 per README; gpuark.com)
- data/raw/gpuark-benchmarks.csv
- data/raw/README.md states GPU Ark specs CC BY 4.0
- Previous batches referenced TechPowerUp snapshot.

## Sources table
1. PassMark CPU benchmark catalog
2. Geekbench Browser - Geekbench 7 CPU  
3. TechPowerUp GPU Database (gpu_1986-2026.csv)

## Observations
- Priority fields: VRAM capacity (memory_gb exists), memory type (exists), memory bus width (MISSING from schema - blocked), memory bandwidth (vram_bandwidth_gbps exists), core clocks (secondary).
- Cannot add bus width without schema modification - forbidden. Report as blocked.
- Many NULL capacity/bandwidth cases have memory_type 'System Shared' (IGP/shared). Do not fill with discrete VRAM.
