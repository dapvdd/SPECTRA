# SPECTRA Batch 009 — Final Report

Date: 2026-10-10
Commit: applied in Batch 009 (see section 11).

## 1. Initial checkpoint and working-tree state

- Branch: `main`. Latest commit at start: `75de142 feat(data): improve
  hardware provenance traceability` (Batch 008) — verified present.
- Working tree: clean except the known untracked `.opencode/`, `data/backups/`,
  two legacy `data/spectra.db.bak-*` files, `data/raw/`, and the pre-existing
  untracked `data/research/batch001/09_independent_audit.md`.
- Database: `data/spectra.db`, SHA-256
  `0a53ba47e2a855e06790a0263611f120c247c82a0969c20edc4280bd92d6a917`
  (matches the reported Batch 008 hash). `PRAGMA quick_check` = `ok`,
  `PRAGMA foreign_key_check` = empty.
- Baseline row counts: hardware 5,239 (CPU 3,360 / GPU 1,879),
  cpu_specifications 3,360, gpu_specifications 1,879, benchmark_results 1,040,
  external_identifiers 3,575, sources 7, field_provenance 3,382.
- Baseline provenance: 3,320 verified / 58 excluded / 4 unmatched;
  2,234 distinct hardware entities with *verified* provenance.
- Batch 008's independent-audit state, its reported hash, and its provenance
  counts were all reproduced exactly before any change was made. The reported
  figure **2,234** is the count of hardware entities with **verified**
  provenance (2,238 incl. excluded/unmatched) — confirmed against the live DB.

## 2. Actual base-import provenance gaps (measured, not estimated)

- Total populated cells in the DB: **53,230** (52,708 distinct field-level
  cells when the Geekbench rows that share one hardware are collapsed).
- Populated cells with verified provenance **before** Batch 009: **3,320**
  (enrichment batches 001–006 only). Effective base-import gap was therefore
  ~49,000 distinct cells (the "≈33,000" figure from Batch 008 was a
  historical estimate; the measured value above 3,320 is the authoritative
  one).
- Populated cells with verified provenance **after** Batch 009: **34,747**.
- Remaining uncovered cells: **17,961** = 15,717 identity cells
  (`name`/`manufacturer`/`type`, out of schema scope) + 1,726
  `cpu_specifications` cells (unmatched or multi-source) + 518–1,040
  `benchmark_results` cells (schema cannot represent benchmark provenance).

## 3. Evidence reconciled by source and status

`evidence_reconciliation.csv` (51,787 rows) classifies every populated
base-import-writable cell: **47,325 verified | 2,251 uncertain | 2,211
unmatched**. Verified by dataset (persistable, non-identity):

| dataset | artifact | verified persistable cells | statuses stored |
|---|---|---|---|
| intel | intel-cpus.csv | 16,276 | verified (all persisted) |
| amd | amd-cpus.csv | 1,765 | verified (all persisted) |
| passmark | benchmark-cpus.csv | 546 | verified (all persisted) |
| techpowerup | gpu_1986-2026.csv | 12,840 persisted (12,854 verified; 14 already covered by batch 005) | verified |
| geekbench | processor-benchmarks.csv | 1,040 score rows | verified in artifacts only (schema-blocked) |

Artifact SHA-256 hashes are recorded in `provenance_reconciliation.json`
(intel `eb164c40…`, amd `abe6c8eb…`, passmark `90b19cd4…`, techpowerup
`495fb95e…`, geekbench `22477b97…`).

## 4. Newly persisted provenance records

- **31,427 new `field_provenance` rows** (all `evidence_status=verified`,
  `batch_no=0`, 30,619 confidence high / 808 medium) loaded idempotently via
  the existing `provenance_service` and schema.
- Sources grew 7 → 9 with two new rows: `Intel ARK (intel-cpus.csv snapshot)`
  and `AMD product specifications (amd-cpus.csv snapshot)`.
- Every new row carries a `source_reference` (artifact + `manufacturer=name`
  entity key), the reconciliation `match_method`, and `license_notes` that
  record the restricted/unknown reuse status of the dataset.
- **Idempotency verified**: a second run inserted 0 rows.
- No schema change was made. `memory_bus_width_bits` was correctly left to its
  existing batch-006 provenance (the base importer never wrote it).
- A source-identity inconsistency was **recorded, not silently "fixed"**: the
  3,575 `external_identifiers` rows are labelled `source_id 1` (PassMark) yet
  demonstrably came from the Intel ARK / AMD exports.

## 5. Source licensing and attribution conclusions (with limitations)

Full evidence in `source_license_assessment.md` / `.json`. This is a research
assessment, not legal advice.
- **PassMark** (`benchmark-cpus.csv`): restricted — terms allow personal,
  non-commercial use within an organisation only; permission required for
  general publication or commercial reproduction. No redistribution licence.
- **TechPowerUp** (`gpu_1986-2026.csv`): restricted — robots.txt prohibits
  data mining, dataset creation and commercial use without prior written
  permission. No redistribution licence.
- **Intel ARK / AMD** (`intel-cpus.csv` / `amd-cpus.csv`): unknown — no reuse
  grant documented; Intel terms page 403-blocked, AMD copyright page has no
  data-reuse grant.
- **Geekbench** (`processor-benchmarks.csv`): unknown — Primate Labs legal
  pages unreachable (403/404). No conclusion drawn.
- **felixsteinke/cpu-spec-dataset**: AGPL-3.0 applies to the code; the dataset
  CSVs carry no data licence and their rights sit with the origin sites.
- **Per-spec-value attribution** (which source supports a stored value) is
  metadata and was persisted; it does **not** grant redistribution.

### TechPowerUp 44-legacy-value disposition

**Recommendation: restrict from future redistribution pending written
permission, while retaining the values in the database clearly flagged for
review.** No deletion: the values are factual, already stored, 16/44 were
cross-checked against NVIDIA official pages, and removal has no technical or
legal justification. Their provenance rows already carry the reuse restriction
in `license_notes`; any future redistribution must first obtain TechPowerUp's
written permission (`w1zzard@techpowerup.com`). This status is explicitly left
unresolved — nothing is represented as a granted right.

## 6. Gaming benchmark research outcome

No candidate dataset meets all reuse criteria (publisher, verifiable licence,
methodology, identifiable GPU/CPU + game + settings + metric, repeatable
structure). TechPowerUp review pages have the right shape but require written
permission; OpenBenchmarking remains 403-blocked (re-verified 2026-10-10), so
its data licence is unverifiable. **No gaming benchmark data was imported.**
Details in `gaming_benchmark_research.md`.

## 7. Pre/post database hashes and integrity

- Pre-load SHA-256: `0a53ba47e2a855e06790a0263611f120c247c82a0969c20edc4280bd92d6a917`
- Post-load SHA-256: `c0e843edece6a2999cf8376a782f1602262b092a6cf5f32cb4bce1763d10c3ce`
- The change is additive (2 source rows + 31,427 provenance rows) and is
  fully explained.
- `PRAGMA quick_check`: pre `ok`, post `ok`. `PRAGMA foreign_key_check`: empty.
- Pre-load backup:
  `data/backups/spectra-pre-batch009-base-provenance-20261010T083202Z.db`,
  on-disk pre-load hash `0a53ba47…`, `quick_check` `ok`. Backup is outside
  Git.
- Pre/post audit snapshots: `data/backups/batch009/pre_state.json` /
  `post_state.json` (outside Git).

## 8. Hardware and benchmark values did not change

The independent audit compared **every row of every data table**
(`hardware`, `cpu_specifications`, `gpu_specifications`, `benchmark_results`,
`external_identifiers`, `build_conversations`, `build_messages`) pre/post:
**zero changed data cells**. Only `sources` and `field_provenance` grew.

## 9. Backend / frontend tests

- Backend (`python -m pytest backend/app -q`): **584 passed**, 0 failed,
  0 skipped, 2 pre-existing warnings (Starlette `httpx` deprecation; anyio
  `BlockingPortal` alias), unrelated to this batch. Batch 009 adds 19 new
  tests in `backend/app/test_base_import_provenance.py`.
- Frontend (`node --test src/*.test.js`, mirroring `npm test`): **520 passed**,
  0 failed, 0 skipped, 0 todo.
- New test coverage: deterministic classification (verified/uncertain/
  unmatched/empty), multi-row vs multi-dataset ambiguity, duplicate
  prevention, idempotent re-runs, preservation of hardware specification
  values, license-note preservation, invalid table/field/status/hardware
  rejection, and the loader's "never persist multi-source as verified" rule.

## 10. Independent audit

`data/research/batch009/independent_audit.md` / `.json`. Verdict: **PASS**.
- 31,427 new provenance rows; 0 removed; all cross-checked (independent path)
  against the reconciliation CSV **and** the live cell value.
- 0 orphan hardware/source references, 0 invalid statuses/tables, no
  duplicates (total = distinct).
- No verified claim without supporting evidence; no restricted dataset
  imported (data tables untouched).
- No provenance claim was marked verified without exact value-level support.

## 11. Files changed / created

Backend (new):
- `backend/app/services/base_import_provenance.py`
- `backend/app/test_base_import_provenance.py`

Research (new, `data/research/batch009/`):
- `import_history.md`, `provenance_reconciliation.md`, `provenance_gaps.md`
- `provenance_reconciliation.json`, `evidence_reconciliation.csv`
- `source_license_assessment.md`, `source_license_assessment.json`
- `gaming_benchmark_research.md`
- `evidence.py`, `load_provenance.py`, `snapshot_state.py`, `compare_states.py`
- `final_report.md`, `independent_audit.md`, `independent_audit.json`

The `sources` table gained 2 rows and `field_provenance` gained 31,427 rows
(live DB, not files).

Deliberately **not** staged: `.opencode/`, `data/backups/`,
`data/spectra.db.bak-*`, `data/raw/`, the pre-existing untracked
`data/research/batch001/09_independent_audit.md`, and the audit state JSONs in
`data/backups/batch009/`.

## 12. `.opencode/` untouched

`.opencode/` was not modified, not staged, and contains only its original
contents. Confirmed before and after the batch.

## 13. Recommended Batch 010

1. **Schema follow-up (minimal migration)**: extend `field_provenance`/
   `provenance_service.VALID_FIELDS` to represent `benchmark_results` metrics
   (start with Geekbench `score`) so the 1,040 reconciled benchmark rows can
   be persisted — no redesign, rebuild of the table-name CHECK constraint and
   additive VALID_FIELDS entry only.
2. **Source identity correction decision**: reassign the 3,575
   `external_identifiers` currently labelled PassMark (`source_id 1`) to the
   correct Intel ARK / AMD sources (or document the reassignment) after a
   human decision.
3. **Licensing**: request written permission from TechPowerUp for the 44
   legacy GPU clock values (and, if desired, for a small attributed gaming
   benchmark set); re-check OpenBenchmarking from a real browser; obtain
   PassMark/Intel/AMD/Primate Labs confirmation before any redistribution.
4. **Frontend prerequisite** if gaming benchmarks are later permitted:
   extend `frontend/src/performance.js` filters and the GPU comparison
   benchmark panel beyond `Geekbench 7`.
5. Re-record access dates for all future evidence collection.