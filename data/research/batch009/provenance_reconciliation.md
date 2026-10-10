# Batch 009 — Provenance Reconciliation

Date: 2026-10-10

This document explains the per-cell reconciliation performed by `evidence.py`
and the exact numbers. It accompanies the machine-readable
`evidence_reconciliation.csv` (per-cell) and `provenance_reconciliation.json`
(summary + artifact hashes).

## 1. Rule applied to every populated cell

> A source being plausible is not proof that a particular database value came
> from that source.

- `verified`: the stored value equals the normalized value read from the
  base-import artifact in **exactly one** documented dataset, with at least
  one source row carrying that value. Confidence `high` when exactly one
  source row matches; `medium` when several rows in the same dataset carry the
  same value (dataset identity certain, exact source row ambiguous).
- `uncertain`: the value is present in **two or more** distinct datasets.
  Source identity is ambiguous at value level; nothing is persisted as
  verified.
- `unmatched`: the value matches no documented dataset. Kept in artifacts
  only.
- `excluded`/`invalid_reference`: not used by this batch (the vocabulary is
  preserved for the schema, which supports `verified | uncertain | excluded |
  unmatched`).

## 2. Status translation

The task brief defined five labels: `verified`, `partial`, `unknown`,
`excluded`, `unmatched`. The schema's stored statuses are `verified`,
`uncertain`, `excluded`, `unmatched` (CHECK constraint in
`field_provenance`). Translation used in this batch:

| Brief label | Stored status | Used for |
|---|---|---|
| verified | `verified` | unique-dataset exact value match |
| partial | `uncertain` | value present in ≥2 datasets (source identity known only partially) |
| unknown | (kept in artifacts) | no dataset matches; schema has no safe value to store |
| excluded | `excluded` | not used this batch (no deliberate exclusions were made) |
| unmatched | `unmatched` | not persisted; kept in artifacts as `unmatched` |

`partial` was mapped to `uncertain` because the schema has no `partial`
status; a multi-dataset value is exactly that case (source not individually
resolvable). No `partial`/`unknown`/`unmatched` record was stored as
`verified`.

## 3. Reconciliation scope

The reconciliation covers every populated **base-import-writable** field:
`hardware.{release_date, architecture}`, `hardware.{name, manufacturer,
type}` (identity), all seven `cpu_specifications` columns, the eight
`gpu_specifications` columns written by the base importer
(`memory_bus_width_bits` is excluded: the base importer never wrote it and
all 1,443 values carry batch-006 GPU Ark provenance), and every
`benchmark_results` score row.

## 4. Results (pre-existing verified provenance = 3,320 at start)

- Reconciliation rows written: **51,787** (including identity cells and 1,040
  benchmark rows).
- Per-cell outcome: **verified 47,325 | uncertain 2,251 | unmatched 2,211**.

Verified breakdown by dataset (all rows, incl. identity):

| dataset | verified rows | artifact |
|---|---|---|
| intel | 16,276 cpu_spec + 2,659×3 identity | intel-cpus.csv |
| amd | 1,765 cpu_spec + 363×3 identity | amd-cpus.csv |
| passmark | 546 cpu_spec + 47×3 identity | benchmark-cpus.csv |
| techpowerup | 12,854 gpu_spec/hardware + 1,879×3 identity | gpu_1986-2026.csv |
| geekbench | 1,040 benchmark scores | processor-benchmarks.csv |

## 5. Persisted records (Phase C load)

Only cells that were `verified`, persistable (field in `provenance_service.
VALID_FIELDS`), and **not already covered** by an existing verified
provenance record were loaded via `insert_provenance_record` (idempotent):

| dataset | new `field_provenance` rows | confidence |
|---|---|---|
| intel | 16,276 | high |
| amd | 1,765 | high |
| passmark | 546 | high/medium |
| techpowerup | 12,840 | high/medium |
| **total** | **31,427** | 30,619 high / 808 medium |

- 14 TechPowerUp cells were already covered by batch-005 provenance and were
  skipped.
- Repeated runs insert 0 rows (idempotent).
- No hardware, specification, benchmark, external-identifier or build value
  was modified (see `independent_audit.md` for the cell-level proof).

## 6. Database coverage delta

- Before Batch 009: 3,320 verified field-level rows (enrichment batches
  001–006 only).
- After Batch 009: 34,747 verified rows (3,320 enrichment + 31,427
  base-import), of which 34,747 distinct populated cells are covered.
- Remaining uncovered cells: 17,961 (see `provenance_gaps.md`).