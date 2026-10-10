# Batch 010 — External Identifier Source-1 Audit

Date: 2026-10-10

## 1. Question

Batch 009 reported that all 3,575 `external_identifiers` rows carry
`source_id` 1, registered as "PassMark CPU benchmark catalog
(benchmark-cpus.csv)". Batch 009's import-history reconstruction suggested the
identifiers actually originated in the Intel ARK and AMD specification exports
used for the base CPU import. This batch determines, with independent value
evidence, whether that label is wrong.

## 2. Method (not inference from the numeric id)

The audit script `identifier_source_audit.py`:
1. Reads every `external_identifiers` row and its owning hardware
   (`hardware_id`, `hardware.name`, `hardware.manufacturer`).
2. Builds the *name spaces* from the actual source artifacts present on disk:
   - `intel-cpus.csv` → the `CpuId` column (2,675 unique values);
   - `amd-cpus.csv` → `Product ID Tray` / `Product ID Boxed` / `Product ID MPK`;
   - `benchmark-cpus.csv` → PassMark's own URL `id=` namespace (4,830 values,
     from `SourceUrl`).
3. For each identifier, checks:
   - is the value present in the expected artifact column set?
   - is the owning hardware's manufacturer consistent with that namespace?
   - is the value present in the PassMark URL id space (negative check)?
4. Writes `id_audit_results.json` (summary) and `id_audit_patch.csv` (the exact
   rows plus their intended target source name).

The decision contract lives in the tested module
`backend/app/services/identifier_source.py`; reassignment is allowed only with
value-level evidence.

## 3. Results (all rows, all checks)

| Identifier type | Rows | Present in expected artifact | On matching hardware | Present in PassMark URL ids |
|---|---:|---:|---:|---:|
| `intel_cpu_id` | 2,675 | 2,675 (intel-cpus.csv `CpuId`) | 2,675 (Intel) | 0 |
| `product_id_tray` | 620 | 620 (amd-cpus.csv) | 620 (AMD) | n/a |
| `product_id_boxed` | 215 | 215 (amd-cpus.csv) | 215 (AMD) | n/a |
| `product_id_mpk` | 65 | 65 (amd-cpus.csv) | 65 (AMD) | n/a |

- Identifiers outside the expected artifact: **0**.
- Hardware-manufacturer mismatches: **0**.
- **PassMark cross-check**: none of the 2,675 Intel ids appears in
  benchmark-cpus.csv's `id=` URL namespace (intersection = 0), and the PassMark
  catalog has no `CpuId` / `Product ID *` columns at all, so the values cannot
  have been sourced from the PassMark catalog.
- Duplicate target keys after reassignment `(hardware_id, new source,
  identifier_type, external_id)`: **0**.

## 4. Conclusion

**The source-1 mapping is proven incorrect for all 3,575 rows.** The stored
label ("PassMark CPU benchmark catalog") does not match the origin of any
identifier value. The correct sources, already registered in batch 009, are:

- `Intel ARK (intel-cpus.csv snapshot)` — source id 8 — for all 2,675
  `intel_cpu_id` rows;
- `AMD product specifications (amd-cpus.csv snapshot)` — source id 9 — for all
  900 `product_id_*` rows.

The `cpu_batch_importer` code path (`normalize_intel_row` produces
`intel_cpu_id` from the `CpuId` column; `normalize_amd_row` produces the three
`product_id_*` types from the AMD export) matches exactly this split, which is
consistent with, but not the basis of, the conclusion.

## 5. Correction applied (guarded)

`data/research/batch010/correct_identifier_sources.py`:

- Required and verified the pre-mutation backup
  (`data/backups/spectra-pre-batch010-20261010T100451Z.db`, hash
  `c0e843ed…`, `quick_check` `ok`).
- Resolved target source ids **by registered name** in the live database
  (not assumed), required the patch composition to be exactly
  {Intel ARK: 2,675, AMD: 900}, ran the whole patch in **one transaction**
  with per-row `UPDATE … WHERE id = ? AND source_id = 1` and a hard expected
  row-count check, verified no duplicate `(hardware, source, type, id)` groups,
  and verified the total row count stayed 3,575. Any mismatch rolls back.
- Result: `source_id` 1 → 8 for 2,675 rows, 1 → 9 for 900 rows. Identifier
  values, types, and hardware associations are **untouched** (confirmed by the
  independent audit). No identifiers were deleted and no hardware entity was
  recreated.

## 6. Regression coverage

`backend/app/test_identifier_source.py` covers the name-space decision logic
(including "value present in another namespace does not cause reassignment"),
the expected-source mapping, duplicate-constraint behaviour, and an end-to-end
source-label update that preserves identifier values and hardware links.