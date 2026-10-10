# Batch 009 — Gaming Benchmark Research Checkpoint

Date: 2026-10-10

Research-only checkpoint. **No gaming benchmark data was imported in this
batch and none is imported without a separate, permissioned decision.**

## 1. Baseline from earlier research

Batch 001 (`data/research/batch001/07_gaming_benchmark_source_review.md`,
research date 2026-10-08) reviewed candidates and found **no dataset with an
identifiable publisher, verifiable licensing, enough methodology, and
permission for reuse**:

- **UL / 3DMark**: publishers UL Solutions/Futuremark. Terms limit use to
  personal, non-commercial; reproduction/distribution requires prior written
  consent; results are commercially sold. Methodology is published but data is
  permission-gated. **Not usable without a licence.**
- **TechPowerUp**: publishes standardized multi-GPU FPS reviews (same
  game/settings across many GPUs) — exactly the data shape wanted — but the
  robots.txt blocks scraping and dataset creation without written permission.
  **Permission-gated.**
- **OpenBenchmarking.org / Phoronix Test Suite**: `openbenchmarking.org`
  returned HTTP 403 on all attempts (2026-10-08), so its results licence and
  gaming-profile licences **could not be verified**. PTS software itself is
  GPL-3.0. **Unknown/blocked.**
- **Tom's Hardware / Future plc**: terms prohibit even manual extraction —
  "not usable".
- GamersNexus: all-rights-reserved; no permission granted. Notebookcheck: not
  assessed.

## 2. Re-check on 2026-10-10 (this batch)

- `https://openbenchmarking.org/` still returns **HTTP 403** to automated
  access (verified today). OpenBenchmarking result licences therefore remain
  **unverified**; manual browser review is required before any use.
- No other new candidate dataset was scraped or downloaded in this batch.

## 3. Scoring the two viable-looking candidates against the criteria

| Criterion | TechPowerUp review pages | OpenBenchmarking results |
|---|---|---|
| Identifiable original publisher | Yes (TechPowerUp) | Yes (Phoronix Media / OpenBenchmarking.org) |
| Verifiable licensing or explicit permission for intended reuse | No (bulk/dataset creation prohibited; permission obtainable via `w1zzard@techpowerup.com`) | No (site blocked; not verifiable) |
| Methodology / test configuration sufficient for comparisons | Yes (same game + settings across many GPUs, review pages) | Not verifiable from here |
| Identifiable GPU/CPU, game, resolution, quality preset, measured metric | Yes, when permission granted | Not verifiable from here |
| Repeatable structure / reasonable data quality | Yes | Unverified |

## 4. Outcome

**No candidate meets all criteria today.** TechPowerUp is the closest on data
shape, but lacks a reuse licence; OpenBenchmarking cannot be assessed while
blocked. This does not block the base-import provenance work completed in this
batch.

## 5. Exact evidence / permissions still needed to unblock

1. **Written permission from TechPowerUp** (`w1zzard@techpowerup.com`) for a
   small, non-commercial, attributed set of standardized multi-GPU FPS
   tables (game, resolution, quality preset, FPS metric, GPU list).
2. **Manual browser review of OpenBenchmarking** terms (requires a real
   browser; automated tooling is 403-blocked) to determine the results-data
   licence before reuse.
3. If either is granted, the frontend filter
   (`frontend/src/performance.js`, hard-filtered to `Geekbench 7` / `points`)
   and the GPU comparison benchmark panel (hardcoded empty until now) must be
   extended so imported rows are visible — otherwise data would be stored but
   invisible.

Recommended Batch 010 action: contact TechPowerUp for permission and re-check
OpenBenchmarking from a real browser; do not import gaming benchmarks until a
licence is documented.