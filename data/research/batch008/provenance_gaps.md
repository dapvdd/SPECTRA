# Batch 008 - Provenance Gaps

Date: 2026-10-09

## 1. Confirmed gap: no persisted field-level provenance

Before Batch 008, the database stored specification values with **no link to
their source**. The `sources` table carried only `name` + `url`; the only
source-linked rows were `external_identifiers` (identifiers, not values) and
`benchmark_results.source_id`. Every source/confidence/URL fact for the
enrichment batches existed only inside research artifacts
(`data/research/batch001-006/`), so an auditor could not query
"which values came from GPU Ark?" directly from the database.

## 2. Source metadata gaps

- **Sources table columns**: no license, attribution, access-date or reuse
  terms columns. Even the identities of the episodic enrichment sources
  (GPU Ark, Wikipedia, Intel ARK) were not registered as `sources` rows.
- **Access dates**: recorded only for batch 003 Wikipedia articles
  (`sources/provenance.json`, `2026-10-09`). Access dates for GPU Ark
  datasets (batches 002/005/006), batch 001 Wikipedia/ARK/TechPowerUp pages
  are **unknown** and were not fabricated.
- **Attribution text**:  recorded in prose in the audits, not as structured
  data.

## 3. Licensing gaps and concerns

- **GPU Ark (CC BY 4.0)**: reuse permitted with attribution. Attribution is
  documented in the audits and is now persisted per-resolution record; a
  display layer must surface it.
- **Wikipedia (CC BY-SA 4.0)**: reuse permitted with attribution **and
  share-alike**. SPECTRA's enrichment values are factual specifications
  transcribed from source tables; share-alike obligations for any derivative
  redistribution need legal confirmation before any user-facing export of
  Wikipedia-derived values. Unresolved.
- **TechPowerUp**: batch 001 imported 44 GPU core clocks from the local
  TechPowerUp snapshot before the reuse assessment that later excluded the
  source. Those 44 values remain in the database; 16 of 44 were cross-checked
  against NVIDIA official pages. The provenance now records the documented
  restriction in `license_notes`; the values themselves are compliance-
  sensitive legacy data.
- **Intel ARK (archived)**: 2 values (process_node_nm) cross-checked via
  Wayback-archived ARK pages; no bulk reuse grant documented.
- **PassMark / Geekbench**: base-import sources with **no documented reuse
  licence**; no enrichment provenance was attached because no enrichment
  batch used them.
- **Gaming benchmarks**: no legally verified bulk dataset found
  (`batch001/07_...md`); none imported. This remains an open source gap.

## 4. Coverage gaps

- 36,473 populated hardware/spec cells in the database; after Batch 008,
  **3,320 (9.1%) carry verified field-level provenance** - exactly the cells
  written by enrichment batches 001-006. The remaining ~33,153 cells come from
  base imports (PassMark CPU data, TechPowerUp GPU import, Geekbench results)
  and have **no provenance records yet**.
- 2,234 of 5,239 hardware items (42.6%) have at least one provenance record.
- Excluded/unmatched evidence (58 + 4 records) was previously only in audit
  language, not queryable as data.
- GPU Ark `source_record_id`, Wikipedia `source_reference`
  (`extract.tables.txt::TABLE n`) are preserved where the artifacts recorded
  them (the precise extract artefacts themselves remain in
  `data/research/batch00x/sources/`).

## 5. How Batch 008 addressed the gaps

1. Registered the enrichment sources as real `sources` rows (GPU Ark,
   Wikipedia (English), Intel ARK, and one documented placeholder for the
   six batch-001 excluded values whose source was not recorded).
2. Added a minimal `field_provenance` model that links `hardware_id` +
   (table, field) to a source and preserves source URL, license,
   attribution, confidence, evidence status, matching keys, access date and
   notes.
3. Loaded 3,382 reconciled evidence records (3,320 verified, 58 excluded,
   4 unmatched), idempotently.
4. Added an idempotent migration consistent with the repository's
   `Base.metadata.create_all` + manual `ALTER` convention (no new migration
   framework).

Remaining gaps for a future batch: reconstruct provenance for base-import
values (PassMark / original TechPowerUp import / Geekbench), resolve
TechPowerUp legacy values, obtain a licensed gaming benchmark dataset, record
access dates for future evidence collection, and confirm CC BY-SA share-alike
handling before user-facing redistribution.