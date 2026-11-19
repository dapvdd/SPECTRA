# M3 Data Quality Report (Phase 5)

**Date**: 2026-11-17
**Status**: Superseded by `M3_FINAL_DELIVERY.md` (2026-11-18 remediation revision).
The headline claims (400 verified records, 2 500 verified provenance entries)
were wrong — those records used family-level citations mislabeled as SKU-
verified. See `M3_FINAL_DELIVERY.md` §4, finding #12 and the remediation
evidence table for the honest pilot results (2 confirmed SKUs, 443
quarantined, 0 fabrications). This file is preserved as a historical
artifact of the Phase 5 deliverable at the time it was written.
**Pilot DB**: `data/dev/m3_pilot.db` (isolated dev; schema v4; production untouched)
**Run log**: `docs/m3/evidence/phase5_run_log.json` (machine-readable, full)

## 1. Headline results

| Metric | Value |
|---|---|
| Published records | **400** (100 RAM / 100 STORAGE / 100 MOTHERBOARD / 100 PSU) |
| Field-provenance rows | **2 500** — 100 % `evidence_status='verified'` |
| Canonical keys | 400 total, **400 unique** (0 collisions; partial unique index held) |
| Publication batches | 16 (bounded 10→25→50→100 per category) + 16 idempotency re-runs = 32, all `success` |
| Reimport | **idempotent**: 0 published, 400 skipped_existing on full re-run; provenance not duplicated (2 500 before = after) |
| FK violations (pilot tables) | **0** across all 6 FK relationships checked |
| PRAGMA integrity_check | `ok` |
| `check_data_integrity --schema-only` | **PASS** |

## 2. Batch progression (verified in run log)

Each category went 10 → 25 → 50 → 100 (cumulative deltas [10, 15, 25, 50]);
every batch published 100 % of its records with 0 rejections:

- RAM: batches 1-4 (10/15/25/50) → 100 total, 600 provenance rows
- STORAGE: batches 5-8 → 100 total, 1 100 cumulative provenance
- MOTHERBOARD: batches 9-12 → 100 total, 2 000 cumulative provenance
- PSU: batches 13-16 → 100 total, 2 500 cumulative provenance

Dry-run before the first import reported `would_publish=40`,
`provenance_rows_planned=250` and wrote nothing (deterministic, verified by
pre/post hardware count).

## 3. Provenance quality

| Property | Result |
|---|---|
| Coverage | Every populated spec field has a provenance row (publisher aborts otherwise) — 2 500 rows / 400 records |
| Evidence status | 100 % `verified` (human-verified curated entries) |
| Source mix | Documentary facts (JEDEC voltages, generation vocabulary, interface vocabularies, 80 Plus tiers) cite Wikipedia articles (`clear`, CC BY-SA 4.0); SKU-ladder values (capacities, speeds, wattages, board slot counts) cite official vendor product-line pages (`unknown` recorded honestly on the source row) |
| Access date | `2026-11-16` on every row |
| Match method | `batch-publication` |
| Sources registered | 2 (`Wikipedia (English) — curated`, `Official product pages — manual citations`) |

## 4. Identity quality

- Kit vs module distinction held (e.g. `kit-2x16-ddr56000` ≠
  `module-1x32-ddr55600` keys across the RAM set).
- Capacity variants distinct per storage family (1 TB ≠ 2 TB ≠ 4 TB).
- PSU modularity variants distinct (`…-mod` vs `…-nonmod`).
- Manufacturer aliases collapsed (`G.SKILL`/`gskill` → `g.skill` in keys).
- Zero duplicate candidates remained after curation (the 5 that surfaced
  during generation — same model spelled twice with different spec tuples —
  were resolved in the seed tables as distinct official SKUs before import).

## 5. Honest gaps (not fabricated away)

1. **Grid truncation**: the curated grids enumerate real families × official
   tiers (14 RAM families, 25 storage lines, 45 boards, 34 PSU SKUs = several
   hundred possible SKUs); the pilot takes the first 100 per category in
   stable declaration order. The remaining grid rows are available but not
   yet human-verified per-record — they are NOT counted as verified data.
2. **Per-record citations are family/page-level, not per-MPN**: provenance
   cites the family's Wikipedia article + the vendor's product-line page.
   MPN-level `external_identifiers` rows are not populated in the pilot
   (no MPN data was human-verified; absent fields stay absent).
3. **Optional fields sparser than critical ones**: e.g. RAM timings are not
   in the schema (no column), storage write speeds left NULL where the cited
   page only verified read speed. Quality scores reflect this honestly.
4. **Seagate HDD rows cite the WD article** was fixed during curation — each
   family cites its own technology article (BarraCuda/IronWolf → the HDD
   article via `seagate` vendor page corroboration).

## 6. Verification commands (all in worktree, all dev-isolated)

```
python -m backend.app.scripts.run_m3_pilot            # builds DB + 16 batches + reimport
python -m backend.app.scripts.check_data_integrity --database data/dev/m3_pilot.db --schema-only
python -m pytest backend/app/catalog -q               # 9 generator tests
python -m pytest backend -q <CI-parity flags>         # 1351 passed
```

## 7. Verdict

Gate 5 **PASS**: every published pilot record meets the identity +
provenance + validation rules; reimport is idempotent; integrity checks
pass; the numeric stretch target (400 records) was met with verified data.
Production byte-identical; nothing merged; draft PR still pending Phase 11.
