# Build Planner M1 — Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RAM, Storage, Motherboard, PSU as first-class catalog categories with provenance, a generic CSV importer, and API/frontend browsing — the data foundation for the compatibility engine (M2) and prices (M3).

**Architecture:** Follow the existing evidence-first patterns exactly: one spec table per category (FK `hardware.id`, unique nullable, like `cpu_specifications`), migration v3 in the versioned runner (4 new tables + `field_provenance` rebuild to lift the table-name CHECK), one generic CSV importer driven by per-category validator configs, provenance rows for every populated field, catalog API extension, and `HARDWARE_TYPES` growth in the frontend.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite (backend), React + Vite (frontend), pytest / node --test.

**Spec:** `docs/superpowers/specs/2026-11-10-build-planner-design.md` (§5 M1 table; anti-goals §2; constraints §3)

## Global Constraints

- Additive migrations only; registered in `backend/app/migrations/runner.py` as version 3; `schema_version` tracked; never applied to production in this work.
- `field_provenance` rebuild is copy-first: create `field_provenance_new` → `INSERT INTO ... SELECT` → drop old → rename; row count + `integrity_check` verified in the migration's `verify` callable.
- Invented spec values are forbidden: missing data stays NULL; provenance or nothing.
- Auto-import only from sources with `license_status="clear"` in the `sources` registry; owner CSVs register as source `owner-manual` (license clear).
- Full suite stays green every task: backend 1095 passed, 2 skipped, 2 deselected (CI ignore/deselect list); frontend 635 passed.
- Frontend: no new state library; `HARDWARE_TYPES` grows in `frontend/src/catalog.js:7`.
- Every task commits with tests in the same commit; TDD throughout (test written first, verified failing, then implemented).
- Migration v3 must rehearse cleanly on a disposable DB copy before the task completes (the runner itself supports `--database <copy>`).

## Review Focus

1. **Empty-CSV / header-only import** — a CSV with headers and zero data rows must complete with 0 imported / 0 failed, not crash. Test: `test_import_empty_csv_yields_zero_rows` (Task 3).
2. **Unknown type value in `Hardware.type`** — `hardware.type` is a closed vocabulary; a row with type `"RAMXX"` must be rejected at import validation, not stored. Test: `test_validator_rejects_unknown_type` (Task 2).
3. **Provenance rebuild preserves rows under CHECK** — copying 36k+ provenance rows into the rebuilt table must keep every row (count match) and the new CHECK must accept the 4 new table names while still rejecting unknown ones. Tests: `test_v3_verify_rebuild_preserves_rows`, `test_new_check_accepts_new_tables_rejects_unknown` (Task 1).
4. **Duplicate component per hardware** — second spec row for the same `hardware_id` must fail import (unique constraint is load-bearing like cpu/gpu). Test: `test_duplicate_hardware_spec_rejected` (Task 3).
5. **Facet counts with new types** — `/hardware/facets` must include RAM/STORAGE/MOTHERBOARD/PSU counts once data exists and not error when they are absent. Test: `test_facets_include_new_types` (Task 4).

---

### Task 1: Migration v3 — 4 spec tables + field_provenance rebuild

**Files:**
- Create: `backend/app/models/ram.py`, `backend/app/models/storage.py`, `backend/app/models/motherboard.py`, `backend/app/models/psu.py`
- Modify: `backend/app/models/hardware.py` (add 4 relationships), `backend/app/models/provenance.py` (extend `VALID_TABLES`), `backend/app/models/__init__.py`, `backend/app/migrations/runner.py` (register Migration v3)
- Test: `backend/app/test_migration_runner.py` (extend), `backend/app/test_models_v31_categories.py` (new)

**Interfaces:**
- Consumes: existing `Migration(version, name, description, statements, downgrade, verify, reversible)` dataclass and `_verify_v2` pattern in `backend/app/migrations/runner.py`; `Hardware` relationship pattern from `cpu.py:62-64`.
- Produces: models `RAMSpecification`, `StorageSpecification`, `MotherboardSpecification`, `PSUSpecification` (importable from `backend.app.models`); `VALID_TABLES` extended to include `"ram_specifications"`, `"storage_specifications"`, `"motherboard_specifications"`, `"psu_specifications"`; schema_version 3. M2's compatibility service and M3's price table FK these models by name.

- [ ] **Step 1: Write the failing model tests**

Test file `backend/app/test_models_v31_categories.py`, class per model, asserting: `__tablename__` values (`ram_specifications`, `storage_specifications`, `motherboard_specifications`, `psu_specifications`); each model's columns exist per the design §5 field lists (e.g. `RAMSpecification.ddr_generation`, `speed_mhz`, `capacity_gb`, `modules`, `ecc`, `voltage_v`, `form_factor`); `hardware_id` is nullable+unique like `cpu.py:21-25`; `Hardware` has relationships `ram_specification`, `storage_specification`, `motherboard_specification`, `psu_specification` (uselist=False). Also assert `VALID_TABLES` contains the four new names.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/app/test_models_v31_categories.py -v`
Expected: FAIL with `ImportError` (modules do not exist).

- [ ] **Step 3: Implement the four models + hardware relationships + VALID_TABLES**

Follow `backend/app/models/cpu.py` exactly (imports, `TYPE_CHECKING`, `Mapped`/`mapped_column`, `back_populates`). Column types per design §5 M1 table: Integer for counts/capacities/slots/wattage/modules; Float for clocks/voltage/mb_s; String for generations/types/interfaces/ratings/socket/chipset/form_factor. Extend `VALID_TABLES` in `provenance.py:35-40`. Register both models in `models/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/app/test_models_v31_categories.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing migration v3 test**

Extend `backend/app/test_migration_runner.py` with `V3Tests`: on a tmp SQLite DB built by the existing baseline fixture (copy the pattern `V2Tests` uses): (a) `upgrade()` records version 3 and creates the 4 tables (assert via `PRAGMA table_info` column presence); (b) `test_v3_verify_rebuild_preserves_rows` — seed N provenance rows pre-upgrade, assert the same N rows exist post-upgrade with identical `(table_name, field_name)` sets; (c) `test_new_check_accepts_new_tables_rejects_unknown` — INSERT with `table_name='ram_specifications'` succeeds, `table_name='bogus_table'` raises `IntegrityError`; (d) downgrade v3→v2 reverses (drop 4 tables; provenance table restored to old vocabulary) per the existing downgrade test pattern.

- [ ] **Step 6: Run to verify the migration test fails**

Run: `python -m pytest backend/app/test_migration_runner.py::V3Tests -v`
Expected: FAIL (no version 3 registered).

- [ ] **Step 7: Implement Migration v3 in runner.py**

Statements in order: 4× `CREATE TABLE IF NOT EXISTS` (mirroring the model columns exactly, incl. the FK and `UNIQUE` on `hardware_id`); then the provenance rebuild: `CREATE TABLE field_provenance_new (...)` with the widened `table_name` CHECK (8 names), `INSERT INTO field_provenance_new SELECT ... FROM field_provenance`, `DROP TABLE field_provenance`, `ALTER TABLE field_provenance_new RENAME TO field_provenance`, recreate the indexes from `provenance.py:80+`. `verify` callable: row count of `field_provenance` matches pre-rebuild count (capture via a `PRAGMA` snapshot inside verify), `PRAGMA integrity_check == 'ok'`, all 4 new tables present with expected columns. `downgrade`: drop the 4 tables + rebuild provenance back to the old CHECK (same copy-first pattern). `reversible=True`.

- [ ] **Step 8: Run migration tests + rehearse on a copy**

Run: `python -m pytest backend/app/test_migration_runner.py -v` → all PASS.
Then rehearse: copy `data/spectra.db` to a temp file, run `python backend/app/migrations/runner.py --database <copy>` → upgrade to v3 with verify OK, run again → `up-to-date`.

- [ ] **Step 9: Full backend suite + commit**

Run: `python -m pytest backend -q` with the CI ignore/deselect list → 1095+ passed, 2 skipped.
```bash
git add backend/app/models/ backend/app/migrations/runner.py backend/app/test_models_v31_categories.py backend/app/test_migration_runner.py
git commit -m "feat(planner): add RAM/storage/mobo/PSU spec tables with provenance rebuild (migration v3)"
```

---

### Task 2: Category validators + license-gated source registration

**Files:**
- Create: `backend/app/importers/component_validators.py` (one validator config per category), `backend/app/importers/test_component_validators.py`
- Modify: `backend/app/seed_sources.py` or equivalent owner-source registration path (add `owner-manual` source idempotently)

**Interfaces:**
- Consumes: the four models from Task 1 (field lists are the validator vocabularies); `LICENSE_STATUSES` from `backend/app/models/source.py:12`; `Hardware.type` closed-vocabulary validation pattern from `hardware.py`.
- Produces: `validate_component_row(category: str, row: dict) -> dict` raising `ValueError` on invalid rows, and `CATEGORY_TYPES: dict[str, str]` mapping category → required `Hardware.type` value (`"RAM"`, `"STORAGE"`, `"MOTHERBOARD"`, `"PSU"`). Task 3's importer is the only consumer.

- [ ] **Step 1: Write the failing validator tests**

`backend/app/importers/test_component_validators.py`: (a) a valid RAM row passes through with types coerced (capacity int, speed int); (b) `test_validator_rejects_unknown_type` — `category="ram"` with `type="RAMXX"` raises; (c) unknown category raises; (d) missing required identity fields (name/manufacturer) raise; (e) empty optional fields normalize to None, never `""`; (f) each of the 4 categories validates one minimal-good row and rejects one wrong-typed value (e.g. `speed_mhz="fast"`).

- [ ] **Step 2: Run to verify failing**

Run: `python -m pytest backend/app/importers/test_component_validators.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `component_validators.py`**

`CATEGORY_TYPES` dict; per-category field spec (name → (python type, required?, max length)); `validate_component_row` coerces, strips, normalizes empties to None, and raises `ValueError` with the offending field named. Type values checked against the closed vocabulary (`RAM`/`STORAGE`/`MOTHERBOARD`/`PSU` implied by category, mismatch = error).

- [ ] **Step 4: Run to verify passing**

Run: `python -m pytest backend/app/importers/test_component_validators.py -v`
Expected: PASS.

- [ ] **Step 5: Ensure `owner-manual` source exists (test + implement)**

Test: registering twice yields one row with `license_status="clear"`. Implement in the existing seed-sources path idempotently.

- [ ] **Step 6: Suite + commit**

```bash
git add backend/app/importers/component_validators.py backend/app/importers/test_component_validators.py backend/app/seed_sources.py
git commit -m "feat(planner): add per-category component validators and owner-manual source"
```

---

### Task 3: Generic CSV importer with provenance

**Files:**
- Create: `backend/app/importers/generic_csv_importer.py`, `backend/app/importers/test_generic_csv_importer.py`

**Interfaces:**
- Consumes: `validate_component_row` + `CATEGORY_TYPES` (Task 2); the 4 models (Task 1); `FieldProvenance` model (`hardware_id` + `table_name` + `field_name`, status vocabulary from `provenance.py:26-30`); `Hardware` creation pattern from `cpu_importer.py`.
- Produces: `import_component_csv(session_factory, category: str, csv_path: Path, source_name: str = "owner-manual") -> ImportReport` where `ImportReport` is a dataclass with `imported: int`, `failed: int`, `errors: list[str]`. API endpoints (Task 4) never call this directly; it is an ops tool (importer family convention).

- [ ] **Step 1: Write the failing importer tests**

Using tmp CSVs: (a) 3 good RAM rows import, `imported==3`, rows exist with specs, and each populated spec field has a `field_provenance` row with `table_name="ram_specifications"` and the owner source; (b) `test_import_empty_csv_yields_zero_rows` — header-only CSV → `imported==0, failed==0`, no crash; (c) `test_duplicate_hardware_spec_rejected` — two rows with the same hardware name → second lands in `errors`, first imports; (d) one bad row (wrong type value) → `failed==1`, good siblings still import (per-row isolation); (e) mixed-category CSV rejected (category is a single argument, no auto-detect).

- [ ] **Step 2: Run to verify failing**

Run: `python -m pytest backend/app/importers/test_generic_csv_importer.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the importer**

Read CSV via stdlib `csv.DictReader`; validate each row through `validate_component_row`; upsert `Hardware` (by name+manufacturer+type) then the category spec row (unique per hardware — second occurrence fails per (c)); write provenance rows only for populated fields, `evidence_status="verified"`, source = the registered source by name. Per-row try/except keeps bad rows from killing the batch (pattern: `cpu_importer.py`).

- [ ] **Step 4: Run to verify passing**

Run: `python -m pytest backend/app/importers/test_generic_csv_importer.py -v`
Expected: PASS.

- [ ] **Step 5: Suite + commit**

```bash
git add backend/app/importers/generic_csv_importer.py backend/app/importers/test_generic_csv_importer.py
git commit -m "feat(planner): add generic component CSV importer with field provenance"
```

---

### Task 4: Catalog API + facets for new categories

**Files:**
- Modify: `backend/app/main.py` (hardware list/detail/facets handlers), `backend/app/schemas/` (detail response models per category)
- Test: `backend/app/test_catalog_v31_categories.py` (new)

**Interfaces:**
- Consumes: the 4 models + relationships (Task 1); existing `get_hardware` handler (main.py:319-366) with `X-Total-Count` pagination; `HardwareFacetsResponse`/`HardwareDetail` schema patterns.
- Produces: `GET /hardware?type=RAM|STORAGE|MOTHERBOARD|PSU` works with q/manufacturer/limit/offset unchanged; `GET /hardware/{id}` returns the type-specific spec block for the new categories (`HardwareDetail` gains optional `ram_specification`/`storage_specification`/`motherboard_specification`/`psu_specification` fields); `GET /hardware/facets` counts the new types. M2's build-planner frontend and M3's price UI consume these endpoints.

- [ ] **Step 1: Write the failing API tests**

`backend/app/test_catalog_v31_categories.py` (TestClient against the app, DB fixture pattern from `test_hardware_catalog_api.py`): (a) seed one row per new category via Task 3's importer or direct model creation; each type filters the list and returns `X-Total-Count: 1`; (b) detail response carries the right spec block with values; (c) `test_facets_include_new_types` — facets include the 4 types with correct counts; facets on an empty catalog for a type returns 0 not error; (d) unknown type value → 422; (e) existing CPU/GPU behaviour unchanged (one regression test each: list + detail).

- [ ] **Step 2: Run to verify failing**

Run: `python -m pytest backend/app/test_catalog_v31_categories.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Extend the type validation set, the detail response models (eager-load the new relationships like cpu/gpu), and the facets type list. No pagination changes.

- [ ] **Step 4: Run to verify passing + full suite**

Run: `python -m pytest backend/app/test_catalog_v31_categories.py -v` then the full backend suite with the CI ignore/deselect list → all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/schemas/ backend/app/test_catalog_v31_categories.py
git commit -m "feat(planner): expose RAM/storage/mobo/PSU through catalog API and facets"
```

---

### Task 5: Frontend catalog categories

**Files:**
- Modify: `frontend/src/catalog.js` (`HARDWARE_TYPES`, `TYPE_LABELS`, manufacturer filter lists), catalog browse/detail components as needed
- Test: `frontend/src/catalog.test.js` (extend)

**Interfaces:**
- Consumes: Task 4's API surface; existing `requestHardwareCatalog`/`getCatalogTypeLabel` helpers.
- Produces: `HARDWARE_TYPES = ["All", "CPU", "GPU", "RAM", "STORAGE", "MOTHERBOARD", "PSU"]`; type labels for the new categories. The Build Planner view (M2) and price UI (M3) reuse these.

- [ ] **Step 1: Write the failing frontend tests**

Extend `frontend/src/catalog.test.js`: `HARDWARE_TYPES` contains the 4 new values in order; `getCatalogTypeLabel("RAM")` returns a human label; the new types survive `getCatalogFilterState` handling (one assertion each).

- [ ] **Step 2: Run to verify failing**

Run: `node --test src/catalog.test.js`
Expected: FAIL.

- [ ] **Step 3: Implement catalog.js changes**

Update `HARDWARE_TYPES` + `TYPE_LABELS`; extend manufacturer filter lists only if the fixture data needs it (builder's call, keep minimal).

- [ ] **Step 4: Run to verify passing + full frontend suite + lint + build**

Run: `node --test src/*.test.js` → 635+ pass; `npx.cmd oxlint src` → 0 errors; `npx.cmd vite build` → success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/catalog.js frontend/src/catalog.test.js
git commit -m "feat(planner): add new component categories to frontend catalog"
```

---

### Task 6: M1 verification gate

**Files:**
- Modify: none (verification only); fix-forward commits if a check fails.

- [ ] **Step 1: Full backend suite**

Run: `python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking`
Expected: all pass, 2 skipped (AI-gated), 2 deselected.

- [ ] **Step 2: Full frontend suite + build**

Run: `node --test src/*.test.js` (in `frontend/`) → 0 fail; `npx.cmd vite build` → success.

- [ ] **Step 3: Migration rehearsal on a fresh copy**

Copy `data/spectra.db` → temp; run the runner against the copy → v3 applied, verify OK, second run `up-to-date`. Confirm production DB untouched (no runner invocation against it).

- [ ] **Step 4: Branch state check**

`git status --porcelain` empty; `git log --oneline main..HEAD` shows the 5 task commits; nothing merged, nothing deployed.

**M1 DONE when:** all four categories browse-able via API with provenance and facets, suite totals ≥ previous baseline plus new tests, migration v3 rehearsed on a copy.
