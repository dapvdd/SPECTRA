# Batch 011 — Source ID 1 Metadata Audit

Date: 2026-10-10

## 1. Scope

Batch 010 corrected the `external_identifiers` source associations away from
source 1. This audit verifies the current live relationships of source 1 and
decides whether its metadata (name/URL) remains accurate, using repository
evidence rather than the numeric id.

## 2. Live relationship verification

Query: `data/research/batch011/source_audit_query.py` (read-only).

References per source (live database):

| source | external_identifiers | field_provenance | benchmark_results |
|---|---:|---:|---:|
| 1 PassMark CPU benchmark catalog (benchmark-cpus.csv) | 0 | 546 | 0 |
| 2 Geekbench Browser - Geekbench 7 CPU | 0 | 1040 | 1040 |
| 3 TechPowerUp GPU Database | 0 | 12884 | 0 |
| 4 GPU Ark | 0 | 2573 | 0 |
| 5 Wikipedia (English) | 0 | 757 | 0 |
| 6 Intel ARK (archived via Wayback Machine) | 0 | 2 | 0 |
| 7 Unknown (placeholder) | 0 | 6 | 0 |
| 8 Intel ARK (intel-cpus.csv snapshot) | 2675 | 16276 | 0 |
| 9 AMD product specifications (amd-cpus.csv snapshot) | 900 | 1765 | 0 |

- Batch 010 confirmed: **0 external identifiers reference source 1**; the
  2,675 / 900 split to sources 8 / 9 is verified in the live database and by
  the independent audit.
- Source 1 is **not orphaned**: it still backs **546 `field_provenance` rows**,
  all `cpu_specifications` cells written by the Batch 009 base-import
  reconstruction (`base_clock_ghz` 47, `boost_clock_ghz` 300, `cores` 47,
  `socket` 58, `tdp_w` 49, `threads` 45). Those rows attribute the cells to
  the **`benchmark-cpus.csv`** PassMark catalog, which is exactly what source
  1's name says.
- No source row is referenced by a nonexistent id (0 orphan source
  references in `external_identifiers`, `field_provenance`, and
  `benchmark_results`).

## 3. Is the name/URL accurate?

`source 1 = "PassMark CPU benchmark catalog (benchmark-cpus.csv)"`,
`url = https://www.cpubenchmark.net/`.

- The batch 009 import-history reconstruction established that
  `benchmark-cpus.csv` is a snapshot scraped from `cpubenchmark.net`
  (documented in the `felixsteinke/cpu-spec-dataset` README and in
  `data/research/batch009/import_history.md`).
- Its remaining role is solely spec-cell provenance for cells whose value was
  reconciled to `benchmark-cpus.csv`. The name and URL match that role.

**Conclusion: the source-1 metadata is accurate; no relabel is justified.** The
inaccuracy reported in Batch 009 was that the *external identifiers* carried
source 1 — that has been corrected in Batch 010, and source 1 now correctly
describes only the PassMark `benchmark-cpus.csv` provenance it still owns.

## 4. Schema note

The `sources` table has only `id`, `name`, `url`. There are no `description`,
`license_notes`, or `attribution` columns, so the audit concerns name/URL only.
Licence facts live in `field_provenance.license_name`/`license_notes`, not on
`sources`.

## 5. Actions

- **No metadata change.** No database mutation was required or performed.
- **No regression test added**, because no correction was made (the batch
  instruction conditions that on "any metadata correction, if one is
  justified").
- Documented here for traceability; the live database hash is unchanged.