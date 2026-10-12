# Batch 015 — Design and additive migration

## Problem

`field_provenance` already recorded, per field/benchmark, the source id, a
source URL, an evidenced value, an evidence status, an optional licence name
and an optional attribution. The `sources` registry, however, held only `name`
and `url`, so the **redistribution status** of a source — the very thing a
transparency surface needs — had nowhere to live. 32,519 provenance rows carry
no `license_name`.

## Smallest safe additive change

Add eight **nullable** columns to `sources`:

| Column | Type | Purpose |
| --- | --- | --- |
| `publisher` | `VARCHAR(200)` | who published the data |
| `description` | `TEXT` | what the source is |
| `license_name` | `VARCHAR(100)` | e.g. `CC BY-SA 4.0` |
| `license_url` | `VARCHAR(500)` | terms/licence reference |
| `license_status` | `VARCHAR(20)` | `clear`/`unknown`/`restricted`/`unresolved` |
| `terms_notes` | `TEXT` | why that status was assigned |
| `attribution` | `TEXT` | required attribution text |
| `retrieved_on` | `DATE` | when the terms were checked |

### Why this shape

- **Additive only.** `ALTER TABLE ... ADD COLUMN` never rewrites existing rows;
  a database that already has the columns is left untouched. No source id is
  remapped, nothing is deleted or renamed.
- **Nullable.** An unknown value stays `NULL` and is reported as unknown — the
  batch never fabricates attribution.
- **No `CHECK` constraint.** A `CHECK` on an added column is inconsistent
  between migrated and freshly-created databases; `license_status` membership is
  enforced in code (`models/source.py` `LICENSE_STATUSES`,
  `source_registry.py`, tests) instead.
- **No table rebuild.** Rebuilding `sources` would risk the foreign keys from
  `field_provenance.source_id` and `benchmark_results.source_id`; adding columns
  avoids that entirely.

### Implications

- Fresh databases created by `Base.metadata.create_all` get the columns from the
  updated ORM model automatically.
- Existing databases require the one-time migration
  `backend/app/migrations/add_source_license_metadata.py` (idempotent,
  `--dry-run`, `--database`). It was rehearsed on a disposable copy **before**
  being applied to the live database, which was backed up first
  (`data/backups/spectra.db.batch015-20261012T062934Z.bak`).
- The read API falls back to `source_registry.py` when a column is `NULL`, so an
  un-migrated/unspecified registry still reports the register rather than
  nothing.

### Seeding

`source_registry.py` holds the evidence-based metadata for the nine sources and
`seed_source_metadata(session)` writes it **fill-only**: a non-`NULL` column is
never overwritten, no row is created/deleted/renamed. Applied to the live DB it
reported `{'updated_rows': 9, 'updated_fields': 55, 'unmatched': []}`.

## Read-only API

| Endpoint | Returns |
| --- | --- |
| `GET /sources` | every source with licence metadata + provenance usage counts |
| `GET /sources/{id}` | one source; 404 if unknown |
| `GET /hardware/{id}/provenance` | per-spec-field provenance + benchmark provenance + honest summary; 404 if unknown |
| `GET /benchmarks/{id}/provenance` | per-benchmark metric provenance; 404 if unknown |

- **No N+1.** Usage counts use grouped aggregates; provenance uses
  `selectinload(...source)`. A test asserts the statement count for a hardware
  lookup stays constant as the record count grows.
- **Backward compatible.** No existing endpoint changed shape; the pre-existing
  `/hardware/{id}/benchmarks` response contract is asserted unchanged by both a
  unit test and the independent audit.
- **Honest statuses.** A field is `verified` / `uncertain` / `excluded` /
  `unmatched` from its records, `unattributed` when a value exists with no
  record, and `unavailable` when neither value nor record exists.

## Frontend

- A compact, native `<details>` source disclosure sits **beneath** each spec
  value that has provenance (or is unattributed). It is visually secondary,
  keyboard operable, and wraps long names/URLs (`overflow-wrap: anywhere`).
- Benchmark evidence shows its source and licence status in a footnote under the
  performance section and the benchmark comparison, reusing the existing
  verified-data separation.
- Comparison decision support gains a compact "Evidence sources" block per side
  (specifications vs benchmarks), and states plainly when a value has no
  recorded source.
