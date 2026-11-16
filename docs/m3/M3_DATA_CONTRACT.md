# M3 Data Contract

**Date**: 2026-11-16
**Status**: Implementation contract for Phases 1-5
**Schema compatibility**: additive over SQLite schema v3 (migration v4+)

## 1. Existing structures (reused — no duplication)

| Concern | Existing structure | Reuse rule |
|---|---|---|
| Catalog rows | `hardware` (name, manufacturer, type, segment, release_date, architecture) | All M3 records are `hardware` rows with `type` in (RAM, STORAGE, MOTHERBOARD, PSU) |
| Per-category specs | `ram_specifications`, `storage_specifications`, `motherboard_specifications`, `psu_specifications` (unique per hardware) | One spec row per hardware; extended only via migration v4 columns |
| Sources | `sources` (+ publisher/license_name/license_url/license_status/terms_notes/attribution/retrieved_on) | New M3 sources enter as rows with honest metadata |
| Field provenance | `field_provenance` (per (hardware, table, field, source) uniqueness) | One row per populated spec field; **never duplicated for M3** |
| External identifiers (MPN) | `external_identifiers` (hardware_id, source_id, external_id, identifier_type) | MPN rows use `identifier_type='mpn'` |
| Import mechanism | `generic_csv_importer.py` + `component_validators.py` | Extended, not replaced |

## 2. New structures (migration v4 — additive)

### 2.1 `canonical_identity` columns on `hardware` (v4)

Add three nullable columns via `ALTER TABLE hardware ADD COLUMN`:

| Column | Type | Purpose |
|---|---|---|
| `canonical_key` | VARCHAR(300) | Deterministic identity key (§3). NULL = pre-M3 rows (never backfilled silently). Unique index (partial, WHERE canonical_key IS NOT NULL) |
| `product_family` | VARCHAR(200) | Family-level grouping (e.g. "Trident Z5", "990 PRO", "B650 Tomahawk") |
| `identity_status` | VARCHAR(20) | `confirmed` / `provisional`. Importers set `confirmed` only when manufacturer+family+model are unambiguous; uncertain identities stay `provisional` and are never auto-merged |

**No destructive change**: existing 5 389 production rows keep NULL canonical
keys; uniqueness is enforced only on non-NULL values (partial unique index).

### 2.2 `ingestion_runs` (v4)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| run_type | VARCHAR(30) | `csv_import` / `acquisition` / `publication` |
| source_id | INTEGER FK sources.id, nullable | NULL for owner-manual |
| category | VARCHAR(20) | RAM/STORAGE/MOTHERBOARD/PSU/ALL |
| mode | VARCHAR(20) | `apply` / `dry_run` |
| status | VARCHAR(20) | `running` / `success` / `failed` / `rolled_back` |
| rows_seen / rows_applied / rows_rejected / rows_quarantined | INTEGER | Counters |
| started_at / finished_at | TEXT (ISO-8601) | |
| notes | TEXT | Includes the run's input reference (file path or adapter name); never secrets |

### 2.3 `publication_batches` (v4)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| batch_no | INTEGER | Monotonic; distinct from provenance `batch_no` (owner-manual=0 stays reserved) |
| category | VARCHAR(20) | |
| record_count | INTEGER | |
| approved_by | VARCHAR(100) | Explicit approval identity (never auto) |
| status | VARCHAR(20) | `prepared` / `published` / `rolled_back` |
| created_at / published_at | TEXT | |
| notes | TEXT | |

### 2.4 `record_status` columns on `hardware` (v4)

| Column | Type | Notes |
|---|---|---|
| `record_status` | VARCHAR(20), default NULL | Lifecycle: DISCOVERED → EXTRACTED → NORMALIZED → VALIDATED → APPROVED → PUBLISHED; terminals: QUARANTINED / REJECTED / SUPERSEDED. NULL = legacy row (pre-M3, treated as PUBLISHED-equivalent for read paths only) |
| `superseded_by_id` | INTEGER FK hardware.id, nullable | Set when SUPERSEDED; points at the replacement record |

Lifecycle transitions are enforced in application code
(`record_lifecycle.py`, Phase 4) with a transition table; unknown transitions
raise. `record_status` is NOT a SQL CHECK constraint (SQLite ALTER TABLE
cannot add one; validated in the application + tests, same pattern as
`sources.license_status`).

## 3. Canonical identity key (contract)

```
canonical_key = lower(
    normalize(manufacturer) + "|" +
    type + "|" +
    normalize(family_or_model) + "|" +
    variant_key
)
```

- `normalize`: Unicode NFKC, invisible chars stripped, whitespace collapsed,
  trademark symbols removed (reuse `backend.app.normalization.primitives`).
- `variant_key` per category (see `M3_IDENTITY_RULES.md`):
  - RAM: `kit-or-module` marker + modules + capacity + generation + speed
    (e.g. `kit-2x16-ddr5-6000` vs `module-1x32-ddr5-5600` — a 2×16 GB kit and
    a single 32 GB module are **never** the same key).
  - Storage: `capacity + form factor + interface` (1 TB ≠ 2 TB).
  - Motherboard: `form factor + revision` when a revision is documented;
    revision-unknown boards keep the base key and `identity_status='provisional'`
    when a revision is suspected.
  - PSU: `wattage + efficiency + modularity`.
- Two records with different `canonical_key` are different SKUs. Two source
  rows producing the same `canonical_key` are duplicate candidates → conflict
  pipeline (Phase 3/4), never auto-merged.

## 4. Field contract per category (import vocabulary)

Import vocabulary = existing `component_validators.py` fields, plus the
categorical constraints M3 adds in Phase 3 (unit semantics, ranges, enum
token lists). The contract fixes the *column set*; validators enforce
*values*.

- RAM: `ddr_generation, capacity_gb, speed_mhz, modules, ecc, voltage_v, form_factor`
- Storage: `storage_type, capacity_gb, interface, read_mb_s, write_mb_s, dram_cache, form_factor`
- Motherboard: `socket, chipset, form_factor, ram_type, ram_slots, max_ram_gb, m2_slots, sata_ports, pcie_slots`
- PSU: `wattage, efficiency_rating, modular, pcie_8pin_count, pcie_12vhpwr`

Every populated field gets a `field_provenance` row (existing mechanism).
Absent fields stay absent (NULL) — never fabricated, never inferred.

## 5. Provenance contract

For each imported record, per populated field:

| field_provenance column | M3 value |
|---|---|
| `table_name` | the category spec table |
| `field_name` | the column name |
| `evidenced_value` | string form of the stored value |
| `source_url` | the citation URL (Wikipedia revision URL or official product page URL) |
| `license_name` / `license_status` (via source row) | `CC BY-SA 4.0` / `clear` for Wikipedia; site terms recorded honestly for manufacturer pages |
| `evidence_status` | `verified` (human-verified curated entry) / `uncertain` (kept out of PUBLISHED) |
| `access_date` | date of citation access |
| `match_method` | `manual-curation` |
| `batch_no` | 0 for owner-manual; publication batch id recorded via `publication_batches` + `ingestion_runs` |

## 6. Test contract (Gate 1)

- Schema tests: migration v4 applies additively on a v3 copy; re-run is a
  no-op; verify() checks columns/tables exist; downgrade documented.
- Identity tests: canonical_key determinism; kit≠module; capacity variants;
  revision handling; provisional vs confirmed.
- Duplicate tests: same canonical_key → conflict record, no silent merge.
- Lifecycle tests: transition table enforcement; PUBLISHED requires approval
  + batch; no path from DISCOVERED to PUBLISHED in one step.
- Rehearsal: full migration on a disposable copy of the pilot DB before any
  batch import.
