# Batch 005 - Phase 3: Mapping and Exclusions

## Summary
- Targets with NULL clocks: 823 GPUs (core_clock_mhz NULL=54, boost_clock_mhz NULL=769; no GPU has both NULL)
- Used GPU Ark (CC BY 4.0) with deterministic matching. Matched ignoring leading vendor token (corekey) to handle name differences while keeping strict 1:1 match requirement.
- Proposed safe updates: 64 total (50 core_clock_mhz, 14 boost_clock_mhz). Evidence rows: 64. Patch entries: 64 distinct hardware updates (some could theoretically fill multiple fields, but in this set each proposed update fills the specific NULL field for that hardware).
- Excluded: 759 (ambiguous matches or no safe values in source). Unmatched: 108.

## Classification of remaining NULLs
- core_clock_mhz remaining NULL after applying safe proposals: 54 - 50 = 4 (if all applied). But we only propose 50 of those 54; remaining 4 have no unambiguous safe source match.
- boost_clock_mhz remaining NULL: 769 - 14 = 755. Many boost clocks may legitimately be unspecified; we only filled where source had explicit boost value and match was unambiguous.

## Matching rules applied
- Deterministic corekey normalization (strip vendor prefix). Single unambiguous match only. No fuzzy matching.
- NULL-only updates; never overwrite existing non-NULL values. No fabrication/interpolation.
- Preserve hardware identity. Validate units (MHz). Sanity check values 0 < v <= 50000.
- Source licence verified (CC BY 4.0). No gaming benchmark data.

## Evidence
- 03_evidence_table.csv contains 64 evidence rows with full provenance (hardware_id, source, source_record_id, source field/value, normalized value, match method, URL, confidence, caveats).
- 05_database_patch.json contains 64 update entries (each hardware gets specific field updates).
