# Batch 006 - Phase 3: Mapping and Exclusions

## Summary
- All 1879 GPUs currently have memory_bus_width_bits NULL (column just added).
- GPU Ark bus_width used as source (bits). Deterministic corekey matching (ignore leading vendor token), strict 1:1.
- Proposed: 1443 updates. Evidence: 1443 rows. Excluded: 436 (ambiguous/no_match/no_valid_bits). Unmatched: 108.
- Values validated as positive integers in bits (<=4096).

## Notes
- Some SKUs may legitimately not have bus width documented or may be ambiguous across variants; we only accept unambiguous exact corekey matches.
- NULL-only updates; no overwriting existing values.
