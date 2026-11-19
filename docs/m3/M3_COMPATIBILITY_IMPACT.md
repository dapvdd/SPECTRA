# M3 Compatibility Impact (Phase 6)

**Date**: 2026-11-16
**Rule contract**: `M2.5-RULES-v1` — unchanged. M3 introduces **zero new rules**
and **zero modified rule semantics**; the engine consumed M3 data through its
existing public functions unchanged.

## 1. Integration evidence

`backend/app/services/test_m3_compatibility_integration.py` (13 tests, all
passing) feeds the seven registered rules records of the exact shape
`publish_batch` stores / `load_build_specifications` loads:

| Scenario | Expected | Result |
|---|---|---|
| DDR5 kit on DDR5 board | COMPATIBLE | ✓ |
| DDR4 kit on DDR5 board | INCOMPATIBLE | ✓ |
| 32 GB kit ≤ 192 GB max | COMPATIBLE | ✓ |
| 4096 GB kit > 192 GB max | INCOMPATIBLE | ✓ |
| 2 modules ≤ 4 slots | COMPATIBLE | ✓ |
| 6 modules > 4 slots | INCOMPATIBLE | ✓ |
| Rated speed above board spec (XMP/EXPO) | never INCOMPATIBLE (no QVL data) | ✓ (generation rule only) |
| NVMe drive on M.2-less board | INCOMPATIBLE | ✓ |
| GPU fit with missing slot data | UNKNOWN | ✓ |
| PSU above TDP reference | **UNKNOWN (advisory)** | ✓ |
| PSU below TDP reference floor | INCOMPATIBLE | ✓ |
| Missing motherboard socket (imported gap) | UNKNOWN | ✓ |
| Missing-data ≠ compatibility (NOT_APPLICABLE separation) | pinned | ✓ |

## 2. Concern separation (mission §8 requirement)

Pinned by `TestSeparationOfConcerns`:

1. **Catalog completeness** — measured by `m3_validation.quality_score`
   (0-100, completeness only).
2. **Field provenance** — `field_provenance` rows per populated field.
3. **Rule applicability** — NOT_APPLICABLE outcomes (e.g. no CPU/GPU for the
   PSU rule) are not compatibility evidence.
4. **Compatibility result** — COMPATIBLE / INCOMPATIBLE / UNKNOWN only, with
   `missing_information` naming every absent field consulted.

## 3. No-false-positive guarantees for imported data

- Imported records with missing critical fields are blocked before PUBLISHED
  (Phase 3 gate) — and even if a field is absent in otherwise-published
  records, the rules return UNKNOWN, never COMPATIBLE (pinned by
  `test_imported_unknown_socket_yields_unknown_not_compatible`).
- PSU adequacy cannot become COMPATIBLE from TDP alone (two-tier policy,
  `PSU_TDP_REFERENCE_FRACTION = 0.3` reference floor; above-floor stays
  UNKNOWN) — pinned.
- BIOS support is not evaluated anywhere (no BIOS data exists in the schema);
  socket match explanations in the engine already state this explicitly.
- GPU fit with missing slot data stays UNKNOWN — pinned.
- Case clearance: no case entity exists; no rule was added (contract
  preserved).

## 4. Regression results

- `python -m pytest backend/app/services -q` → 73 passed (all existing
  compatibility tests + 13 new integration tests).
- Full backend suite: 1342 passed, 2 skipped, 2 deselected (CI-parity flags).

## 5. Conclusion

No false-positive compatibility conclusions are introduced by M3-imported
data. The M2.5 rule contract is intact; imported data exercises the same
rules with the same honest boundaries.
