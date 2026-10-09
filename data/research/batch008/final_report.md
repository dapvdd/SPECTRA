# SPECTRA Batch 008 - Final Report

Date: 2026-10-09
Commit: applied in Batch 008 (see independent audit for the database state).

## 1. Initial checkpoint and working-tree state

- Branch: `main`. Latest commit at start: `67bae46 chore(data): audit hardware specification quality` (Batch 007).
- Working tree: clean except pre-existing untracked items (`.opencode/`,
  `data/backups/`, two legacy `data/spectra.db.bak-*` files, and the
  pre-existing untracked `data/research/batch001/09_independent_audit.md`).
- Database: `data/spectra.db`, SHA-256 `858a67256853a486af580ac8e5d5c193b4d1c97875b89f0f6fce28df0b2bc39c`,
  `PRAGMA quick_check` = `ok`.
- Baseline counts: hardware 5,239 (CPU 3,360 / GPU 1,879), cpu_specifications 3,360,
  gpu_specifications 1,879, benchmark_results 1,040, external_identifiers 3,575,
  sources 3, build_conversations 4, build_messages 4. All match the expected checkpoint.

## 2. Findings about current provenance support

- The database schema had **no field-level provenance**: `sources` holds only
  `name`/`url`; only `external_identifiers` and `benchmark_results.source_id`
  reference sources, and neither traces a specification value to its source.
- All provenance facts (source names, URLs, confidence, per-batch statuses,
  licences) lived only in research artifacts under `data/research/batch001-006/`.
- Batch 003 alone recorded Wikipedia article access dates in
  `sources/provenance.json`; GPU Ark access dates were not recorded per row.
- Documented licences: GPU Ark CC BY 4.0; Wikipedia CC BY-SA 4.0; TechPowerUp
  bulk reuse blocked (robots.txt); Intel ARK archived cross-check only
  (no reuse grant). See `provenance_gaps.md`.

## 3. Evidence audited and mapped

- **3,382 evidence records** reconstructed from the committed artifacts of
  batches 001-006.
- **3,320 mapped reliably (verified)** - every value the artifacts claim as
  applied/the claimed value reconciles **exactly** to the current database
  value. 0 uncertain, 0 invalid references.
- **58 excluded** (6 batch 001 deliberately excluded, 50 batch 002 ambiguous,
  2 batch 003 excluded) and **4 unmatched** (batch 002) are recorded with
  status + reasons.
- Breakdown: batch 1: 210 (204 verified + 6 excluded); batch 2: 1,066
  (1,012 + 50 + 4); batch 3: 599 (597 + 2); batch 4: 0 (schema-blocked);
  batch 5: 64 verified; batch 6: 1,443 verified.

## 4. Implemented changes and rationale

Rationale: provenance existed only in research artifacts and could not be
queried; the mapping to persisted values is fully reliable (3,320 exact
reconciles), so a minimal, normalised storage mechanism was justified.

1. **Model** `backend/app/models/provenance.py` - new `field_provenance`
   table linking `hardware_id` + (table, field) to a `sources` row, with
   source URL, license name/notes, attribution, access date, confidence,
   evidence status (`verified|uncertain|excluded|unmatched`), matching keys,
   batch number and notes; CHECK constraints on status and table name; unique
   identity constraint; indexes on (hardware, table, field), source, status.
2. **Service** `backend/app/services/provenance_service.py` - validated,
   idempotent insert; rejects unknown hardware, table, field, or status.
3. **Migration** `backend/app/migrations/add_field_provenance.py` - idempotent
   `CREATE TABLE IF NOT EXISTS` consistent with the repository's
   `Base.metadata.create_all` + manual-SQL convention (no new migration
   framework introduced).
4. **Loader** `data/research/batch008/load_provenance.py` - extracts evidence
   from the artifacts, reconciles against the live DB, registers sources,
   inserts provenance idempotently; never writes specification values.
5. **Schema**: 4 new `sources` rows (GPU Ark, Wikipedia (English), Intel ARK,
   one documented placeholder for the 6 untracked excluded records); live DB
   got the `field_provenance` table + 3,382 rows.
6. Frontend UI and application behaviour untouched.

## 5. Database hash before/after

- Before: `858a67256853a486af580ac8e5d5c193b4d1c97875b89f0f6fce28df0b2bc39c`
- After: `0a53ba47e2a855e06790a0263611f120c247c82a0969c20edc4280bd92d6a917`
- Difference is additive (new table + 4 source rows) - see independent audit.

## 6. Backup

- Path: `data/backups/spectra-pre-batch008-provenance-20261009T122335Z.db`
  (kept outside Git).
- SHA-256: `858a67256853a486af580ac8e5d5c193b4d1c97875b89f0f6fce28df0b2bc39c`
  (matches pre-migration DB).
- `PRAGMA quick_check`: `ok`.

## 7. PRAGMA quick_check

- Pre: `ok`. Post: `ok`. Post `PRAGMA foreign_key_check`: empty.

## 8. Row counts and specification-value diff

| Table | Before | After |
|---|---|---|
| hardware | 5,239 | 5,239 |
| cpu_specifications | 3,360 | 3,360 |
| gpu_specifications | 1,879 | 1,879 |
| benchmark_results | 1,040 | 1,040 |
| external_identifiers | 3,575 | 3,575 |
| build_conversations | 4 | 4 |
| build_messages | 4 | 4 |
| sources | 3 | 7 |
| field_provenance | (absent) | 3,382 |

- Specification-value diff: **none** (all CPU, GPU and hardware fields
  byte-identical before/after, verified by the independent audit).

## 9. Backend / frontend tests

- Backend: **565 passed** (548 pre-existing + 17 new provenance tests), 0 failed,
  0 skipped. Two pre-existing warnings (FastAPI/Starlette `httpx` deprecation and
  anyio `BlockingPortal` alias) unrelated to this batch.
- Frontend: `node --test`: **520 passed**, 0 failed, 0 skipped, 0 todo.
- No Docker runtime was used; no claim is made about container validation.

## 10. Licensing and attribution limitations

- GPU Ark values record `CC BY 4.0` + required attribution.
- Wikipedia values record `CC BY-SA 4.0`; attribution and share-alike
  obligations must be honoured in any user-facing redistribution - needs
  legal confirmation before export.
- 44 legacy TechPowerUp GPU clocks remain in the DB with the documented reuse
  restriction recorded in `license_notes`; 16/44 were cross-checked vs NVIDIA.
- 2 Intel ARK cross-check values carry no reuse grant.
- Base-import sources (PassMark, original TechPowerUp import, Geekbench) have
  **no documented licence and no provenance records yet** - a remaining gap.
- Access dates unknown for most evidence; recorded only for batch 003
  (2026-10-09); not fabricated elsewhere.

## 11. Files changed

- `data/research/batch008/evidence.py` (new) - extraction + reconciliation.
- `data/research/batch008/load_provenance.py` (new) - idempotent loader.
- `data/research/batch008/snapshot_state.py` (new) - audit state snapshot.
- `data/research/batch008/compare_states.py` (new) - independent audit.
- `data/research/batch008/provenance_inventory.md`, `provenance_gaps.md` (new).
- `data/research/batch008/provenance_audit.json`,
  `data/research/batch008/evidence_reconciliation.csv` (new, machine-readable).
- `data/research/batch008/independent_audit.md`,
  `data/research/batch008/independent_audit.json` (new).
- `data/research/batch008/final_report.md` (new, this file).
- `backend/app/models/provenance.py` (new) - `FieldProvenance` model.
- `backend/app/services/provenance_service.py` (new).
- `backend/app/migrations/add_field_provenance.py` (new).
- `backend/app/test_field_provenance.py` (new) - 17 tests.
- `backend/app/models/__init__.py`, `backend/app/models/hardware.py`
  (modified) - exports + relationship.

`.opencode/` untouched and not staged. Database backups, the two legacy
`data/spectra.db.bak-*` files, and the pre-existing untracked
`batch001/09_independent_audit.md` were not staged.

## 12. Remaining gaps and recommended next batch

Reconstruct provenance for base-import values (PassMark CPU rows, original
TechPowerUp GPU import, Geekbench benchmarks) and register their licences;
determine disposition of the 44 legacy TechPowerUp-derived GPU clocks;
secure a legally verified gaming-benchmark dataset with provenance; record
access dates for all future evidence collection; confirm CC BY-SA share-alike
handling before any redistribution of Wikipedia-derived values.