# Batch 010 — Benchmark Provenance Design

Date: 2026-10-10

## 1. Problem

- 1,040 Geekbench 7 `benchmark_results` rows exist. Batch 009 reconciled all
  1,040 to unique rows of `processor-benchmarks.csv` (device ids + exact
  scores) but could not persist that provenance: the `field_provenance`
  schema restricted `table_name` to
  `hardware | cpu_specifications | gpu_specifications`.
- Pushing benchmark provenance into `field_provenance` verbatim (as a
  hardware-level "field") would misrepresent a benchmark *record*, because the
  natural identity of a benchmark result is the benchmark row itself, not `(hardware,
  column)`. The existing unique constraint was keyed on `hardware_id` and would
  have collapsed two identical-score benchmark rows on the same hardware into
  one provenance identity.

## 2. Chosen design: generalise `field_provenance` with a benchmark key

Instead of a second parallel provenance system, the existing `field_provenance`
is extended with one nullable key and two partial unique indexes:

- `benchmark_result_id INTEGER NULL REFERENCES benchmark_results(id)`.
- `table_name` CHECK constraint extended to allow `'benchmark_results'`.
- Coherence CHECK: a row is either
  - specification provenance (`benchmark_result_id IS NULL` and
    `table_name != 'benchmark_results'`), or
  - benchmark provenance (`benchmark_result_id IS NOT NULL` and
    `table_name = 'benchmark_results'`).
- Two **partial unique indexes** replace the single composite unique
  constraint, so each keying model is guarded independently and an exact
  benchmark record (not a hardware+column pair) is the identity for benchmark
  provenance:
  - `uq_field_provenance_identity` (WHERE `benchmark_result_id IS NULL`) on
    `(hardware_id, table_name, field_name, source_id, evidenced_value,
    evidence_status)`;
  - `uq_field_provenance_benchmark_identity` (WHERE `benchmark_result_id IS
    NOT NULL`) on `(benchmark_result_id, field_name, source_id,
    evidenced_value, evidence_status)`.
- Index on `benchmark_result_id` for lookups and orphan checks.

Why this shape:
- **References an exact benchmark record and metric**: the `score` metric of a
  specific `benchmark_results.id`.
- **One or more provenance records per benchmark** (multiple sources) is
  naturally supported because `(benchmark_result_id, field_name, source_id, ...)`
  is only unique per source.
- **Referential integrity**: `benchmark_result_id` is a hard FK; with
  enforcement on, a benchmark row carrying provenance cannot be deleted (no
  orphan provenance), and a provenance row cannot point at a missing benchmark.
- **Generic**: `benchmark_name`, `test_type`, `unit` stay on `benchmark_results`;
  the provenance layer only names the metric (`score`) and therefore supports
  any current/future benchmark source without Geekbench-specific assumptions.
- **Reuses the evidence vocabulary** (`evidence_status`, `confidence`,
  `license_name`, `license_notes`, `attribution`, `access_date`,
  `source_reference`, `match_method`, `batch_no`, `notes`) rather than
  duplicating a second system.

The service contract in `provenance_service.py`:
- `VALID_FIELDS` gains `benchmark_results: {"score"}`.
- `insert_provenance_record` raises `ProvenanceValidationError` when
  `benchmark_result_id` is missing for `benchmark_results`, present for
  specification tables, references an unknown benchmark, or references a
  benchmark whose `hardware_id` does not match the row's `hardware_id`.

## 3. Schema migration

`backend/app/migrations/add_field_provenance.py` remains the single, idempotent
migration (no new framework). It now has two paths:
- Fresh database: creates the table from the model (already new schema).
- Existing table without `benchmark_result_id`: one-transaction rebuild —
  `CREATE TABLE field_provenance_new`, `INSERT ... SELECT <18 cols>, NULL`,
  drop + rename, recreate the six indexes, `PRAGMA foreign_keys=OFF/ON`
  around the transaction. Re-running is a no-op (guarded on column presence).

Verified on a live copy: 34,809 existing spec rows are preserved byte-for-byte
with `benchmark_result_id = NULL`; the CHECK constraints reject cross-type rows.

## 4. Backfill and exact reconciliation coverage

- Evidence: `data/research/batch009/evidence_reconciliation.csv`, dataset
  `geekbench`, status `verified` — **1,040 rows**.
- Match: each evidence row is joined to `benchmark_results` by
  `(hardware_id, score)`. Verified first that no `(hardware_id, score)` or
  `(hardware_id, test_type, score)` duplicates exist in the current dataset,
  so the match is exact and unambiguous. The loader requires exactly one match
  and otherwise reports (0 ambiguous, 0 missing observed).
- Persisted fields per record: `hardware_id`, `benchmark_result_id`,
  `table_name='benchmark_results'`, `field_name='score'`, `source_id` = the
  Geekbench source, `evidence_status='verified'`, `batch_no=0`, `confidence`
  from the reconciliation, `source_reference =
  processor-benchmarks.csv#devices/id=<n>` (the exact catalog row), the
  benchmark's `test_type` in notes, and license notes that record the unknown
  Geekbench reuse status.
- Idempotency: a second backfill run inserted 0 rows. No benchmark score,
  `test_type`, `unit`, `source_id` or `recorded_at` value changed.

The dataset-level-vs-record-level distinction is preserved: every persisted
record is supported by an exact `devices/id` + score match; nothing is claimed
as verified from a dataset-level association only.

## 5. Respecting the task constraints

- Benchmark schema and application behavior preserved (`benchmark_results`
  untouched; API shape unchanged).
- No Geekbench-specific assumptions in the schema (only the generic metric
  `score` is named).
- No broad/unrelated schema change.
- No gaming benchmark data added.
- No restricted dataset imported (provenance metadata only).