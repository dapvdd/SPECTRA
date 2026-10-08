# SPECTRA Research Batch 001 — Review Package

**Date:** 2026-10-08
**Status:** PROPOSAL ONLY — nothing has been imported into SQLite. `data/spectra.db` was opened read-only; its last-write time is unchanged (2026-10-05).
**Scope:** Data completeness audit, prioritized gap analysis, manual research for 98 popular hardware items (54 CPUs + 44 GPUs), and a proposed, source-attributed database patch.

## Contents

| File | Deliverable |
|---|---|
| `01_completeness_audit.md` | **A.** Data completeness audit (schema, NULL rates, benchmark coverage, raw-source fill analysis) |
| `02_prioritized_missing_fields.md` | **B.** Which missing fields matter most for SPECTRA's comparison/build intelligence (based on actual code usage) |
| `03_selected_hardware.csv` | **C.** The 98 selected hardware items with their current missing fields |
| `04_evidence_table.csv` | **D.** Research/evidence table: 204 values, each with hardware identity, field, value, source, source URL, confidence, notes |
| `05_database_patch.json` | **E.** Proposed patch (structured, guarded `... IS NULL` updates, `applied: false`) |
| `06_risks_and_open_questions.md` | **F.** Risks, ambiguities, and fields that should remain NULL |
| `07_gaming_benchmark_source_review.md` | Special-priority investigation: legally usable GPU gaming-benchmark sources |
| `sources/` | Local extracts of every source page used (Wikipedia table extracts, prose snippets, ARK cross-check values) so a reviewer can re-verify without re-fetching |

## Headline numbers

- **204 proposed values** across 98 items: 174 high confidence, 30 medium confidence.
  - `hardware.architecture`: 54 (all selected CPUs; currently 0 % populated for CPUs)
  - `hardware.release_date`: 48 (6 Intel items deliberately left NULL — see risks)
  - `cpu_specifications.process_node_nm`: 36, `base_clock_ghz`: 11, `tdp_w`: 11
  - `gpu_specifications.core_clock_mhz`: 44
- **Not researched / excluded on purpose:** Intel Comet Lake (3) and 9th-gen Coffee Lake (3) release dates (only quarter-granularity evidence found); `boost_clock_ghz` for Intel Core i3-8100 and Pentium G4560 (these CPUs have no turbo boost — NULL is correct); card length for RX 9070/9070 XT (AIB-model dependent).
- **GPU gaming benchmarks:** no legally clean bulk source was found (see `07_...md`). TechPowerUp and UL/3DMark both prohibit systematic retrieval; OpenBenchmarking could not be verified (HTTP 403). **No gaming benchmark data is proposed for import.**

## Method and sourcing rules applied

1. **No database or application code was modified.** Only new files under `data/research/batch001/`.
2. **Official sources first.** NVIDIA official product pages were used and cross-checked for 16 GPUs. Intel ARK live pages returned HTTP 403, so *archived ARK copies (Wayback Machine)* were used for cross-checks of two 12th-gen SKUs. AMD product pages are JavaScript-rendered and returned no server-side specification data (documented in `06_...md`); AMD GPU fetch also failed at transport level.
3. **Reputable secondary sources** (Wikipedia articles that cite official sources) were used for CPU fields where official sources were unreachable; the exact article is recorded per value.
4. **TechPowerUp GPU Database** (the project's existing `source_id 3`, already present in `data/raw/gpu_1986-2026.csv`) provides GPU base clocks; 16 values were independently confirmed against NVIDIA's official pages (base *and* boost clocks match within rounding).
5. **No value was invented or interpolated.** Every number was extracted from a fetched document by the generator script, then asserted against an independently hand-entered expected value (double-entry). The run reported: `All verification checks passed.`
6. Uncertain values were left NULL rather than guessed (see `06_...md`).

## How to review / apply later

1. Read `01_...`, `02_...`, `06_...`, `07_...`.
2. Spot-check `04_evidence_table.csv` rows against `source_url` (local copies of the extracts are in `sources/`).
3. If accepted: apply `05_database_patch.json` updates one by one with the guard shown (`WHERE hardware_id = <id> AND <column> IS NULL`), then run the validation queries in `06_...md §Validation`.
4. The patch is designed to be idempotent and reverts nothing (all guards require the column to still be NULL).
