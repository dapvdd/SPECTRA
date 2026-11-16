# M3 Validation Rules (Phase 3 — normative reference)

**Date**: 2026-11-16
**Implementation**: `backend/app/importers/m3_validation.py`
**Tests**: `backend/app/importers/test_m3_validation.py` (20 tests)

## 1. Unit semantics (never conflated)

| Quantity | Stored as | Validation |
|---|---|---|
| RAM speed | `ram_specifications.speed_mhz` | Must be a **transfer rate** (MT/s); sane range 800-12,000. Values like 6 or 6,000,000 fail (clock-rate or typo confusion). The column name is a documented historical misnomer — sources quote MT/s and the validator enforces MT/s semantics. |
| Storage sequential throughput | `read_mb_s` / `write_mb_s` | Must be **MB/s**; sane range 40-12,500. A 14,000 value (PCIe 5.0 Gb/s transcribed as MB/s) fails. |
| PSU wattage | `psu_specifications.wattage` | **Rated output power** (never a TDP claim); sane range 100-8,000 W. |
| PCIe generation | `storage_specifications.interface` | Free vocabulary string ("PCIe 4.0 x4"); **never** treated as a physical-connector compatibility statement by any rule. |
| TDP | `cpu_specifications.tdp_w` / `gpu_specifications.tdp_w` | Listed TDP is a manufacturer rating, not measured power — the PSU rule already treats it as advisory (M2.5 semantics, unchanged). |

## 2. Range checks

Inclusive sane ranges per field (see `_RANGES` in the implementation):

- RAM: capacity 1-2048 GB, speed 800-12,000 MT/s, modules 1-8, voltage 1.0-2.0 V
- Storage: capacity 8-131,072 GB, read/write 40-12,500 / 20-12,500 MB/s
- Motherboard: ram_slots 1-16, max_ram_gb 2-8,192, m2_slots 0-12, sata_ports 0-16, pcie_slots 0-12
- PSU: wattage 100-8,000 W, pcie_8pin_count 0-12, pcie_12vhpwr 0-6

## 3. Cross-field consistency

- **RAM kit consistency**: `capacity_gb % modules == 0` (a 2×16 kit is 32 GB;
  33 GB / 2 modules fails).
- **Motherboard DIMM sanity**: `max_ram_gb / ram_slots ≤ 256` (no 512 GB
  desktop DIMMs exist).

## 4. Missing-data classification

- **Critical** (blocks APPROVED): RAM {ddr_generation, capacity_gb,
  speed_mhz, modules}; STORAGE {storage_type, capacity_gb, interface};
  MOTHERBOARD {socket, form_factor}; PSU {wattage, efficiency_rating}.
- **Optional** (absent stays NULL, listed as warnings): all remaining spec
  columns per category.
- Absent optional values are never invented and never inferred.

## 5. Source conflict detection

`detect_conflicts(records)`: records sharing a `canonical_key` but differing
on any spec field produce `Conflict(key, field, {source: value})` entries.
Conflicts are **never auto-merged** and block publication while unresolved
(`no_blocking_conflict` requirement). Resolution is human, via SUPERSEDED.

## 6. Duplicate detection

`identity.canonical.duplicate_candidates(keyed_rows)`: groups of ≥2 rows with
identical canonical keys are duplicate candidates feeding the conflict
pipeline. Combined with the partial unique index (migration v4), duplicates
cannot silently enter the catalog.

## 7. Quality scoring (deterministic)

`quality_score(type, record)` ∈ 0-100: critical fields weigh 80 % (evenly
split), optional fields 20 %. Identical inputs → identical scores. The score
measures **completeness only** — it is never displayed as a compatibility
guarantee and never substitutes for the compatibility engine.

## 8. Fail-closed gate

`validate_record(type, record)` → `ValidationOutcome(passed, blockers,
warnings, quality_score)`. `passed=False` excludes the record from the
approved publication set. Blockers: unit/range failures, cross-field
failures, missing critical fields, unresolved conflicts, unconfirmed
identity. Gate 3 requirement satisfied.
