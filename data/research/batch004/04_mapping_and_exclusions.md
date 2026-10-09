# Batch 004 - Phase 3: Mapping and Exclusions

## Summary
- Targets with NULL memory_gb or vram_bandwidth_gbps: 341 (all GPU type; all have memory_type 'System Shared')
- Among discrete GPUs (memory_type != 'System Shared'), 0 have NULL memory_gb or bandwidth
- GPU Ark (CC BY 4.0) reviewed; no safe matches to fill discrete VRAM for shared-memory IGPs

## Method
- Deterministic normalized name matching against GPU Ark
- Only accept unambiguous single matches; skip ambiguous (>1). Strip suffixes cautiously to avoid false positives.
- Normalize VRAM: if year < 2018, treat values < 256 as MB (div by 1024); if year >= 2018 and < 256 treat as GB. Also handle values >= 256 appropriately per era. Normalize bandwidth by extracting numeric GB/s value.
- Safety: never fill discrete capacity when source indicates shared/system memory; NULL-only updates; no overwrites.

## Results
- Proposed updates: 0
- Evidence rows: 0
- Excluded: 341 (reasons: source indicates shared memory or no safe discrete match)
- Unmatched: 0
- Bus width: blocked (no column in schema; cannot modify schema per rules)

## Evidence/Patch
- 03_evidence_table.csv has header only
- 05_database_patch.json is empty array []
