# M3.1 Acquisition Report

**Date**: 2026-11-23
**Branch**: `feat/m31-catalog-acquisition`
**Scope**: Full M3.1 acquisition mission — the 443 quarantined candidates from the M3 pilot generator turned into a verified, manufacturer-evidence-backed catalog expansion published to an isolated dev DB.

## Result

| Metric | Value |
|---|---|
| Candidates in inventory | 443 (RAM 128 / STORAGE 109 / PSU 106 / MOTHERBOARD 100) |
| MATCHED (verified SKUs) | **49** (RAM 32, STORAGE 10, PSU 7) |
| REPLACED | 11 (RAM family variants superseded by verified SKUs) |
| UNRESOLVED | 383 (RAM 85, STORAGE 99, PSU 99, MOTHERBOARD 100) |
| INVALID | 0 |
| Published to dev DB | 49 hardware rows + 270 field_provenance rows (all `evidence_status='verified'`) |
| Idempotent re-run | skipped_existing 49, published 0 |
| PRAGMA integrity_check | ok |
| PRAGMA foreign_key_check | 0 violations |

Product decision honored: no artificial combinations were created to hit numerical targets; a smaller verified set (49) won over an unsubstantiated catalog (443).

## Test evidence (final, 2026-11-23)

- Backend CI-parity: **1498 passed / 2 skipped / 2 deselected** (baseline 1426 + 72 new acquisition/runner tests; CI-parity flags per `.github/workflows/ci.yml`).
- Frontend: **681 passed / 0 failed**; vite build OK; oxlint 4 pre-existing warnings identical on `main` (branch touches no frontend file).

## What was verified (MATCHED, with per-SKU evidence)

- **RAM (32)** — Corsair only: Vengeance DDR5 (14), Dominator Titanium (6, consolidated to Dominator Platinum RGB SKUs), Vengeance LPX DDR4 (9), Value Select DDR4 (3). MPNs `CMK…/CMT…/CMV…`, per-SKU `corsair.com/p/<MPN>` pages, spec-table rows, access 2026-11-22.
- **STORAGE (10)** — WD_BLACK SN850X (3: `WDS100T2X0E-00BCA0`, `WDS200T2X0E-00BCA0`, `WDS400T2X0E-00BCA0`; Sandisk product pages, access 2026-11-23); Kingston KC3000 (4: `SKC3000S/512G`, `SKC3000S/1024G`, `SKC3000D/2048G`, `SKC3000D/4096G`; datasheet PDF, access 2026-11-23); Kingston A400 (3: `SA400S37/240G`, `SA400S37/480G`, `SA400S37/960G`; datasheet PDF, access 2026-11-23).
- **PSU (7)** — Corsair RMx 2021 (4: `CP-9020197-NA` … `CP-9020200-NA`) + RMx SHIFT (3: `CP-9020251-NA` … `CP-9020253-NA`); corsair.com per-SKU pages, access 2026-11-23.

Every MATCHED SKU carries: non-empty MPN, per-SKU URL, APPROVED FieldEvidence per populated spec field (source_reference locator, match_method ∈ manual-curation|spec-table-row|manufacturer-declaration, access date). Wikipedia never backs SKU-specific fields.

## What was not verified and why (UNRESOLVED, fail-closed)

Per-family source-access evidence is recorded in `data/research/m31/02_resolution_report.json` and the per-category research notes:

- **Samsung/Seagate/WD families** — vendor pages JS-rendered; per-SKU model numbers not served to polite fetches.
- **Crucial** — WAF/403 on product pages.
- **Kingston NV2/A2000/KC2500** — discontinued/redirect pages; the NV3 page's AddToCart PartNumbers do not map to any inventory candidate (no family-level pass was made).
- **Seasonic/be quiet!/Cooler Master/Thermaltake** — JS-rendered catalogs; per-SKU URLs not retrievable.
- **EVGA** — PSU business exited; official per-SKU pages retired.
- **ASUS/MSI/Gigabyte/ASRock motherboards (all 100)** — vendor pages JS-rendered/generic; no per-SKU MPN evidence obtainable this session.
- **G.Skill/Kingston Fury/Crucial RAM, TeamGroup/ADATA** — JS-rendered or 404 product paths.

No MPN was invented; optional unknown spec fields stay NULL.

## Pipeline (Tasks 1–8)

1. **Inventory** (`581711e`) — 443 candidates extracted deterministically from the M3 pilot enumeration.
2. **Acquisition package** (`2b9145b`) — manifest (fail-closed validation), resolver (deterministic 4-way classification), pipeline (dedup → quarantine → bounded batches 10/25/50/100 → checkpoint → publish), errors (8-kind vocabulary).
3. **Source adapters** (`2945ac7`) — Wikipedia REST revision client (polite); manufacturer adapters are citation PLANNERS with structural no-network pins.
4. **RAM manifests** (`72c5925`) + **Storage/PSU manifests + runner + resolution report** (`496c610`) + **rehearsal** (`c9317c1`).
5. **Category runner rule (fail-closed fix)** — only MATCHED manifest entries participate in identity resolution; UNRESOLVED entries verify nothing and must not turn same-family candidates REPLACED.
6. **Publication rehearsal** — `data/dev/m31_acquisition.db` (cloned v1 schema + migrations 1–4): dry-run → bounded apply → idempotent re-run → PRAGMA checks. Evidence: `docs/m3/evidence/m31_run_log.json`.

## Deliverables

- `data/research/m31/01_candidate_inventory.{csv,json}` — 443 rows.
- `data/research/m31/manifest_{ram,storage,psu}.json` — verified-SKU manifests (validate_manifest clean).
- `data/research/m31/research_{ram,storage,psu}.md` — per-family research notes.
- `data/research/m31/02_resolution_report.json` — per-candidate outcome + evidence + confidence.
- `data/dev/m31_acquisition.db` — rehearsal DB (git-ignored).
- `docs/m3/evidence/m31_run_log.json` — rehearsal run log.
- `docs/m3/M31_SKU_VERIFICATION_MANIFEST.md`, `M31_DATA_QUALITY_REPORT.md`, `M31_RESIDUAL_RISKS.md`, `M31_RELEASE_READINESS.md`.

## Test evidence

- Backend CI-parity suite: green (see M31_RELEASE_READINESS.md for the exact final counts).
- Acquisition suites: `test_acquisition.py` + `test_acquisition_adapters.py` + `test_category_runner.py` = 72 passed.
- Frontend suite: 681 passed (untouched by this branch's runtime code; build + lint clean).
