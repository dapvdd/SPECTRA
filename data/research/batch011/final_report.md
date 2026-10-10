# SPECTRA Batch 011 — Final Report

Date: 2026-10-10

## 1. Initial checkpoint and working-tree state

- Branch `main`. Head at start: `f403b43 feat(data): add benchmark provenance
  support` (Batch 010) — verified via `git log`.
- Working tree: clean except the known pre-existing untracked items
  (`.opencode/`, `data/backups/`, `data/raw/` (git-ignored), two legacy
  `data/spectra.db.bak-*` files, and the pre-existing untracked
  `data/research/batch001/09_independent_audit.md`).
- Database: `data/spectra.db`, SHA-256
  `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
  (matches the reported Batch 010 hash). `quick_check` = `ok`,
  `foreign_key_check` = empty.
- Counts: hardware 5,239 (3,360 CPU / 1,879 GPU),
  cpu_specifications 3,360, gpu_specifications 1,879, benchmark_results 1,040,
  external_identifiers 3,575 (2,675 → source 8, 900 → source 9; source 1 has
  none), sources 9, field_provenance 35,849, build_conversations 4,
  build_messages 4 — all matching the reported state.
- Batch 010's final report and independent audit were inspected
  (`data/research/batch010/`).

## 2. Workstream A — Optional benchmark API filters (implemented)

`GET /hardware/{hardware_id}/benchmarks` gained three **optional** query
parameters, applied as parameterised ORM `WHERE` clauses with AND semantics:

| Parameter | Type | Behaviour |
|---|---|---|
| `source_id` | int | exact `benchmark_results.source_id` match |
| `benchmark_name` | str | exact `benchmark_results.benchmark_name` match |
| `test_type` | str | exact `benchmark_results.test_type` match |

Examples (live data):
- `GET /hardware/1508/benchmarks` → 2 rows (all).
- `GET /hardware/1508/benchmarks?source_id=2` → 2 rows.
- `GET /hardware/1508/benchmarks?test_type=single-core` → 1 row.
- `GET /hardware/1508/benchmarks?benchmark_name=Geekbench%207&test_type=multi-core` → 1 row.
- `GET /hardware/1508/benchmarks?source_id=1` (unknown filter value) → `200 []`.
- `GET /hardware/999999/benchmarks` → `404 {"detail":"Hardware not found: 999999"}`.
- `GET /hardware/1508/benchmarks?source_id=abc` → `422` (FastAPI validation).

Design notes:
- Backward compatible: requests without parameters produce byte-identical
  results to before (same rows, same `id` order, same response shape
  `list[BenchmarkResultResponse]`).
- Follows the existing project filter convention (`GET /hardware?type=…`):
  an unknown filter value returns an **empty list**, not a 404; the hardware
  path is the only not-found condition (404).
- `source` is loaded with `selectinload` (no join), so no duplicate rows.
- No raw SQL; user input never interpolated.
- Only existing fields/relationships used; no invented suites or
  configurations. `benchmark_name` is a reliable `NOT NULL` database column,
  so it is used directly (no mapping invented).

Files: `backend/app/main.py` (route), `backend/app/services/benchmark_service.py`
(service), `backend/app/test_benchmark_api_filters.py` (14 new API tests).

## 3. Workstream B — Frontend benchmark generalisation (deferred, documented)

No frontend change. The Geekbench-7 filter in `frontend/src/performance.js` is
retained because the metric model keys `single_core`/`multi_core` by test type
with **no suite dimension**; removing the `benchmark_name === "Geekbench 7"`
guard would, once a second suite exists, silently merge unrelated suites' scores
into one metric (`isEarlierResult` keeps an arbitrary lowest-`id` record). The
response contract does carry `source`/`benchmark_name`/`test_type`, but the
metric model cannot use them safely without a suite-scoped redesign, and the
current dataset has exactly one suite, so a suite filter would present a single
fixed choice. Exact prerequisites (licensed second dataset → suite-scoped
metric model → use the new API filters → then UI) are recorded in
`frontend_benchmark_filter_audit.md`.

The source name is already displayed per record in `App.jsx`, and empty/
loading/error states already follow existing conventions.

## 4. Workstream C — Source ID 1 metadata audit

Verified live (`source_audit_query.py`): source 1
(`PassMark CPU benchmark catalog (benchmark-cpus.csv)`, `cpubenchmark.net`)
now has **0 external identifiers**, **546 `field_provenance` rows** (all
`cpu_specifications` base-import cells reconciled to `benchmark-cpus.csv`), and
**0 benchmark rows**. It is not orphaned, and its name/URL accurately describe
its remaining role. **No relabel is justified; metadata unchanged; no database
mutation.** (`sources` has only `id`/`name`/`url` — no description/licence
columns.) Details in `identifier_source_audit.md`.

## 5. Workstream D — Licensing status (preserved)

No new legal action; no permission requests sent; no restricted dataset
imported; no gaming benchmark data added. Standing findings (from
`data/research/batch010/source_permission_research.md`, accessed 2026-10-10)
are unchanged:
- **PassMark** and **TechPowerUp**: restricted — further permission review
  required before publication/redistribution.
- **Geekbench / Primate Labs**, **Intel**, **AMD**: reuse permission
  unresolved (terms inaccessible / no grant documented).
- **GPU Ark CC BY 4.0** and **Wikipedia CC BY-SA 4.0** remain the only
  established reuse licences (share-alike handling still needs confirmation).
- The **44 legacy TechPowerUp GPU clock values** remain in the database,
  flagged, and must not be deleted or redistributed in this batch (they were
  not touched).

## 6. Database hash and integrity

- **Unchanged**: `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
  (identical to the Batch 010 checkpoint). No database mutation was required or
  performed by this batch, so the hash must and does remain the same.
- `PRAGMA quick_check` = `ok`; `PRAGMA foreign_key_check` = empty.
- Benchmark rows, external identifiers, provenance and sources are
  byte-identical to the checkpoint (full-table diff: no changed tables).
- Benchmark data unchanged: 520 Geekbench 7 single-core + 520 multi-core;
  sample scores intact (hardware 1508: 695.0 single-core, 2005.0 multi-core).

## 7. Tests

- Backend: **626 passed**, 0 failed, 0 skipped, 2 pre-existing warnings
  (Starlette `httpx` deprecation; anyio `BlockingPortal` alias) — same two
  warnings as batches 008–010. Batch 011 adds **14 API filter tests**.
- Frontend: **520 passed**, 0 failed, 0 skipped, 0 todo (unchanged; no
  frontend code change).
- Docker: not run (no runtime validation claimed).

New tests cover: no-filter backward compatibility; each filter independently
(`source_id`, `benchmark_name`, `test_type`); exact-match-only name filtering;
combined filters with AND semantics; contradictory combined filters → empty;
unknown source/name → empty list; NULL-source exclusion; non-integer
`source_id` → 422; hardware-not-found with filters → 404; duplicate-free
responses; unchanged response shape.

## 8. Independent audit

`data/research/batch011/independent_audit.md` / `.json` — verdict **PASS**,
via a path separate from the HTTP layer (direct service calls + full-table
snapshot comparison against the Batch 010 checkpoint): DB SHA unchanged;
`quick_check` ok; `foreign_key_check` empty; no table changed; filters
independently re-derived correct against live data; no duplicates.

## 9. Files changed

Modified:
- `backend/app/main.py` — optional query params on the benchmarks route.
- `backend/app/services/benchmark_service.py` — optional filters (AND,
  parameterised ORM, `selectinload`).

New:
- `backend/app/test_benchmark_api_filters.py` — 14 API-level filter tests.
- `data/research/batch011/frontend_benchmark_filter_audit.md`
- `data/research/batch011/identifier_source_audit.md`
- `data/research/batch011/final_report.md`
- `data/research/batch011/independent_audit.md`
- `data/research/batch011/independent_audit.json`
- `data/research/batch011/independent_audit.py`
- `data/research/batch011/verify_filters.py`
- `data/research/batch011/source_audit_query.py`

Live database: **no changes** (hash unchanged).

**Not staged:** `.opencode/`, `data/backups/`, `data/spectra.db.bak-*`,
`data/raw/`, and the pre-existing untracked
`data/research/batch001/09_independent_audit.md`.

## 10. `.opencode/` untouched

`.opencode/` was not modified, staged, or committed; it remains untracked with
its original contents.

## 11. Recommended Batch 012

1. **Frontend benchmark model** (only if licensed data is added): introduce a
   suite dimension in `performance.js` and use the new `source_id` /
   `benchmark_name` / `test_type` API filters; do not add a suite selector
   while only one suite exists.
2. **Source metadata**: consider adding optional `description` / licence
   columns to `sources` (a schema change) so licence/attribution facts can live
   next to the source rather than only on `field_provenance`; would need its
   own migration + tests.
3. **Licensing**: if the user wants, send the drafted permission requests
   (TechPowerUp `w1zzard@techpowerup.com`, PassMark, Primate Labs) and
   manually review Primate Labs / OpenBenchmarking terms from a browser.
4. **Gaming benchmarks**: still gated on a licensed dataset with adequate
   methodology; no import until then.
5. **Remaining base-import provenance gaps** (1,378 multi-source `uncertain`
   cells and 1,726 unmatched/identity cells) remain artifact-only; decide
   whether a targeted second-source resolution pass is worthwhile.