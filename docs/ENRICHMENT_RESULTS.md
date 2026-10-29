# SPECTRA Enrichment Results (Batch 018 — GPU Ark CC BY 4.0)

**Date**: 2026-10-29
**Phase**: Phase 2 / Phase 7 evidence for Operation Data Completeness

## 1. Bottom line

Batch 018 enriched SPECTRA GPU specifications from the GPU Ark dataset
(CC BY 4.0, source_id=4) **on the isolated staging database only**.

**965 records enriched with verified values, 0 overwrites, 0 conflicts.**

## 2. Numbers (verified, reproducible)

| Metric | Value |
|---|---|
| Candidates generated | **993** |
| **Invalid candidates (excluded)** | **28** — all `interface` with empty `bus_interface` in GPU Ark |
| **Valid & applied** | **965** |
| — `gpu_specifications.interface` | **938** |
| — `gpu_specifications.memory_bus_width_bits` | **27** |
| Conflicts (GPU Ark value present but differs from existing DB value) | **0** |
| Duplicate hardware_id per field | 0 |
| Overwrites (existing non-NULL changed) | 0 |

## 3. The 28 excluded (all face the SAME cause)

All 28 invalid rows are **identical cause**: GPU Ark's `bus_interface` is the empty
string in the source CSV for these records. They are all **console / APU / SoC /
embedded** GPUs using unified-memory (UMA) or custom memory interconnects:

- Nintendo Switch (20nm / 16nm / 2), Wii U, Xbox One / S / X / Series S / Series X /
  Series X 6nm, PlayStation 4 / 4 Pro / 4 Slim / 5 / 5 Pro, Steam Deck /
  Steam Deck OLED, Atari VCS 400 / 800, Zhongshan Subor Z+, AeroBox,
  Ryzen Z1, Z1 Extreme, Z2, Z2 A, Z2 Extreme, Z2 Go, Ryzen AI Z2 Extreme

**None fabricated, none converted to 0.**

## 4. Coverage before → after (GPU, n=1,879)

| GPU field | Before | After | Delta | Before % | After % |
|---|---|---|---|---|---|
| `interface` | 849 | 1,787 | **+938** | 45.2% | **95.1%** |
| `memory_bus_width_bits` | 1,443 | 1,470 | **+27** | 76.8% | **78.2%** |

## 5. Source & provenance evidence

- Source: GPU Ark, CC BY 4.0, sha256 `bcaba01096…f734`, fetched 2026-10-28.
- Provenance: 965 `field_provenance` rows (source_id=4, batch_no=18, `confidence=medium`,
  `evidence_status=verified`, `license_name='CC BY 4.0'`, attribution recorded).
- `sources.retrieved_on` set to `2026-10-28` for source #4.

## 6. Integrity & idempotency

- `PRAGMA quick_check` → `ok`
- `PRAGMA foreign_key_check` → 0 violations
- **Idempotent**: re-running the matcher after apply yields **0 new** records.

## 7. Tests

| Suite | Result |
|---|---|
| Backend backend suite | 703 passed, 2 skipped |
| Segment classifier | 29 passed |
| NULL-only guard (no overwrite) | 0 overwrites |
