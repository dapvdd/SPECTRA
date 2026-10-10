# Batch 009 — Provenance Gaps After Reconstruction

Date: 2026-10-10

## 1. Remaining coverage gaps (measured from the live database)

Total populated cells across `hardware`, `cpu_specifications`,
`gpu_specifications`, `benchmark_results`: **53,230** (52,708 distinct
field-level cells after collapsing Geekbench rows that share a hardware).

After Batch 009, **34,747 distinct cells carry verified field-level
provenance** (up from 3,320 before the batch). Remaining uncovered: **17,961
cells**, of which:

| Gap bucket | Cells | Why it remains open |
|---|---:|---|
| `hardware.name / manufacturer / type` identity | 15,717 | `field_provenance` and `provenance_service.VALID_FIELDS` deliberately restrict to enrichable fields; identity provenance is captured for every entity in `evidence_reconciliation.csv` (entity-level) but is not persisted. |
| `cpu_specifications` cells (unmatched/uncertain) | 1,726 | Value matches no single dataset (e.g. AMD boost clocks read from a drifted column, or values shared by two datasets); stored only in artifacts. |
| `benchmark_results.score` | 518–1,040 | The schema's `table_name` CHECK constraint only allows `hardware/cpu_specifications/gpu_specifications`; benchmark provenance cannot be represented. Row-level provenance exists (`source_id` = 2 = Geekbench) and the artifact reconciles 1,040/1,040. |

(The distinct-cell collapse treats AMD Ryzen 7 7840U's three multi-core scores
as one `(hardware, score)` cell; all three rows are reconciled individually in
the CSV and none is persisted for the schema reason above.)

## 2. Source-identity inconsistency recorded, not fixed

- All 3,575 `external_identifiers` carry `source_id` 1 ("PassMark CPU
  benchmark catalog"). The evidence shows they were produced by the
  `intel-cpus.csv` (Intel ARK) and `amd-cpus.csv` (AMD) imports. The stored
  label is therefore inaccurate at source level.
- The `sources` row with id 6 ("Intel ARK (archived via Wayback Machine)")
  refers to the batch-001 cross-check usage, distinct from the base import's
  `intel-cpus.csv` snapshot; both are kept as separate sources to preserve
  their different evidence paths.

## 3. License/attribution metadata gaps

- None of the base-import sources has an established redistribution licence
  (details in `source_license_assessment.md`). Each persisted provenance row
  records the unresolved/restricted reuse status in `license_notes`.
- No attribution string is verifiable for any base-import source, so
  `attribution` is NULL. Access dates are NULL (no recorded access dates and
  they are not invented).

## 4. Schema limitation documented (no schema change made)

`field_provenance` cannot safely represent:
- benchmark/metric provenance (benchmark_results not in the CHECK constraint);
- the `partial` distinction (multi-source) except via `uncertain`;
- identity-field provenance (name/manufacturer/type not in VALID_FIELDS).

Batch 009 made **no schema change**. A minimal follow-up migration is proposed
for Batch 010 (see `final_report.md`) to extend provenance to
`benchmark_results` and, if desired, identity fields, without an
unreviewed redesign.

## 5. What is now queryable that was not before

- Which base-import dataset supports each CPU/GPU specification cell
  (`field_provenance` with `batch_no = 0`).
- Which artifact file and entity key (in `source_reference`) and which
  confidence support the claim.
- Which values could not be attributed to a unique dataset (`uncertain`) or to
  any dataset (`unmatched`) — via the reconciliation CSV, kept outside the
  database.