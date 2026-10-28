# SPECTRA Data Provenance Report

**Generated**: 2026-10-28
**Verified against**: local copy of deployed SPECTRA database + `field_provenance` table + `sources` table.

---

## 1. Provenance architecture

SPECTRA records provenance at **field level** in `field_provenance`:

- `(hardware_id, table_name, field_name, source_id, evidenced_value, evidence_status)`
- `evidence_status ∈ {verified, uncertain, excluded, unmatched}`
- `confidence ∈ {high, medium, rejected, None}`
- Each row records `source_url`, `license_name`, `license_status`, `access_date`,
  `match_method`, `batch_no`, `recorded_at`, `notes`.
- Text `source_reference` and `attribution` capture the exact reference.

**Two provenances keying models share one vocabulary** (spec fields vs benchmark
metrics), enforced by a CHECK constraint.

## 2. Numeric findings from the deployed DB

| Measure | Value |
|---|---|
| field_provenance rows | 36,946 |
| sources | 9 |
| hardware covered | 5,360 / 5,380 |
| hardware uncovered | 20 |
| benchmark results covered | 1,040 / 1,040 |
| confidence high | 34,523 |
| confidence medium | 2,361 |
| confidence None | 60 |
| confidence rejected | 2 |
| evid_status excluded | 58 |
| evid_status unmatched | 4 |

### 2.1 Provenance by (table, status)

| Table | verified | excluded | unmatched |
|---|---:|---:|---:|
| benchmark_results | 1,040 | 0 | 0 |
| cpu_specifications | 19,515 | 0 | 0 |
| gpu_specifications | 12,687 | 50 | 4 |
| hardware | 3,642 | 8 | 0 |

### 2.2 Source attribution density

- 9 sources; all 3 main datasets (PassMark, TechPowerUp, Wikipedia/GPU Ark)
  present with licence metadata.
- 4 sources marked `unknown` licence (Geekbench, Intel ARK, others); 1
  `unresolved`; `data/research/batch009/source_license_assessment.json` +
  `batch009/source_license_assessment.md` carry the assessment trail.

## 3. What provenance can and cannot prove

**Can prove**: which source, which URL, which licence, which confidence, which
batch, which evidence status backs a given field or benchmark record; whether a
value is verified vs uncertain vs unmatched vs excluded; which hardware rows
have *no* provenance at all.

**Cannot prove**: absolute truth, measured performance on workloads we do not
store, a benchmark we deliberately do not collect (GPU). Provenance here is
designed to *decline* to fabricate: `excluded`/`unmatched` statuses exist
specifically so a value is never silently assigned and never silently removed.

## 4. Known provenance-quality limits

1. **20 hardware rows have no provenance at all** (`hardware` table, status of
   any record `None`). They are reported honestly as unattributed.
2. **8 `hardware`-table rows marked `excluded`** and **4 `gpu_specifications`
   rows `unmatched`**: these are candidate records that were reviewed and
   deliberately not given confirmed specification evidence. They remain in the
   catalog with explicit status rather than vanishing.
3. **2 `rejected` confidence values** and **60 NULL-confidence** rows: these
   are edge cases from Batch 007 (semantic corrections) / Batch 014 that
   should be re-audited but are not silently dropped (see
   `data/research/batch007` and `batch014`).
4. **Geekbench Browser (`unknown` licence)** backs all 1,040 benchmark
   records. The Geekbench dataset's licence is not `clear`; the project tracks
   this honestly but should get explicit permission (see
   `data/research/batch010/source_permission_research.md`, which documents why
   permission was not obtained and what the fallback is).
5. **GPU benchmarks absent by design** (0 rows). Not a provenance failure; a
   documented product decision.

## 5. Provenance API surface

Verified live:

| Endpoint | Returns |
|---|---|
| `GET /hardware/{id}/provenance` | field-level evidence per hardware |
| `GET /benchmarks/{id}/provenance` | evidence for a benchmark record |
| `GET /sources` / `GET /sources/{id}` | source metadata incl. licence + attribution |

- Missing hardware → 404.
- Empty provenance → `unattributed`/`unavailable` (no fabricated attribution).

## 6. Audit trail of batches

`data/research/batch001..016` contain, per batch: source dumps, candidate lists,
evidence tables, database patches, apply results, independent audits, and
post-apply verification. This yields a replayable provenance chain: each
`field_provenance.batch_no` maps to a batch directory holding the raw evidence.
`batch009` reconstructed base-import provenance; `batch010` rebuilt
identifier/source mapping; `batch014` expanded modern CPU catalog with
provenance; `batch015` added source licence transparency columns.

## 7. Recommendations

1. **Re-audit the 2 `rejected`-confidence and 60 NULL-confidence rows** — decide
   `verified`/`uncertain`/`excluded` explicitly rather than leaving NULL.
2. **Reconcile the 20 unattributed hardware rows** — either source them or move
   them to a clearly-labeled "unattributed" state with `evidence_status` set so
   they are not counted as validated without provenance.
3. **Track source access date/robots.txt compliance** in `sources.terms_notes`
   for every future import (see `DATABASE_EXPANSION_PIPELINE.md`).
4. Keep **licence status honest**: `unknown`/`restricted`/`unresolved` must
   never be upgraded to `clear` without evidence; the pipeline must record the
   evidence for the licence itself.
5. **Do not confuse laptop and desktop GPU performance.** The current schema has
   no segment/form-factor column; before any mobile GPU import, add the column
   and backfill (see audit fix list).
