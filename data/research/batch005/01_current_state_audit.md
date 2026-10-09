# Batch 005 - Phase 1: Live Audit

Date: 2026-10-09

## Database
- spectra.db hash (current): acb390e91ef63390afe267b82851dcd2689172ee7f5fd31da11453870292d68d
- Integrity: (to verify in later phases)

## Counts
- GPU hardware (type='gpu'): 1879
- GPU spec rows: 1879 (1:1)

## Clock coverage
- core_clock_mhz: NULL=54, NONNULL=1825, total=1879
- boost_clock_mhz: NULL=769, NONNULL=1110, total=1879

## Distributions
Manufacturers (top 4): NVIDIA 876, AMD 722, Intel 175, ATI 106
System Shared / integrated (memory_type='system shared'): 341

## Existing sources/provenance
- GPU Ark (gpuark-gpu-specs.csv): CC BY 4.0 (local)
- TechPowerUp snapshot (gpu_1986-2026.csv): present locally; previous batches treated as not suitable for bulk import without explicit permission
- Other local datasets as documented previously
