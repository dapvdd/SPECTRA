# F. Risks, Ambiguities, and Fields That Should Stay NULL

This batch deliberately leaves values NULL where the evidence would force us to guess.
Each decision below states what was found and why the field stays empty (or which value
was chosen and why).

## 1. Release dates deliberately left NULL

| Hardware | Situation |
|---|---|
| Intel Core i5-10400F, i5-10500-era peers absent from batch; **i5-10400F, i7-10700K, i9-10900K** (Comet Lake desktop) | Wikipedia: *"Intel announced … desktop Comet Lake-S CPUs on April 30, 2020"* (announcement, not retail). Intel ARK (archived) gives only `Q2'20`. Retail day not stated in any fetched source. → **NULL**. If announced-date semantics are acceptable to the developer, 2020-04-30 can be adopted later; it was intentionally excluded from the patch. |
| Intel Core i9-9900K, i7-9700K, i5-9400F (9th-gen Coffee Lake) | Launch day (2018-10-19) appears in the article only as an *archived-review citation date*; both the Wikipedia table and archived ARK expose quarters (`Q4'18` / `Q1'19` for the 9400F). → **NULL**. |
| AMD Ryzen 5 5600G / 4600G | Sources list two dates: OEM (2021-04-13 / 2020-07-21) and retail (2021-08-05 / 2022-04-04). Batch chooses **retail availability** (consistent with how SPECTRA stores retail GPU launch dates). Note recorded per row. |

## 2. Fields that rightly have no numeric value

| Hardware | Field | Reason |
|---|---|---|
| Intel Core i3-8100, Pentium G4560 | `boost_clock_ghz` | These parts ship **without Turbo Boost**; the Wikipedia desktop tables explicitly mark turbo as N/A. NULL is the correct representation; do **not** fill. |

## 3. Value-semantics decisions taken (and alternatives)

- **CPU `process_node_nm` for AMD** = chiplet/CCD node (Zen=14, Zen+=12, Zen 2/3=7, Zen 4=5),
  matching how AMD markets each family. Desktop Ryzen 5000/7000 I/O dies use a larger node
  (12 nm / 6 nm); the per-value note records this. If SPECTRA later wants the IOD node too,
  it needs a new column — do not conflate.
- **Intel 12th/13th-gen `process_node_nm` = 10** ("Intel 7", formerly 10 nm Enhanced SuperFin).
  Archived ARK literally reports `Lithography: Intel 7`; 10 is the nm-class stored per SPECTRA's
  nm convention (the DB stores 14/22/32 for older Intel parts).
- **Intel 12th/13th-gen `tdp_w` = Processor Base Power (PBP)** (125 W / 65 W / 58 W / 150 W),
  NOT Max Turbo Power (241 W/253 W…). This matches existing DB convention (i9-10900K = 125 W).
  Max Turbo Power remains uncaptured — add a column if wanted.
- **Intel 12th/13th-gen `base_clock_ghz` = P-core base frequency** (hybrid parts have a second,
  E-core base; not representable in the current single column).
- **12th/13th-gen release dates are family-level launch statements** (not per-SKU table cells):
  K-series 2021-11-04, non-K 2022-01-04, per-row for 13th-gen. Confidence noted medium-high in
  the evidence table notes.
- **GPU `core_clock_mhz` = TechPowerUp "Base Clock"**, i.e. the same reference-clock field as the
  "GPU Clock" column that populated the 802 GPUs already holding a value (verified: the two CSV
  columns never co-occur — they are the same concept across source-file generations). For 16 NVIDIA
  cards the value independently matches NVIDIA's official "Base Clock".

## 4. Provenance / methodology caveats

- **AMD official pages returned no data.** `https://www.amd.com/en/products/cpu/amd-ryzen-5-5600`
  serves a JS shell (no spec text server-side); an AMD GPU fetch aborted at transport level.
  Hence Wikipedia (which cites official sources) is used for AMD CPU fields and TechPowerUp for
  AMD GPU base clocks. Recorded in each evidence row.
- **AMD GPU base clocks are medium-confidence.** AMD publishes boost/game clocks but *not base
  clocks* for RDNA2/3; TPU's "Base Clock" (e.g. RX 7900 XTX = 1929 MHz) is TechPowerUp's own figure.
- **Legacy NVIDIA GPUs (Turing/Pascal/Maxwell)** have no NVIDIA product page anymore → TPU only,
  medium confidence.
- **Intel ARK is blocked live (HTTP 403);** archived copies (Wayback Machine) were used and are
  cited with the `web.archive.org` URL.
- **Wikipedia is secondary** and can be edited; the exact table/row is citeable, and local extracts
  are preserved under `sources/` for re-verification. Confidence levels assume the reviewer accepts
  Wikipedia-with-official-references as the fallback when officials are unreachable.

## 5. Legal / licensing flags (from `07_gaming_benchmark_source_review.md`)

- **TechPowerUp robots.txt**: content for *personal, non-commercial use*; prohibits data mining,
  AI/LLM use, and *creating datasets of their content* without prior written permission. SPECTRA
  already stores TechPowerUp-derived GPU specs via `data/raw/gpu_1986-2026.csv` (existing
  source_id 3). Batch 001's GPU values come from that same already-acquired snapshot. If SPECTRA
  plans any **public** redistribution, obtain TechPowerUp's permission
  (`w1zzard@techpowerup.com`) — it is explicitly reachable "for assistance".
- **UL / 3DMark Terms & EULA**: reproduction/distribution of results needs written permission;
  no public API (commercial retail API is gated). Bulk retrieval prohibited.
- **Future plc (Tom's Hardware)**: explicitly bars even *manual* extraction.
- **Phoronix.com articles**: require prior written consent. **OpenBenchmarking.org** could not be
  fetched (403) — result-data license **unverified**; treat as unknown until browsed directly.
- **All values in this patch are short factual data points** (clocks, dates, TDP, node), not
  article/chart content; sourced from manufacturer pages or Wikipedia (CC BY-SA) table cells.

## 6. Pre-existing data issues observed (NOT fixed here)

1. **97 of 899** name-matched GPUs hold a `core_clock_mhz` that equals *neither* the raw
   "GPU Clock" nor "Base Clock" column (older IGP/mobile rows like `Radeon HD 6310 IGP`). They
   were imported from a different source ordering; a dedicated re-audit is recommended before any
   cleanup (cleanup is out of scope — this batch never touches a non-NULL column).
2. `memory_gb` is occasionally populated with MB-era values? No — memory is in GB; the 341 NULL rows
   are simply absent from the raw snapshot's `Memory__Memory Size` at correct granularity. The
   sprint18b `parse_memory_gb` handles "256 MB" → 0.25 GB for a future bulk fill.
3. `hardware.architecture` style is inconsistent for GPUs (e.g. both `Maxwell` and `Maxwell 2.0`
   exist). Batch defines CPU architecture as the plain microarchitecture name (`Zen 3`, `Alder Lake`,
   …) to match the dominant GPU style (`Ampere`, `RDNA 2.0`). No existing value was touched.

## 7. Validation & rollback plan (for whoever applies the patch)

```sql
-- Before + after each group of updates:
SELECT hardware_id, name FROM hardware WHERE id IN (<patch ids>);
-- After applying: every patched value should be non-NULL and the guard should reject a rerun:
UPDATE certain table SET ... WHERE hardware_id = ... AND <column> IS NULL;  -- 0 rows affected on rerun

-- Final sanity queries (targets after apply):
SELECT count(*) FROM hardware WHERE type='CPU' AND architecture IS NOT NULL;  -- expect 54 more filled
SELECT count(*) FROM hardware WHERE type='CPU' AND release_date  IS NOT NULL; -- expect 48 more filled
SELECT count(*) FROM cpu_specifications WHERE process_node_nm IS NOT NULL AND hardware_id IN (…AMD ids…) IS NOT NULL;
SELECT count(*) FROM gpu_specifications WHERE core_clock_mhz IS NOT NULL;     -- up to 1879 after bulk fill
```

Rollback: a one-line `UPDATE … SET <column> = NULL WHERE hardware_id IN (…)` per patched set; the
patch JSON embeds the exact id lists. Take a DB backup first (convention: `data/backups/`).

## 8. What this batch does NOT do

- No DB write, no code change, no schema change (verified: `data/spectra.db` last-write 2026-10-05
  predates this session; all DB access was `mode=ro`).
- No gaming-benchmark data is imported (see `07_...md` — no legally clean source found and the
  frontend cannot render it yet).
- No correction of existing values; all 204 updates are NULL-fills guarded by `… IS NULL`.