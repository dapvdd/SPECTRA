# M3 Source Registry

**Date**: 2026-11-16
**Scope**: Sources used or evaluated by M3 catalog expansion (RAM/Storage/Motherboard/PSU).
This registry is the M3 layer over the existing repository registry
(`docs/DATA_SOURCE_REGISTRY.md`, `backend/app/source_registry.py`); it does not
relax any existing restriction.

## Registry

| # | Source | Canonical URL | Type | Categories | License | Status | Access mechanism in M3 | Permission evidence |
|---|---|---|---|---|---|---|---|---|
| M3-1 | Wikipedia (English) | https://en.wikipedia.org/wiki/ | Tertiary, community | RAM, Storage, Motherboard, PSU | CC BY-SA 4.0 (+GFDL dual) | **clear** (attribution + share-alike obligations recorded) | Curated manual citations (article URL + revision); REST API allowed for future automation with polite UA | Wikipedia:Copyrights policy page, verified 2026-11-16; `data/research/batch010/source_permission_research.md` |
| M3-2 | Official manufacturer product pages (Intel/AMD/ASUS/MSI/Gigabyte/ASRock/G.Skill/Corsair/Crucial/Samsung/WD/Kingston/Seasonic/be quiet!) | per-product URL stored per citation | Primary | RAM, Storage, Motherboard, PSU | Site terms — no redistribution licence published | **unknown** | Human-read citations only; **no automated fetching**; every value cites the exact product URL + access date | batch009/010 assessments (terms grant nothing reproducible) |
| M3-3 | GPU Ark | https://gpuark.com/datasets/ | Primary, dataset | GPU only | CC BY 4.0 | **clear** | Existing Batch 018 pipeline | batch010 §2; registry id 4 |
| M3-4 | PassMark | — | Aggregator | all | commercial | **restricted** | **Prohibited** — never fetched, never cited | batch009/015 |
| M3-5 | TechPowerUp | techpowerup.com | Aggregator | GPU | commercial/restricted | **restricted** | **Prohibited** | batch009/015 |
| M3-6 | Geekbench Browser | browser.geekbench.com | Benchmarks | CPU/GPU perf | unknown | **unknown** | Out of M3 scope | batch009/010 |
| M3-7 | Intel ARK (Wayback snapshots) | ark.intel.com | Primary | CPU (not M3) | unknown | **unknown** | Reference only | batch009/010 |
| M3-8 | Owner-manual (SPECTRA first-party) | n/a (in-repo CSV) | First-party | all 6 | First-party (no external licence needed) | **clear** | `generic_csv_importer`, `batch_no=0`, `evidence_status='verified'`, citation columns carry the per-field source URL | Existing M1 Task 3 mechanism |

## Attribution obligations

- **M3-1 (Wikipedia)**: any published record whose values were verified against
  a Wikipedia article stores that article URL (+ revision id when used) in
  `field_provenance.source_url`/`source_reference`; the catalog UI (Phase 7)
  renders a data-attribution notice: "Specs verified against sources including
  Wikipedia (CC BY-SA 4.0)" linking the article. Data files derived
  substantially from Wikipedia expressive text are NOT redistributed as files;
  the catalog stores factual values, which keeps the dataset out of the
  share-alike obligation for expressive content — recorded here as a
  determination, with the conservative alternative (full SA compliance) noted.
- **M3-2 (manufacturer pages)**: each value cites the official product URL and
  access date in provenance. The source row's `license_status` remains
  `unknown` (honest reporting) while the *provenance row* is
  `evidence_status='verified'` because a human verified the value at access
  time. No bulk redistribution of page text occurs.
- **M3-8 (owner-manual)**: first-party curation; attribution column notes the
  human curator step and the cited evidence per field.

## Prohibited/unknown handling (fail-closed)

- No automated fetch of M3-2 in M3 (rule inherited from the mission safety
  contract; enforcement is structural: the two M3 adapters perform zero network
  I/O at import time).
- Any future source must enter as a registry row with evidence before its
  first import; the `SourceLicenseGate` quarantines `restricted`/`unknown`
  bulk extraction.

## Change log

- 2026-11-16: registry created (M3 Phase 0).
