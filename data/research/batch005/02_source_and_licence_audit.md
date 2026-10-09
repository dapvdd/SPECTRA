# Batch 005 - Phase 2: Source Audit

Date: 2026-10-09

## Sources inspected
1. GPU Ark (data/raw/gpuark-gpu-specs.csv) - CC BY 4.0
- Has base_clock (core) and boost_clock fields in MHz. Used in Batch 002 for core clocks; provenance clear.

2. TechPowerUp snapshot (data/raw/gpu_1986-2026.csv) - restrictive terms per prior audits
- Contains clock fields but reuse not clearly authorized for bulk import. Do not use.

3. Other local sources - none obvious for GPU clocks beyond GPU Ark.

## Assessment
GPU Ark is the best local candidate with clear licence. Must apply same safety rules: deterministic matching, no overwriting non-NULL, no fabricating values, preserve identity. Boost clock exists in source but may not be applicable for all SKUs; only import where documented and safe.

## Chosen source
GPU Ark (CC BY 4.0) as primary candidate for filling remaining NULL core/boost clocks where unambiguous matches exist.
