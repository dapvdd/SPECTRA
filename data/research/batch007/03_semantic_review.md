# Batch 007 - Phase 2: Semantic Review

## Findings
- GPU core>boost: 14 cases (mobile/older parts) - possible base/boost naming or mobile boost semantics. Insufficient evidence to auto-correct.
- CPU base>boost: 3 cases - needs source verification.
- System Shared semantics: 341 GPUs marked System Shared; none have memory_gb>0 - consistent.
- Bus width: all stored as integer bits, no bad values detected.
- Clocks/TDPS: no zero/negative values.

## Classification
Most findings are ambiguous. No confirmed defects with strong provenance. Recommend manual review; no automated corrections.
