# M3 Phase 0 — Baseline Audit

**Date**: 2026-11-16
**Branch**: `feat/m3-catalog-expansion` (base `5074211`)
**Auditor**: M3 autonomous execution (evidence-based)
**Scope**: Code-side schema/importers/pipeline/API/frontend/CI audit + read-only production audit

This audit documents what SPECTRA actually has at base commit `5074211`, from
repository evidence and a read-only inspection of the production database. It
distinguishes directly verified evidence from assumption.

---

## 1. Verified baseline

| Item | Value | Evidence |
|---|---|---|
| origin/main SHA | `5074211` ("Merge pull request #5 from dapvdd/docs/m2-5-release-records") | `git log origin/main -5` after `git fetch` |
| GitHub main | `507421115369...` | `gh api repos/dapvdd/SPECTRA/commits/main` from david-lab |
| Production deploy | `M2.5-production`, sha `dcfd7df`, image `cf19a3ec…` | `/api/release` on 100.113.157.0:8080 |
| Production readiness | `ready`, DB reachable, `tracked-version-3` | `/api/ready` |
| Production schema version | 3 | read-only `SELECT version FROM schema_version` |
| Prod containers | spectra-m25-backend (healthy), spectra-m25-frontend, spectra-backend (healthy), spectra-frontend, spectra-m2-staging-backend-1 (healthy), spectra-m2-staging-frontend-1 | `docker ps` |
| Local repo | `C:\Users\user\spectra-local` | directory discovery |
| M3 worktree | `C:\Users\user\spectra-m3`, branch `feat/m3-catalog-expansion` at `5074211`, clean, 860 files | `git worktree add` output |

**Note**: production runs M2.5-production at `dcfd7df`, which is *behind* main
(`5074211` merged the release records; main has 3 commits not yet deployed).
The M3 worktree is cut from main per mission directive.

---

## 2. Production catalog state (read-only evidence)

Counts from the production database (`file:/app/data/spectra.db?mode=ro`):

| Table | Rows |
|---|---|
| hardware | **5 389** |
| CPU | 3 501 |
| GPU | 1 879 |
| RAM | 3 |
| STORAGE | 2 |
| MOTHERBOARD | 2 |
| PSU | 2 |
| ram/storage/motherboard/psu_specifications | 3 / 2 / 2 / 2 |
| sources | 11 |
| field_provenance | 39 503 |
| benchmark_results | 1 040 |
| schema_version | 3 |

Key findings:

- The catalog is CPU/GPU-dominated as the M3 brief states: 5 380 of 5 389 rows
  (99.83 %) are CPU or GPU.
- The four new categories exist in the schema but hold only 9 hardware rows
  total (4 RAM + 2 STORAGE + 2 MOTHERBOARD + 1 PSU by spec-table count; 9 rows
  by type). These are demo/fixture rows from earlier milestones — they are not
  a production catalog. M3 Phase 5 replaces them with verified pilot data in an
  isolated dev database first.
- `field_provenance` (39 503 rows) already covers all 4 new spec tables in its
  `VALID_TABLES` vocabulary — provenance infrastructure is reusable as-is.

---

## 3. Code-side schema audit (repository evidence)

### 3.1 Models (`backend/app/models/`)

| File | Table | Fields (all nullable except keys) |
|---|---|---|
| `hardware.py` | `hardware` | id, name (200, NOT NULL), manufacturer (100, NOT NULL), type (50), segment, release_date, architecture + relationships to 6 spec tables, benchmarks, provenance, external_identifiers |
| `ram.py` | `ram_specifications` | hardware_id (unique FK), ddr_generation (CHECK DDR3/4/5/6), capacity_gb, speed_mhz, modules, ecc, voltage_v, form_factor |
| `storage.py` | `storage_specifications` | hardware_id (unique FK), storage_type (CHECK NVMe/SATA SSD/HDD), capacity_gb, interface (40), read_mb_s, write_mb_s, dram_cache, form_factor |
| `motherboard.py` | `motherboard_specifications` | hardware_id (unique FK), socket (30), chipset (30), form_factor (20), ram_type (10), ram_slots, max_ram_gb, m2_slots, sata_ports, pcie_slots |
| `psu.py` | `psu_specifications` | hardware_id (unique FK), wattage (CHECK >0), efficiency_rating (CHECK 80 Plus list), modular, pcie_8pin_count, pcie_12vhpwr |
| `source.py` | `sources` | name, url, publisher, description, license_name, license_url, license_status (clear/unknown/restricted/unresolved), terms_notes, attribution, retrieved_on |
| `provenance.py` | `field_provenance` | hardware_id, source_id, table_name (CHECK includes 4 new tables), field_name, evidenced_value, source_url, license_name/license_notes, attribution, access_date, confidence, evidence_status (verified/uncertain/excluded/unmatched), source_reference, match_method, batch_no, recorded_at, benchmark_result_id |
| `external_identifier.py` | `external_identifiers` | hardware_id, source_id, external_id, identifier_type, unique (hardware_id, source_id, external_id) |

Verified facts:

- All 6 category spec tables exist in the SQLAlchemy `Base.metadata` and in the
  v2/v3 migration DDL (runner v3 creates them additively).
- Provenance is field-level and already supports the four new categories —
  **no new provenance infrastructure is required** (mission rule: avoid
  duplicate structures).
- The spec models are skeletons: RAM has no XMP/EXPO column, storage has no
  PCIe-gen or protocol column, motherboard has no BIOS-support field, PSU has
  no ATX-version/connector-inventory/dimensions fields. Phase 1 decides, per
  field, whether the missing field is (a) additive migration v4 column, (b)
  stored in existing columns, or (c) left UNKNOWN in M3 (documented).

### 3.2 Importers (`backend/app/importers/`)

| Module | Role | Reuse for M3 |
|---|---|---|
| `component_validators.py` | Per-category field vocabulary + coercion; closed `CATEGORY_TYPES` (ram/storage/motherboard/psu); `ValueError` on invalid; strips/normalizes empties | Directly reusable; extend vocabulary only if migration v4 adds columns |
| `generic_csv_importer.py` | CSV → Hardware upsert (name+manufacturer+type) + spec row + field_provenance (owner-manual, batch_no=0) | Directly reusable for pilot CSV import path |
| `cpu_csv.py` / `gpu_csv.py` | stdlib csv.DictReader readers | Pattern reference |
| `cpu/gpu_validator.py`, `cpu/gpu_normalizer.py` | Category-specific CPU/GPU validation + normalization | Pattern reference for M3 category validators |
| `test_component_validators.py`, `test_generic_csv_importer.py`, etc. | Existing pytest coverage | Regression baseline |

### 3.3 Acquisition/enrichment framework (`backend/app/scripts/`)

| Module | Role | M3 status |
|---|---|---|
| `source_acquisition.py` | `SourceAdapter` contract (source identity, license_*, required_columns, map_record, normalize_field_value), `AcquiredValue` provenance record, `SourceLicenseGate` (only `clear` passes), `register_adapter`/`acquire` | Exists; GPU/CPU-oriented field map. Phase 2 extends to 4 categories |
| `enrichment_pipeline.py` | Stage 3: `EnrichmentPlan`/`EnrichmentAction` (apply/reject/quarantine/conflict), `audit_dev_db`, `validate_acquisitions`, `import_dev` (dev-only, transactional, idempotent), `rollback_dev` | Exists; field map GPU/CPU-only → extend for RAM/Storage/Motherboard/PSU |
| `check_data_integrity.py` | PRAGMA quick_check + FK check + min row counts (`hardware ≥ 4500`, `sources ≥ 5`, `benchmark_results ≥ 800`, `field_provenance ≥ 1000`) | Exists; must stay valid on the dev DB used for the pilot |
| `seed_ci_dev_db.py` | Seeds `data/dev/spectra_dev.db` from `Base.metadata` | Pattern for the M3 pilot dev DB |

### 3.4 API (`backend/app/main.py` + `schemas/`)

- `CATALOG_TYPES = ("CPU", "GPU", "RAM", "STORAGE", "MOTHERBOARD", "PSU")` at
  line 127 — all 6 types already served by `/hardware` (server-side filters
  type/q/manufacturer/segment + limit/offset + `X-Total-Count`).
- `/hardware/facets` — type/manufacturer/segment facet counts under the same
  filters.
- `/hardware/{id}` — per-type `specifications` payload; RAM/STORAGE/MOTHERBOARD/
  PSU branches already implemented (lines 536/587/638/699).
- `/hardware/{id}/provenance`, `/sources`, `/sources/{id}` — provenance
  transparency endpoints exist.
- `security_headers.py` middleware sets nosniff, XFO DENY, CSP
  `default-src 'none'; frame-ancestors 'none'`, referrer policy — **preserve as-is**.
- Auth: feature-flagged (`SPECTRA_AUTH_ENABLED`), bcrypt + HMAC tokens,
  `require_auth` dependency. Production has `auth_enabled: false` and
  `ai_provider: unconfigured` (503-safe `/build/chat`).

### 3.5 Frontend (`frontend/src/`)

- `catalog.js`: `HARDWARE_TYPES = ["All","CPU","GPU","RAM","STORAGE","MOTHERBOARD","PSU"]`;
  manufacturer options derived from live facets (no static Intel/NVIDIA list).
- `buildConfig.js`: `BUILD_SLOTS` covers all 6 slots; per-category detail
  view models exist (RAM/Storage/Motherboard/PSU labels at lines 392-396).
- `detail.js`: `getRamDetailViewModel`, `getStorageDetailViewModel`,
  `getMotherboardDetailViewModel`, `getPsuDetailViewModel`, and
  `getCategoryDetailViewModel` routing — all 4 new categories already render.
- `App.jsx`: `GenericCategoryDetailView` (line 1390) + state-driven detail
  (no URL routing — preserved).
- Tests: `categoryDetail.test.js` covers the 4 view models (N/A for missing
  values, never CPU fields), `buildSlots.test.js`, `catalog.test.js`.

### 3.6 Compatibility engine (`backend/app/services/`)

- `compatibility_model.py`: `RULES_VERSION = "M2.5-RULES-v1"`,
  `COMPONENT_SLOTS` = 6 slots; states COMPATIBLE/INCOMPATIBLE/UNKNOWN/
  NOT_APPLICABLE.
- `compatibility_rules.py`: 7 registered rules (CPU×MB socket, RAM×MB
  generation, RAM×MB capacity, RAM×MB slots, storage×MB interface, PSU×build
  wattage two-tier with `PSU_TDP_REFERENCE_FRACTION = 0.3`, GPU×MB slot).
  Honest boundaries documented in the module docstring; UNKNOWN is
  first-class.
- `compatibility_service.py`: `load_build_specifications` (validates slot
  types) + `check_build_compatibility` (read-only).

### 3.7 Migration framework (`backend/app/migrations/`)

- `runner.py`: versioned, additive-only, copy-first, verify-per-step,
  idempotent; `schema_version` table; `MIGRATIONS` list (v1 baseline record,
  v2 auth tables, v3 four spec tables + provenance rebuild); `LATEST_VERSION = 3`.
- Production is at v3 — any M3 schema addition must be **migration v4+**.

### 3.8 CI (`.github/workflows/ci.yml`)

Gates observed: backend `pytest -q backend`; frontend `node --test src/*.test.js`
(vitest is NOT used; it fails on this codebase), `npx oxlint src`,
`npx vite build`; data-integrity `python -m backend.app.scripts.ci_verify_schema`
(fresh schema + migration runner + integrity check).

---

## 4. Existing source licensing assumptions (repository evidence)

From `docs/DATA_SOURCE_REGISTRY.md`, `docs/DATA_SOURCES.md`,
`data/research/batch009/source_license_assessment.md`,
`data/research/batch010/source_permission_research.md`, and
`data/research/batch015/02_source_and_license_audit.md`:

| Source | License status | M3 relevance |
|---|---|---|
| GPU Ark (gpuark.com/datasets) | **clear** (CC BY 4.0) | GPU only — not relevant to the 4 new categories |
| Wikipedia (English) | **clear** (CC BY-SA 4.0, share-alike) | Candidate for all 4 categories (manual/curated) |
| PassMark | restricted | Prohibited for bulk import |
| TechPowerUp | restricted | Prohibited for bulk import |
| Geekbench Browser | unknown | Benchmarks only; not a spec source |
| Intel ARK (Wayback) | unknown | Reference only |
| AMD product pages | unknown | Reference only |
| felixsteinke/cpu-spec-dataset | AGPL-3.0 code; **CSVs carry no data licence** | CPU only; not usable for the 4 new categories |

Conclusion carried into `M3_SOURCE_FEASIBILITY.md`: **no bulk "clear"-licensed
dataset exists today for RAM/Storage/Motherboard/PSU.** The viable Phase 0
path for each new category is (4) in the mission preference order: manually
curated records with verifiable official citations — imported through the
existing owner-manual source (`batch_no=0`, evidence_status='verified') —
until an explicitly licensed bulk feed is found and documented.

---

## 5. Gap list M3 must close

1. `docs/m3/` deliverables (all 14) — none exist yet.
2. Source feasibility + registry for the 4 new categories (Phase 0/Gate 0).
3. Identity rules: kit-vs-module (RAM), capacity/revision variants
   (storage/MB), MPN handling via `external_identifiers`, canonical identity
   keys (Phase 1).
4. Migration v4: only if a required spec field cannot be represented by
   existing columns (additive only, copy-first).
5. Category validators for range/cross-field checks and unit distinctions
   (MB/s vs Gb/s, MHz vs MT/s, TDP vs measured power) — extend
   `component_validators.py` or add an M3 layer.
6. Record lifecycle (DISCOVERED→…→PUBLISHED/QUARANTINED/REJECTED/SUPERSEDED),
   ingestion runs, publication batches (Phase 4) — as additive tables or
   in-pipeline state, decided in Phase 1.
7. Wikipedia/manual import path extension of `source_acquisition.py` +
   `enrichment_pipeline.py` field maps (Phase 2).
8. Pilot data: 400 verified records in an isolated dev DB (Phase 5) with the
   bounded-batch verification protocol.
9. Compatibility regression tests with real approved catalog examples
   (Phase 6).
10. UX: source attribution/last-verified/completeness display on category
    detail views (Phase 7) — reuse existing `source_service` endpoints.

---

## 6. Verified vs assumed

- **Verified**: everything in §1-§4 (git/remote/read-only DB/module reads).
- **Assumed (to verify in later phases)**: that manual CSV curation with
  official citations is acceptable under Gate 0 for all 4 categories (it is
  the documented fallback path); that the 4 new spec tables hold zero rows in
  the *dev* DB used for the pilot (checked at Phase 5 start).
