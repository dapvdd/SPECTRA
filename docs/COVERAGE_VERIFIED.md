# Verified Data Coverage (2026-10-28)

Companion to `COVERAGE_VERIFIED.json`. Measured from the local copy of the
deployed database — the same database the API serves, so these numbers are the
real coverage the endpoint exposes, not an idealised model.

## The one sentence test of honesty

> A database with 5,380 rows is not "comprehensive". It is comprehensive only
> for what it can actually demonstrate, field by field, provenance by proof.

## Verified totals

| Measure | Value |
|---|---|
| hardware rows | 5,380 |
| CPU rows | 3,501 |
| GPU rows | 1,879 |
| benchmark results | 1,040 (all Geekbench 7, all CPU) |
| external identifiers | 3,575 |
| provenance rows | 36,946 |
| sources | 9 |
| hardware covered by provenance | 5,360 / 5,380 (99.6%) |
| hardware benchmarks present | 518 / 5,380 (9.6%) |

## Field completeness (what is *actually present*, not what we wish were)

CPU coverage is best for `cores` (99.9%) and weakest for `boost_clock_ghz`
(69.3%) and `process_node_nm` (70.6%). GPU coverage is best for `memory_type`
(100%) and worst for `length_mm` (40.8%) and `interface` (45.2%). Boost clock is
the single weakest shared field (~60–70% on both CPU and GPU).

## What "validated" means here

- 99.6% of hardware rows have ≥1 provenance row; the 20 without are counted as
  unattributed, never guessed.
- All 1,040 benchmark records carry provenance with `evidence_status=verified`.
- 58 excluded + 4 unmatched provenance rows are real: records whose source
  evidence did not confirm a value. They are kept, flagged, and excluded from
  validated counts rather than silently dropped.

## Honesty bounds (features we deliberately do not fake)

1. **No GPU benchmarks.** 0 GPU benchmark rows — by design; no pipeline faked
   one.
2. **No prices / MSRP / prices history.** Not ingested; not shown.
3. **No system power claims.** Build shows "listed TDP", never measured draw.
4. **No fabricated citations.** Every value links to a `sources` row with a URL
   and licence status (3 `clear`, 4 `unknown`, 1 `restricted`, 1 `unresolved`).

## After Batch 017 (this session)

- Added `hardware.segment` (nullable, additive) via
  `backend/app/migrations/add_hardware_segment.py`. The 5,380 legacy rows now
  have `segment = NULL`, which is reported honestly as "unknown" until backfilled
  from manufacturer category pages (Intel ARK / AMD product pages / GPU Ark).
- The catalog API now returns `segment`; a build-intelligence compatibility
  module and comparison power-efficiency metric are covered by tests.

## Re-measure command

```bash
python data/research/phase2_quality_audit.py
```
