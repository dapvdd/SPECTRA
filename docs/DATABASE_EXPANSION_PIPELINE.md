# SPECTRA Database Expansion Pipeline

**Generated**: 2026-10-28
**Scope**: Phase 2 is **deferred** per the selected strategy. This document
describes:
1. The proven pipeline (CPU/GPU) as reference architecture.
2. A prioritized backlog for improving the existing CPU/GPU catalog.
3. A design blueprint for new categories (RAM, SSD, HDD, MB, PSU, cooling,
   laptops, monitors), ready to implement when data is sourced.

> Rules that apply to all future ingestion:
> - Never invent product specifications, benchmark scores, prices, or citations.
> - Never confuse laptop GPU performance with desktop GPU performance.
> - Never assume products sharing a marketing name have identical configurations.
> - Respect `robots.txt`, API terms, and rate limits of every source.
> - Every ingested value requires a `field_provenance` row before insertion.
> - Every source requires a `sources` entry with `license_status` set
>   before ingestion (never import from a source whose licence is unresolved).

---

## 1. Reference: proven CPU/GPU ingestion pipeline

The existing pipeline (documented across `data/research/batch001..016`) follows
this sequence:

```
RAW SOURCE ARTIFACT
    │
    ▼
PARSER  (wikitext tables → structured rows)
    │
    ▼
NORMALIZER (name, units, whitespace, manufacturer)
    │
    ▼
VALIDATOR (value-range checks, type checks, duplicate detection)
    │
    ▼
CANDIDATE INVENTORY  (batchNNN/03_candidate_inventory.csv)
    │
    ▼
EVIDENCE TABLE  (batchNNN/04_evidence_table.csv — every candidate + source)
    │
    ▼
MAPPING & EXCLUSIONS  (batchNNN/04_mapping_and_exclusions.md)
    │
    ▼
DATABASE PATCH  (batchNNN/05_database_patch.json — dry-run)
    │
    ▼
INDEPENDENT AUDIT  (batchNNN/*_independent_audit.md — verifies no data
                    corruption, no provenance shortcut, no scope creep)
    │
    ▼
APPLY  (batchNNN/apply_batchNNN.py — idempotent, INSERT OR IGNORE / UPDATE)
    │
    ▼
POST-APPLY VERIFICATION  (counts, integrity_check, foreign_key_check)
```

Key properties:
- **Batch isolation**: each batch is a complete self-contained directory; no
  batch depends on artifacts of another batch.
- **Independent audit**: a separate script re-derives expected state from raw
  source evidence rather than trusting the patch's own report.
- **Idempotent**: re-running apply is safe (uses `INSERT OR IGNORE` / upsert by
  hardware+source+identifier).
- **Evidence preserved**: `sources/*.txt` files hold raw source dumps (Wikitext
  tables, CSV rows) so provenance can be re-derived.
- **Provenance-first**: every patch record has a corresponding `field_provenance`
  row before the hardware row is considered "present".

## 2. Backlog: improve existing CPU/GPU catalog

The DB audit revealed actionable gaps. These are addressable without new source
categories:

### 2.1 CPU: fill boost_clock_ghz gaps (1,076 missing, 69.3% coverage)

**Priority**: high
**Approach**: Use Intel ARK (source #6/#8, Wayback) and AMD product specs
(source #9) to fill known gaps. Each missing value needs an evidence row.
**Constraints**: licence is `unknown` for Intel ARK; must not be upgraded to
`clear` without explicit review.

### 2.2 CPU: fill process_node_nm gaps (1,028 missing, 70.6% coverage)

**Priority**: medium
**Approach**: AMD ARK / Intel ARK for known process nodes; architecture column
can be used as a proxy (Zen 4 = 5nm, Raptor Lake = Intel 7). Document
architecture→process_node mapping as an explicit inference assumption in the
provenance row (`match_method="architecture_inference"`).

### 2.3 GPU: fill interface gaps (1,030 missing, 45.2% coverage)  ✅ DONE (Batch 018)

**Status**: Completed 2026-10-29. GPU Ark (`bus_interface`) filled 938 of the
1,030 gaps via deterministic normalized-name matching; `interface` now 95.1%
covered. 28 remaining gaps are console/APU/embedded GPUs where GPU Ark has no
bus_interface (none fabricated). Scripts: `data/research/batch017/`; provenance
source_id=4, batch_no=18.

### 2.4 GPU: fill length_mm gaps (1,113 missing, 40.8% coverage)

**Priority**: medium
**Approach**: TechPowerUp (source #3, `restricted`) and GPU Ark (source #4,
`clear`) both have physical dimensions. Document the restriction in
`source.terms_notes`.
**Note**: GPU Ark's `gpuark-gpu-specs.csv` does **not** provide `length_mm`
(verified against the CSV schema in batch017); only TechPowerUp (restricted)
has it. Remains open.

### 2.5 CPU: fill threads gaps (461 missing, 86.8% coverage)

**Priority**: low
**Approach**: many older Intel parts (pre-HyperThreading, Atom, Celeron); also
some server Xeons. Document those as `HT=unknown` rather than `HT=false` unless
confirmed from source.

### 2.6 Add segment/form-factor column to hardware  ✅ DONE (Phase B)

**Status**: Completed 2026-10-28. Implementation:
- `backend/app/migrations/add_hardware_segment.py`: additive `ALTER TABLE`
  (additive, idempotent; creates `hardware.segment` with CHECK constraint)
- `data/research/segment_classifier.py`: deterministic rule-based classifier
  (no external fetch; derives from manufacturer product naming conventions)
- `backend/app/migrations/backfill_segment.py`: idempotent backfill with
  provenance tracking (applies to local copy only; never touches production DB)
- `data/research/test_segment_classifier.py`: 29 unit tests, all passing

**Classification logic** (deterministic, auditable — 15 distinct rules):
| Priority | Check | Result |
|---|---|---|
| 1st | Explicit "Mobile / Laptop / Mobility / Mobile Processor" | mobile |
| 1st | NVIDIA `GeForce GTX/RTX NNNM` (single M = mobile GeForce) | mobile |
| 1st | NVIDIA `Max-Q / Max-Q` (thin-mobile suffix) | mobile |
| 1st | NVIDIA `GeForce MX450/550…` | mobile |
| 1st | NVIDIA `NVS NNNM` (NVS is mobile only) | mobile |
| 1st | NVIDIA `RTX NNN A-Ada` (Ada laptop variant) | mobile |
| 1st | Intel `Arc A370M / A730M…` (M-suffix Arc) | mobile |
| 1st | AMD `Mobility Radeon` | mobile |
| 1st | AMD `FirePro Mxxxx / WxxxM` | mobile |
| 1st | AMD `Radeon RX/R NNNM` / `R5 M230` | mobile |
| 1st | AMD `Radeon Pro NNNxM / Vega NNM` | mobile |
| 1st | CPU suffix: `H/HX/HK/U/HS/E` (Ryzen + Intel) | mobile |
| 1st | CPU suffix: `M` (standard mobile, all vendors) | mobile |
| 1st | CPU suffix: `P` — REFUSED (ambiguous: `6402P` desktop, `1240P` mobile) | NULL |
| 2nd | NVIDIA `Tesla / T / A100 / H100 / GB200…` | server |
| 2nd | Intel `Xeon` / AMD `EPYC` | server |
| 2nd | AMD `Instinct MI/MX/M300…` | server |
| 2nd | AMD `FirePro Sxxxx / Dxxxx` (compute rack GPU) | server |
| 3rd | NVIDIA `Quadro` / `NVS` / `RTX A…` / `RTX NNNN` | workstation |
| 3rd | AMD/ATI `FirePro` (non-mobile) | workstation |
| 3rd | AMD/ATI `Radeon Pro WX…` / `Arc Pro` | workstation |
| 3rd | Intel CPU whose name embeds "Radeon Pro" (Kaby Lake-G) — REFUSED | NULL |
| REFUSE | Bare `GeForce RTX/GTX NNN` (no suffix) | NULL |
| REFUSE | Bare `M+digits` without family context (M2000: Quadro vs FirePro vs Tesla) | NULL |
| REFUSE | Intel `HD/UHD/Iris Graphics` without explicit "mobile" | NULL |
| REFUSE | Any Apple Silicon | NULL |

**Result**: 2,494 / 5,380 classified (46.3%). 2,886 remain NULL (honest unknown).

**Integrity**: zero overrides (additive-only on newly-added column); every classified
record has exactly one segment provenance row (source #10); zero conflicts;
zero duplicate provenance rows; re-running classifier on classified records produces
zero new classifications (idempotence verified).

**Source for this batch**: "Derived from manufacturer product naming conventions"
(source #10, `license_status=clear`). The classification is grounded in each
vendor's published naming convention, which is public. A token that carries a
different meaning across families is deliberately returned NULL rather than guessed.

**Safety**: all writes go to local staging copy only; never touches production DB
or david-lab server.

### 2.7 External GPU benchmark integration

**Priority**: deferred (requires a source meeting all constraints from batch010)
**Note**: the batch010 research (`data/research/batch010/source_permission_research.md`)
identified that no candidate source met all licensing, provenance, accessibility,
and reproducibility requirements simultaneously. Future integration should only
proceed when a source satisfies all four.

## 3. Blueprint: new hardware categories

The schema extension plan follows the same proven pattern (additive, with
provenance). Each new category requires:

1. A `hardware.type = "RAM" | "SSD" | ...` entry (reuse `hardware` identity table).
2. A new `ram_specifications` / `ssd_specifications` / etc. table.
3. A provenance entry for every field.
4. An independent audit verifying no collision with existing hardware names.
5. A frontend update: `HARDWARE_TYPES` constant + catalog filter + detail view
   + comparison metrics.

### 3.1 RAM

**Data model suggestion** (additive, no schema changes to existing tables):

```
hardware: manufacturer, type="RAM", name (e.g. "Kingston FURY DDR5-5600 32GB")
ram_specifications:
  capacity_gb          — total kit capacity
  modules_count        — sticks in the kit (e.g. 2×16 GB)
  module_capacity_gb   — per stick
  speed_mhz            — XMP/EXPO rated speed
  latency_cl           — CAS latency (e.g. CL36)
  voltage_v            — XMP voltage
  type                 — DDR5 / DDR4 / DDR3 / LPDDR5 / etc.
  ecc                  — boolean
 Registered/Unbuffered — boolean
  form_factor          — DIMM / SODIMM
  height_mm            — for case clearance
  heat_spreader        — boolean
```

**Source candidates**:
- Manufacturer product pages (Kingston, Corsair, G.Skill, Crucial — all public
  product catalogs with machine-readable specs, respect robots.txt, no API key
  needed for public pages).
- PCPartPicker (public, terms允许 non-commercial research; scrape robots.txt
  compliant sections, do not use API without key).
- Wikipedia DDR standards (for standards specs — clearly licensed).
- NotebookCheck for SODIMM/LPDDR real-world data (respect rate limits).
- **Constraint**: do not import MSRP/current prices (ephemeral, often stale).

### 3.2 SSD

**Data model suggestion**:

```
ssd_specifications:
  capacity_gb              — user-available capacity
  type                     — NVMe / SATA / SATAIII
  form_factor              — 2280 M.2 / 2.5" / U.2 / AIC
  interface                — PCIe 4.0 x4 / SATA 6 Gb/s / etc.
  nand_type                — TLC / QLC / PLC (may be unknown for some models)
  sequential_read_mbps     — rated sequential read
  sequential_write_mbps    — rated sequential write
  random_read_iops         — rated random read
  random_write_iops        — rated random write
  tbw                     — terabytes written endurance
  warranty_years           — warranty period
  power_idle_w            — idle power
  power_active_w          — active write power
  dimensions_mm            — L×W×H for form-factor validation
  controller               — optional, for brand transparency
```

**Source candidates**: same manufacturer pages + AnandTech/Tom's Hardware
reviews for real-world performance. Do not use UserBenchmark (licence unclear,
data quality contested).

### 3.3 Motherboard

**Data model suggestion**:

```
mb_specifications:
  socket                 — AM5 / LGA1700 / AM4 / etc.
  chipset                — B650 / Z790 / X670E / etc.
  form_factor            — ATX / mATX / ITX / E-ATX
  ram_type               — DDR5 / DDR4
  ram_slots              — number of DIMM slots
  ram_capacity_max_gb    — maximum supported memory
  ram_speed_max_mhz      — XMP/EXPO maximum supported
  pcie_slots             — count + generation per slot
  m2_slots               — M.2 slot count
  sata_ports             — SATA III port count
  usb_20gbs_ports        — USB-C 20Gbps port count
  usb_10gbs_ports        — USB-A/C 10Gbps count
  audio_codec            — Realtek ALC / etc.
  ethernet_speed_gbps    — 2.5G / 5G / 10G
  wifi                   — boolean or standard (Wi-Fi 6E / Wi-Fi 7)
  tdp_w                  — chipset TDP (not total system)
  length_mm              — PCB length for case clearance
  width_mm               — PCB width
  vrm_phases             — approximate VRM quality indicator
  bios_chip              — flash recovery method
```

**Source candidates**: manufacturer ARK/产品规格 pages (Intel ARK, AMD.com,
ASUS ROG, MSI, Gigabyte) — publicly accessible, respecting rate limits.

### 3.4 Power Supply

**Data model suggestion**:

```
psu_specifications:
  wattage_w              — rated continuous output
  efficiency_rating      — 80+ Bronze / Gold / Platinum / Titanium
  modular                — full / semi / non-modular
  length_mm              — PSU length for case clearance
  fan_size_mm            — fan diameter
  atx_version            — ATX 3.0 / ATX 2.x / SFX
  pcie_16pin_12v2        — native 12VHPWR / 12V-2×6 present
  protections            — OVP / OCP / SCP / OPP / OTP / NLO (flags)
  warranty_years         — warranty period
  weight_g               — weight for case compatibility
```

**Source candidates**: manufacturer product pages; JonnyGuru reviews
(for real load testing); Cybenetics efficiency certifications
(public ETA rating database — clearly licensed).

### 3.5 CPU Cooling

**Data model suggestion**:

```
cooler_specifications:
  type                   — tower_air / top_blower / aio_liquid / passively_cooled
  socket_compatibility    — JSON array: ["AM5", "LGA1700", "LGA1200", ...]
  tdp_support_w          — maximum TDP supported
  height_mm              — for ITX/small case clearance
  fan_size_mm            — primary fan diameter
  fan_rpm_min            — minimum rpm
  fan_rpm_max            — maximum rpm
  noise_level_dba        — at max rpm (from specs, not from reviews)
  radiator_size_mm       — for AIO: radiator length (240/280/360/420mm)
  weight_g               — for CPU socket stress
```

**Source candidates**: Noctua specifications (public), be quiet! product pages,
Arctic product pages. All publicly accessible, robots.txt compliant.

### 3.6 Laptop Models (entire system, not just CPU/GPU)

**Data model**: the most complex category. Rather than a single record per
laptop, consider a `laptop_system` table linked to `hardware`:

```
laptop_system:
  id, hardware_id (to the GPU or the system name)
  screen_size_inches     — display diagonal
  screen_resolution      — e.g. 1920×1080 / 2560×1600
  screen_refresh_hz      — e.g. 60 / 120 / 144 / 240
  panel_type             — IPS / OLED / TN / MiniLED (may be unknown)
  ram_std_gb             — standard/bought config
  ram_max_gb             — maximum upgradeable
  storage                — primary storage type + capacity
  battery_whr             — battery capacity
  weight_kg              — as-configured weight
  thickness_mm           — chassis thickness
  chassis_material       — aluminum / plastic / magnesium (may be unknown)
  webcam_mp              — webcam resolution
  port_complement        — ports available (structured flags)
  bios_locked            — whether BIOS lock prevents RAM upgrades
```

**Source candidates**: NotebookCheck (detailed, review-based; respect rate limits;
check robots.txt); manufacturer spec sheets. Do not cross-mix performance data
from different laptop models of the same GPU (the mission's "don't confuse laptop
and desktop GPU" applies here with extra force).

### 3.7 Monitors

**Data model suggestion**:

```
monitor_specifications:
  panel_type             — IPS / VA / TN / OLED / MiniLED
  size_inches            — diagonal
  resolution             — e.g. 3840×2160
  refresh_hz             — maximum refresh rate
  response_time_ms       — GtG or MPRT
  hdr_standard           — HDR400 / HDR600 / HDR1000 / Dolby Vision / none
  color_space            — sRGB / DCI-P3 coverage %
  brightness_cd_m2       — typical or peak brightness
  contrast_ratio         — static contrast (may be unknown for OLED)
  ports                  — HDMI 2.1 / DP 1.4 / USB-C / etc. (structured flags)
  adjustable_stand        — height/tilt/pivot/rotate
  vesa_mm                — VESA mounting pattern
  power_consumption_w    — typical consumption
  dimensions_mm          — W×H×D for desk clearance
  weight_kg              — with stand
  speakers               — boolean or rated watts
```

**Source candidates**: DisplaySpecifications.com (public product database,
robots.txt compliant); RTINGS.com reviews (clearly licensed); manufacturer
specification pages.

## 4. Implementation checklist for any new category

- [ ] Draft schema: add a `hardware` row with `type`, then a spec table.
- [ ] Research source licensing; add a `sources` row with `license_status`.
- [ ] Fetch source respecting `robots.txt` and rate limits.
- [ ] Store raw source dumps in `data/research/batchNNN/sources/`.
- [ ] Run normalizer/validator on raw data.
- [ ] Build evidence table.
- [ ] Write independent audit.
- [ ] Apply patch with `INSERT OR IGNORE` idempotency.
- [ ] Add provenance rows for every field.
- [ ] Update frontend: `HARDWARE_TYPES`, filter, detail view, comparison.
- [ ] Add frontend tests.
- [ ] Run full backend test suite.
- [ ] Verify `PRAGMA integrity_check` passes.
- [ ] Measure and record validated coverage statistics.

## 5. Sources that should NOT be used without explicit re-review

| Source | Reason to re-review |
|---|---|
| UserBenchmark | Licence disputed; data quality contested in hardware community |
| PassMark (bulk CSV) | `restricted` licence; re-confirm before any new use |
| Any source without an accessible `robots.txt` review | Compliance obligation |

## 6. Phased expansion plan (recommended execution order)

**Phase A** (1 session): add `segment` column, backfill from manufacturer pages;
fix CPU boost clock gaps from Intel ARK + AMD specs; fix GPU interface gaps from
GPU Ark. No new schema.

**Phase B** (1 session): new `ram_specifications` model + first RAM import from
manufacturer pages (Kingston/Corsair/Crucial product catalogs). Frontend RAM
view + comparison.

**Phase C** (1 session): new `ssd_specifications` model + first SSD import.
Frontend SSD view + comparison.

**Phase D** (1 session): new `mb_specifications` model + motherboard import.

**Phase E** (1 session): `psu_specifications`, `cooler_specifications`.

**Phase F** (1 session): laptop_system + monitor.

Each phase follows the batch audit pattern and ends with independent audit.
