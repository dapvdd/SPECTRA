# M3 Evidence — Phase 6 compatibility integration (2026-11-16)

## TDD cycle
- RED: `backend/app/services/test_m3_compatibility_integration.py` written
  first; 3 failed against M3-shaped PSU build dict (the rule expects
  `{"cpu": {...}, "gpu": {...}}` build shape) and missing_information field
  name — fixed by aligning the tests to the real rule/service contracts
  (rule signatures unchanged).
- GREEN: 13/13 pass.
- REGRESSION: `python -m pytest backend/app/services -q` → 73 passed.

## Boundary verification performed (rule contract intact, zero rule changes)
- generation match/mismatch → COMPATIBLE/INCOMPATIBLE
- capacity within/over max → COMPATIBLE/INCOMPATIBLE
- module count vs slots → COMPATIBLE/INCOMPATIBLE
- rated speed above board spec → never INCOMPATIBLE (XMP/EXPO boundary)
- NVMe on M.2-less board → INCOMPATIBLE
- PSU above TDP reference → UNKNOWN (advisory; never COMPATIBLE)
- PSU below reference floor → INCOMPATIBLE
- missing socket on imported record → UNKNOWN (never false positive)
- NOT_APPLICABLE is not compatibility evidence

## Full-suite state at this point
- Full backend (CI-parity flags): 1342 passed, 2 skipped, 2 deselected.

## Rule version
- RULES_VERSION remains `M2.5-RULES-v1`; no new rules registered; no rule
  semantics modified. M3_COMPATIBILITY_IMPACT.md documents the full matrix.
