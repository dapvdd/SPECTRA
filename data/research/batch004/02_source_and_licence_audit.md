# Batch 004 - Phase 2: Source and Licence Audit

Date: 2026-10-09

## Existing local datasets - inspection
1. data/raw/gpuark-gpu-specs.csv
- README states: license cc-by-4.0, curated by GPU Ark (gpuark.com/datasets)
- Reuse permitted for non-commercial/commercial with attribution per CC BY 4.0.
- Contains fields relevant to batch004: ram (memory size), ram_type (memory type), bus_width, ram_bandwidth (bandwidth). 
- Also contains base_clock/boost_clock. Units vary (ram sometimes MB vs GB per README note; we must normalize carefully).

2. data/raw/gpu_1986-2026.csv (TechPowerUp style)
- Previous audits (batch001, batch002, batch003) found TechPowerUp's terms restrictive for bulk automated reuse; treated as NOT suitable for bulk import unless permission obtained. The snapshot is present locally but reuse permission is not clearly established for this batch's purpose. We do not assume it's pre-approved.
- Contains Top__MEMORY SIZE/TYPE/BUS WIDTH, Memory__* fields including Bandwidth in MB/s/GB/s forms - but licence constraint blocks bulk reuse.

3. Other datasets present (benchmarks etc) - not relevant.

## Sources table context
Existing sources registered: (1) PassMark CPU, (2) Geekbench CPU, (3) TechPowerUp GPU Database (gpu_1986-2026.csv). Registration alone does not guarantee reuse permission for new bulk imports.

## Licence considerations for candidate sources
- GPU Ark CC BY 4.0: usable with attribution. We must record attribution/provenance. Citation format provided.
- TechPowerUp: robots.txt/terms reviewed in prior batches indicate bulk automated extraction and redistribution require permission; not acceptable as source for importing new values in this batch without explicit permission. Reject for bulk enrichment.
- Official vendor docs (NVIDIA/AMD/Intel): public documentation pages have varying terms; scraping may be restricted. For this batch, prefer using existing local datasets with clear licences over fetching new web content. Also batch rules say "verify licence and reuse permissions" - safer to use GPU Ark (clear CC BY 4.0).

## Chosen sources (if any)
Primary candidate: GPU Ark (gpuark-gpu-specs.csv), licence CC BY 4.0. Suitable for extracting VRAM capacity, memory type, bus width, bandwidth if present and mappable.

Secondary: TechPowerUp snapshot - rejected for bulk import due to insufficiently clear reuse licence per batch rules.

## Fields available in GPU Ark
- ram: memory size (value; units inconsistent historically per README - e.g. older MB, newer GB). Must normalize to GB with documented rule.
- ram_type: memory type (GDDR3/GDDR5/HBM etc)
- bus_width: memory bus width in bits (e.g. 128)
- ram_bandwidth: memory bandwidth with units like "25.60 GB/s" (string form in the dataset? need to inspect)

## Blocked fields due to schema
- Memory bus width (bus_width from sources) does not exist as column in gpu_specifications. Cannot store without schema modification - forbidden. Therefore bus_width enrichment is blocked at schema level.

## Assessment
- VRAM capacity (memory_gb), memory type, memory bandwidth (vram_bandwidth_gbps) are eligible targets that exist in schema.
- Memory bus width: eligible semantically but target column missing -> blocked.
- Core clocks: batch002 already did extensive work; remaining NULLs may exist but treat as secondary priority.

## Recommendation
Proceed with GPU Ark (CC BY 4.0) for: memory_gb, memory_type (careful not to overwrite if different), vram_bandwidth_gbps. Do not use TechPowerUp bulk data. Do not attempt schema changes.
