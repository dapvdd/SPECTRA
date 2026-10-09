# Batch 008 - Provenance Inventory

Date: 2026-10-09

This inventory maps every research/evidence artifact from batches 001-006 to
the data models, sources and database changes they relate to. It is the
basis for the provenance gap analysis and the field-level provenance
implementation.

## 1. Data models and tables relevant to provenance

| Table | Purpose | Provenance relevance |
|---|---|---|
| `hardware` | Hardware identity rows (5,239: 3,360 CPU + 1,879 GPU) | target of enrichment fields `release_date`, `architecture` |
| `cpu_specifications` | 3,360 CPU spec rows, one per CPU hardware row | target of `cores, threads, base_clock_ghz, boost_clock_ghz, tdp_w, process_node_nm, socket` |
| `gpu_specifications` | 1,879 GPU spec rows | target of `memory_gb, memory_type, core_clock_mhz, boost_clock_mhz, vram_bandwidth_gbps, memory_bus_width_bits, tdp_w, interface, length_mm` |
| `benchmark_results` | 1,040 CPU benchmark results | linked to `sources` via `source_id` only; no field-level provenance |
| `sources` | Source registry (3 rows pre-Batch 008: PassMark, Geekbench, TechPowerUp) | identity only: `name`, `url`; no license, access date or attribution columns |
| `external_identifiers` | 3,575 hardware↔source external IDs (e.g. AMD tray product IDs from PassMark) | links hardware to a source but records an identifier, not a value's provenance |
| `build_conversations` / `build_messages` | application state | not provenance-related |

**Pre-Batch 008 finding:** no table persisted field-level provenance. A spec
value's source existed only inside research artifacts on disk.

## 2. Evidence artifacts per batch

### Batch 001 (`data/research/batch001/`)
- `04_evidence_table.csv` - 204 evidence rows: `hardware_id`, `hardware_name`,
  `hardware_type`, `table`, `field`, `current_value`, `researched_value`,
  `source_name`, `source_url`, `confidence`, `notes`.
- `05_database_patch.json` - 204 updates each with `table`, `hardware_id`,
  `column`, `new_value`, `guard`, `source`, `source_url`, `confidence`,
  `applied_status: applied`; plus 6 `deliberately_excluded` records.
- `apply_results.json` - 204 applied.
- `sources/` - local extracts of every cited page (Wikipedia table extracts,
  NVIDIA cross-check values, archived ARK values) with no per-page access date.
- Reconciles to the live DB: **204/204 verified**, **6 excluded**, 0 uncertain.

### Batch 002 (`data/research/batch002/`)
- `02_mapping_results.csv` - full GPU Ark mapping results.
- `04_database_patch.json` - 1,012 `updates` (`table`,
  `gpu_specifications.core_clock_mhz`, `hardware_id`, `new_value`, `source`,
  `source_record_id`, `source_field`, `source_value`, `source_unit`,
  `source_url`, `confidence`, `match_method`) for GPU base clocks; plus
  **50 `excluded`** (`status: ambiguous` with reasons) and **4 `unmatched`**
  (no GPU Ark row).
- Reconciles: **1,012/1,012 verified**, **50 excluded**, **4 unmatched**.

### Batch 003 (`data/research/batch003/`)
- `02_source_and_licence_audit.md` - documents Wikipedia CC BY-SA 4.0 as used
  source; documents the Zen+ vs Zen 2 mislabel correction.
- `sources/provenance.json` - per-article URL, access date `2026-10-09`,
  licence `CC BY-SA 4.0`, table counts for 8 microarchitecture articles.
- `03_evidence_table.csv` - 597+ evidence rows incl. `source_reference`
  (extract file + `TABLE n`).
- `05_database_patch.json` - 597 `updates` (architecture, release_date, AMD
  process node) + 2 `excluded` (Kaby Lake collision, rejected confidence).
- Reconciles: **597/597 verified**, **2 excluded**.

### Batch 004 (`data/research/batch004/`)
- `02_source_and_licence_audit.md` - GPU Ark bus-width target identified but
  **blocked at schema level** (no `memory_bus_width_bits` column existed).
- `03_evidence_table.csv` / `05_database_patch.json` - empty (0 applicable
  evidence rows).

### Batch 005 (`data/research/batch005/`)
- `03_evidence_table.csv` - 64 evidence rows (50 `core_clock_mhz`,
  14 `boost_clock_mhz`) from GPU Ark with `source_record_id`, `source_value`,
  `normalized_value`, `match_method`, `confidence` (medium),
  `source_url`, `caveats`.
- Reconciles: **64/64 verified**.

### Batch 006 (`data/research/batch006/`)
- `01_schema_migration_audit.md`, `06_preflight_and_migration_test.md` -
  documented the additive `memory_bus_width_bits INTEGER` migration.
- `03_evidence_table.csv` - 1,443 evidence rows (bus width, bits) from
  GPU Ark.
- Reconciles: **1,443/1,443 verified**.

## 3. Sources, URLs, licences and confidence

| Source | Evidence URL(s) | Licence | Access date(s) | Used by | Confidence |
|---|---|---|---|---|---|
| Wikipedia articles / lists | per-article `https://en.wikipedia.org/wiki/...` | CC BY-SA 4.0 (documented in batch 001/003 audits) | 2026-10-09 recorded only in batch003 `provenance.json`; other batches: **unknown** | batches 001, 003 | high (batch003), high/medium (batch001) |
| GPU Ark dataset | `https://gpuark.com/datasets/` | CC BY 4.0 (per `data/raw/README.md` and live re-verification in batch 002) | **not recorded per evidence row** | batches 002, 005, 006 | high (002), medium (005/006) |
| TechPowerUp GPU DB snapshot | `https://www.techpowerup.com/gpu-specs/` | **no bulk reuse grant** (robots.txt re-verified batch 002; bulk dataset creation prohibited) | unknown | batch 001 only (44 GPU core clocks; 16/44 cross-checked vs NVIDIA official pages) | high/medium |
| Intel ARK (archived via Wayback Machine) | `https://ark.intel.com/` | **no reuse grant documented**; accessed only as archived cross-check | unknown | batch 001 only (2 process_node_nm) | high |
| PassMark / Geekbench (existing source rows 1-2) | registry URLs | **unknown / not documented** | n/a | base import only; not used by any enrichment batch | n/a |

## 4. Relationship of evidence artifacts to applied database changes

Verified totals after reconciliation against the current database (SHA-256
`0a53ba47...`):

| Batch | Evidence rows | Verified | Excluded | Unmatched | Uncertain |
|---|---|---|---|---|---|
| 1 | 210 | 204 | 6 | 0 | 0 |
| 2 | 1,066 | 1,012 | 50 | 4 | 0 |
| 3 | 599 | 597 | 2 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 |
| 5 | 64 | 64 | 0 | 0 | 0 |
| 6 | 1,443 | 1,443 | 0 | 0 | 0 |
| **Total** | **3,382** | **3,320** | **58** | **4** | **0** |

Every evidence row that an artifact marks as applied/value-claiming
reconciles **exactly** to the value currently stored in the database; no row
shows a differing or missing stored value, and no row references an invalid
table or field. This makes provenance mapping reliable for the full verified
set.

Machine-readable artefacts: `provenance_audit.json`, `evidence_reconciliation.csv`.

## 5. Notes

- Batch 004 produced no applicable evidence (blocked at schema level).
- Gaming benchmark data was intentionally not imported (see
  `batch001/07_gaming_benchmark_source_review.md`); no legally verified bulk
  gaming benchmark dataset was found.
- The reconciliation compares evidence target values against the current DB;
  where the same value is supported by more than one evidence record (e.g.
  architecture for the same CPU in batch 001 and batch 003), both records are
  retained, which supports multiple sources per field.