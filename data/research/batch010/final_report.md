# SPECTRA Batch 010 — Final Report

Date: 2026-10-10

## 1. Initial checkpoint and working-tree state

- Branch: `main`. Head at start: `8bddd7f feat(data): reconstruct base
  import provenance` (Batch 009) — verified present via `git log`.
- Working tree: clean apart from the known pre-existing untracked items
  (`.opencode/`, `data/backups/`, `data/raw/` (git-ignored), two legacy
  `data/spectra.db.bak-*` files, and the pre-existing untracked
  `data/research/batch001/09_independent_audit.md`).
- Database: `data/spectra.db`, pre-mutation SHA-256
  `c0e843edece6a2999cf8376a782f1602262b092a6cf5f32cb4bce1763d10c3ce`
  (matches the reported Batch 009 hash). `PRAGMA quick_check` = `ok`,
  `PRAGMA foreign_key_check` = empty.
- Pre-mutation row counts: hardware 5,239 (3,360 CPU / 1,879 GPU),
  cpu_specifications 3,360, gpu_specifications 1,879, benchmark_results 1,040,
  external_identifiers 3,575, sources 9, field_provenance 34,809,
  build_conversations 4, build_messages 4 — all matching the reported state.
- Backups and audit snapshots kept outside Git:
  `data/backups/spectra-pre-batch010-20261010T100451Z.db` (hash
  `c0e843ed…`, `quick_check` `ok`), `data/backups/batch010/pre_state.json`
  and `post_state.json`.

## 2. Workstream A — Benchmark provenance

**Design.** `field_provenance` was generalised (rather than a second parallel
system) with one nullable `benchmark_result_id` FK to `benchmark_results(id)`,
an extended `table_name` CHECK, a coherence CHECK, and two *partial* unique
indexes — one for specification provenance, one for benchmark provenance keyed
on the exact `benchmark_result_id`. This lets provenance reference an exact
benchmark record + metric (`score`), supports multiple sources per benchmark,
prevents orphans/duplicates, and stays generic for any future benchmark source
(no Geekbench-specific schema assumptions). Full design in
`benchmark_provenance_design.md`.

**Migration.** `add_field_provenance.py` gained an idempotent single-transaction
table-rebuild path (guarded on column presence, FK toggled around the
transaction, no-op on re-run); no new migration framework. Verified: all 34,809
existing spec rows preserved with `benchmark_result_id = NULL`.

**Backfill and exact reconciliation coverage.** Used the Batch 009 evidence
(`data/research/batch009/evidence_reconciliation.csv`, dataset `geekbench`,
status `verified`) = **1,040 rows**. Each was matched to a `benchmark_results`
row by `(hardware_id, score)` — deterministic because no `(hardware_id, score)`
or `(hardware_id, test_type, score)` duplicates exist in the dataset (0 groups).

- **Persisted: 1,040 benchmark provenance records** (all `evidence_status =
  verified`, `batch_no = 0`, `field_name = score`, `source_id = 2`
  Geekbench, `confidence` high, `source_reference =
  processor-benchmarks.csv#devices/id=<n>`, `match_method` records the
  devices/id + score reconcile, `test_type` captured in notes, license notes
  record the unknown Geekbench reuse status).
- Ambiguous / missing matches: 0 / 0. Re-run inserted 0 rows (idempotent).
- Dataset-level-only evidence was NOT asserted as per-record verified; every
  persisted row has an exact `devices/id` + score match.

## 3. Workstream B — External identifier source-1 audit

**Conclusion: the source-1 mapping is proven wrong for all 3,575 rows.**

| Identifier type | Rows | In expected artifact | On matching hardware | In PassMark URL ids |
|---|---:|---:|---:|---:|
| `intel_cpu_id` | 2,675 | 2,675 (`intel-cpus.csv` `CpuId`) | 2,675 Intel | 0 |
| `product_id_tray` / `boxed` / `mpk` | 620 / 215 / 65 | 900/900 (`amd-cpus.csv`) | 900 AMD | n/a |

- Identifiers outside the expected artifact: 0; hardware-manufacturer
  mismatches: 0; the PassMark catalog has no such columns and **none** of the
  2,675 Intel ids overlaps its URL `id=` namespace (intersection = 0).
- Evidence is value-level (independent of the numeric source id), encoded in
  the tested module `backend/app/services/identifier_source.py`.

**Correction applied** (`correct_identifier_sources.py`, guarded, single
transaction): verified the backup first, resolved target source ids by
*registered name*, required the exact patch composition (2,675 / 900),
per-row `UPDATE … WHERE id = ? AND source_id = 1` with hard expected row
count, duplicate-identity and row-count guards, rollback on any mismatch.

- **3,575 rows corrected**: 2,675 `intel_cpu_id` → source 8 (Intel ARK
  snapshot), 900 `product_id_*` → source 9 (AMD snapshot); source 1 now holds
  zero identifiers.
- Identifier values, types, and hardware associations unchanged; no rows
  added/removed; no identifiers deleted; no hardware entities recreated.
- Machine-readable patch: `id_audit_patch.csv` (+ `id_audit_results.json`);
  full details in `identifier_source_audit.md`.

## 4. Workstream C — Frontend benchmark filter audit

- Backend: `GET /hardware/{id}/benchmarks` returns all records (id, name, score,
  unit, test_type, source) with **no query-parameter filters**; hardware
  identity is in the path. Schema supports suite/source/test-type filtering.
- Frontend: client-side filter in `frontend/src/performance.js` hard-restricts
  to Geekbench 7 / points / single-core + multi-core; comparison panel is
  titled "Geekbench 7 scores". No user-facing filter control and no
  resolution/settings field exists (the schema has none).

**No frontend change made.** A suite/source filter UI is not justified while
only one benchmark family exists (it would return a fixed selection). Exact
dependency documented in `frontend_benchmark_filter_audit.md`: import licensed
benchmark data first → then expose optional API filters (`source_id`,
`benchmark_name`, `test_type`) → then generalise the hard-coded frontend
filter.

## 5. Workstream D — Permission and source research

Findings in `source_permission_research.md` (repository facts vs. pages
accessed 2026-10-10 vs. unresolved items):

- **PassMark** (`https://www.passmark.com/legal/disclaimer.php`,
  `https://www.cpubenchmark.net/`, accessed 2026-10-10): restricted — personal,
  non-commercial / within-organisation use only; permission required for
  publication or commercial reproduction.
- **TechPowerUp** (`https://www.techpowerup.com/robots.txt`, accessed
  2026-10-10): restricted — no data mining/dataset creation/commercial use
  without written permission (`w1zzard@techpowerup.com`).
- **Geekbench / Primate Labs** (`https://www.primatelabs.com/legal/` 403,
  `https://www.geekbench.com/legal/` 404, accessed 2026-10-10): terms not
  accessible → **unknown**, no inference drawn.
- **OpenBenchmarking** (403, re-verified): licence still unverifiable.
- **Intel / AMD exports**: unknown (no reuse grant documented).
- **Established permissive licences** (unchanged): GPU Ark CC BY 4.0, Wikipedia
  CC BY-SA 4.0 (share-alike handling still needs legal confirmation).
- **44 legacy TechPowerUp GPU clock values: retain flagged for review and
  restrict from future redistribution pending written permission** (no
  deletion; redistribution rights unresolved — nothing is claimed as granted).
- No permission request was sent. A draft template is provided in
  `permission_request_template.md`.
- No new gaming benchmark dataset with verifiable licence + adequate
  methodology + reproducible structure was found; position unchanged from
  batch 009.

## 6. Database hash and integrity

- **Pre-mutation SHA-256:** `c0e843edece6a2999cf8376a782f1602262b092a6cf5f32cb4bce1763d10c3ce`
- **Post-mutation SHA-256:** `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
- The change is fully explained: the `field_provenance` table rebuild
  (adds `benchmark_result_id` + extended CHECK + partial unique indexes),
  + 1,040 benchmark provenance rows, and the 3,575 identifier `source_id`
  label corrections.
- `PRAGMA quick_check`: pre `ok`, post `ok`. `PRAGMA foreign_key_check`:
  empty (pre and post).

### Before / after counts

| Table | Before | After |
|---|---:|---:|
| benchmark_results | 1,040 | 1,040 (values identical) |
| external_identifiers | 3,575 | 3,575 (only source_id labels corrected) |
| sources | 9 | 9 |
| field_provenance | 34,809 | 35,849 |
| hardware / cpu_specifications / gpu_specifications / build_* | unchanged | unchanged |

**Benchmark scores, test_type, unit, benchmark_name, source_id and recorded_at
are byte-identical before and after** (full-row diff), as are hardware,
specification and build tables. Gaming benchmark rows: 0.

Provenance by source after the batch: 1 → 546, 2 → 1,040 (new benchmark
provenance), 3 → 12,884, 4 → 2,573, 5 → 757, 6 → 2, 7 → 6, 8 → 16,276,
9 → 1,765. Statuses: verified 35,787 (34,747 spec + 1,040 benchmark),
excluded 58, unmatched 4.

## 7. Tests

- Backend: **612 passed**, 0 failed, 0 skipped, 2 pre-existing warnings
  (Starlette `httpx` deprecation; anyio `BlockingPortal` alias) — the same two
  warnings reported in batches 008–009. 28 new tests added
  (`test_benchmark_provenance.py`, `test_identifier_source.py`).
- Frontend: **520 passed**, 0 failed, 0 skipped, 0 todo.
- Docker: not run (no Docker runtime validation claimed).

New-test coverage: benchmark provenance references and referential integrity
(unknown/mismatched benchmark rejected, spec-table rejection of
`benchmark_result_id`), multiple sources per benchmark, duplicate prevention,
idempotent backfill, unknown/incomplete evidence metadata, benchmark
value/config preservation, orphan prevention (a benchmark with provenance
cannot be silently deleted), safe schema initialization/upgrade on an
existing database (column added, rows preserved, re-run no-op, cross-type rows
rejected), identifier source-decision logic (namespace evidence, no
numeric-id inference), identifier source-label update preserving values/links,
and duplicate-constraint behaviour.

## 8. Independent audit

`independent_audit.md` / `independent_audit.json` — verdict **PASS**, via a
separate comparison path (full-dump snapshot diff, not the migration/load
code): benchmark and identifier counts identical; full benchmark and
identifier value/association diffs clean; only the allowed 3,575 source
transitions; all 34,809 pre-existing provenance rows preserved; exactly 1,040
new verified benchmark provenance rows, all cross-checked against the
reconciliation evidence; 0 orphan, 0 duplicate references; 0 unsupported
provenance claims; no restricted dataset imported.

## 9. Files changed

Backend (modified):
- `backend/app/models/provenance.py` — `benchmark_result_id` + CHECKs + partial
  unique indexes + relationship.
- `backend/app/models/benchmark.py` — `field_provenance` relationship.
- `backend/app/services/provenance_service.py` — benchmark provenance contract
  + validation.
- `backend/app/services/base_import_provenance.py` — `VALID_FIELDS` alignment.
- `backend/app/migrations/add_field_provenance.py` — idempotent rebuild path.

Backend (new):
- `backend/app/services/identifier_source.py`
- `backend/app/test_benchmark_provenance.py`
- `backend/app/test_identifier_source.py`

Research (new, `data/research/batch010/`):
- `benchmark_provenance_design.md`, `identifier_source_audit.md`,
  `frontend_benchmark_filter_audit.md`, `source_permission_research.md`,
  `permission_request_template.md`
- `identifier_source_audit.py`, `correct_identifier_sources.py`,
  `load_benchmark_provenance.py`, `snapshot_state.py`, `compare_states.py`,
  `verify_state.py`
- `id_audit_results.json`, `id_audit_patch.csv`
- `final_report.md`, `independent_audit.md`, `independent_audit.json`

Live database changes: `field_provenance` 34,809 → 35,849 (+1,040) and the
table schema; `external_identifiers.source_id` for 3,575 rows. No `sources`
rows added or removed.

**Not staged:** `.opencode/`, `data/backups/` (including the batch010 pre/post
snapshots and the pre-mutation DB backup), `data/spectra.db.bak-*`, `data/raw/`,
and the pre-existing untracked `data/research/batch001/09_independent_audit.md`.

## 10. `.opencode/` untouched

`.opencode/` was not modified, staged, or committed; it remains untracked with
its original contents.

## 11. Recommended Batch 011

1. **Frontend/API benchmark filter readiness** (the deferred dependency):
   optionally expose query filters on `GET /hardware/{id}/benchmarks`
   (`source_id`, `benchmark_name`, `test_type`) and generalise the
   Geekbench-7 hard filter in `performance.js` — but only in step with actual
   licensed benchmark data.
2. **Source identity cleanup follow-through**: source 1 (PassMark) still backs
   546 specification provenance records from batch 009 (correctly, they are
   `benchmark-cpus.csv` matches) but now holds zero identifiers; consider
   whether the `sources.name` for id 1 should be clarified so it no longer
   reads as "the" CPU source.
3. **Permissions**: send (if the user requests) the drafted permission request
   to TechPowerUp for the 44 legacy GPU clocks and PassMark/Primate Labs for
   their data; manual review of Primate Labs and OpenBenchmarking terms from a
   real browser.
4. **Gaming benchmarks**: unchanged blocker — obtain a licensed dataset with
   adequate methodology before any import; treat as gated on the batch-009
   criteria.
5. **Cover the batch-009 base-import multi-source (`uncertain`) cells**: 1,378
   cells and 1,726 unmatched/identity gaps remain only in artifacts; decide
   whether a second-source resolution pass is worth pursuing.