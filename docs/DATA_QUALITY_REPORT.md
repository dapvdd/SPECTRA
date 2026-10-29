# SPECTRA Data Quality Report (Batch 018 — GPU Ark enrichment)

**Date**: 2026-10-29
**Scope**: Post-enrichment data-quality verification for the GPU Ark (CC BY 4.0)
Batch 018 enrichment, applied to the isolated staging database.

## 1. Quality checks run

| Check | Test | Result |
|---|---|---|
| Referential integrity | `PRAGMA foreign_key_check` | 0 violations ✅ |
| Database integrity | `PRAGMA quick_check` | `ok` ✅ |
| Duplicate hardware identities | `SELECT name, manufacturer ... GROUP BY HAVING COUNT(*)>1` | 0 duplicates ✅ |
| Existing-value preservation | NULL-only guard — re-check each target field | 0 overwrites ✅ |
| Idempotency | Re-run matcher on post-apply DB | 0 new records ✅ |
| Source attribution | 965 `field_provenance` rows with source_id=4, batch_no=18 | all present ✅ |
| Empty/None values | Filter applied records | 0 empty applied ✅ |
| Ambiguous matching | Same name → multiple distinct values | 0 ✅ |
| Out-of-range values | Interface strings validated against known set; bus width sanity | 0 ✅ |

## 2. Field-level completeness

Measured on staging DB (`gpu_specifications`, n=1,879).

| Field | Before (filled/total, %) | After (filled/total, %) |
|---|---|---|
| `interface` | 849 / 1,879 (45.2%) | 1,787 / 1,879 (95.1%) |
| `memory_bus_width_bits` | 1,443 / 1,879 (76.8%) | 1,470 / 1,879 (78.2%) |
| `memory_gb` | 1,538 / 1,879 (81.9%) | unchanged (no safe fill) |
| `memory_type` | 1,879 / 1,879 (100%) | unchanged |
| `core_clock_mhz` | 1,875 / 1,879 (99.8%) | unchanged |
| `boost_clock_mhz` | 1,124 / 1,879 (59.8%) | unchanged (GPU Ark lacks values) |
| `tdp_w` | 1,675 / 1,879 (89.1%) | unchanged |
| `length_mm` | 766 / 1,879 (40.8%) | unchanged (not in GPU Ark schema) |
| `vram_bandwidth_gbps` | 1,538 / 1,879 (81.9%) | unchanged |

## 3. Records rejected / quarantined

**28 records rejected** (not applied), all for the *single, exactly-verified* cause:
GPU Ark's `bus_interface` is empty in the source CSV. These are console / APU / SoC /
embedded GPUs with unified-memory interconnects (Nintendo Switch, Wii U, Xbox One/S/X,
Series S/X, PlayStation 4/4 Pro/4 Slim/5/5 Pro, Steam Deck, Atari VCS 400/800,
Zhongshan Subor Z+, AeroBox, Ryzen Z1/Z2 family and AI Z2 Extreme).

No value was invented; the empty source value was treated as an absence, not a zero.

## 4. Interface terminology integrity

The destination `interface` column now holds the **source-vendor's own
terminology** recorded verbatim (preserved, not re-mapped). Values include:
`PCIe 1.0/2.0/3.0/4.0/5.0` (×1/×4/×8/×16), `AGP 2x/4x`, `MXM`/`MXM-A/B/HE/II`,
`IGP`, `Ring Bus`, `FSB`, `PCI`, `QPI`, `Apple MPX`.

Semantics are intentionally preserved as distinct interface concepts — a
`Ring Bus` or `IGP` is not conflated with a socketed `PCIe` slot.

## 5. Regression against baseline

- 703 backend tests passed, 2 skipped (no regression).
- 29 segment-classifier tests passed.
- No schema change introduced; only `gpu_specifications.interface` and
  `gpu_specifications.memory_bus_width_bits` were updated (NULL → value).
- All existing non-NULL values preserved (0 overwrite).

## 6. Confidence model

- **Match method**: normalized full-name equality with chip-vendor prefix stripped,
  plus vendor compatibility (AMD↔ATI interchangeable; exact otherwise).
- **Confidence**: `medium` — conservative name-based match; corroborated by
  the fact that no same-name record maps to multiple interface values.
- **Evidence status**: `verified` (value taken verbatim from GPU Ark, attributed).

## 7. Known remaining gaps (unchanged, no fabrication)

- `length_mm`: 1,113 missing (GPU Ark has no such field; TechPowerUp is restricted).
- `boost_clock_mhz`: 755 missing (GPU Ark has many NULLs, esp. integrated GPUs).
- `memory_gb`: 341 missing (mostly IGPs / unified memory — left NULL, no fake VRAM).
