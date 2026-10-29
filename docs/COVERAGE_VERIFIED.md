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
| provenance rows | 40,405 (↑965 from Batch 018 GPU enrichment) |
| sources | 10 (↑1 from Phase B) |
| hardware covered by provenance | 5,360 / 5,380 (99.6%) |
| hardware benchmarks present | 518 / 5,380 (9.6%) |
| segment classified | 2,494 / 5,380 (46.3%) |

## Field completeness (what is *actually present*, not what we wish were)

CPU coverage is best for `cores` (99.9%) and weakest for `boost_clock_ghz`
(69.3%) and `process_node_nm` (70.6%). GPU coverage is best for `memory_type`
(100%) and worst for `length_mm` (40.8%). GPU `interface` improved from 45.2%
to 95.1% via Batch 018 (GPU Ark CC BY 4.0, sha256:bcaba010…). Boost clock
is the single weakest shared field (~60–70% on both CPU and GPU).

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

## After Batch 018 (GPU Ark CC BY 4.0 enrichment — Phase C, 2026-10-29)

- GPU `interface` enriched from GPU Ark `bus_interface` (938 records → 45.2% → 95.1%).
- GPU `memory_bus_width_bits` enriched (27 data-center HBM GPUs → 76.8% → 78.2%).
- Source: GPU Ark (`https://gpuark.com/datasets/`, CC BY 4.0), CSV fetched
  2026-10-28, sha256 `bcaba010961cdeca4d2260028d7f27f2c18317e67ffbddec7a09d3dddfa9f734`,
  13,566 rows.
- 28 candidate records excluded (GPU Ark `bus_interface` genuinely empty for
  console/APU/embedded GPUs: Wii U, Xbox, PlayStation, Switch, Steam Deck,
  Ryzen Z1/Z2). No values fabricated.
- 965 records applied with full provenance (source_id=4, batch_no=18, confidence
  medium, evidence_status verified). NULL-only guard: 0 overwrites, 0 conflicts.
- Integrity after apply: `quick_check=ok`, `foreign_key_check=0`,
  idempotent (re-run produces 0 new records), 703 backend + 29 classifier tests pass.
- Scripts and README: `data/research/batch017/`.

## After Batch 017 (segment backfill — Phase B, 2026-10-28)

- `hardware.segment` populated via deterministic classifier (no external fetch).
  - 2,494 / 5,380 rows classified: mobile 1,047, server 1,209, workstation 238.
  - 2,886 rows remain NULL (honest unknown; classifier refuses ambiguous tokens).
  - New source added: #10 "Derived from manufacturer product naming conventions"
    (`license_status=clear` — grounding is each vendor's published naming convention).
  - 2,494 new provenance rows added (source_id=10, field_name=segment).
  - Integrity: 0 segment-value overrides (column was NULL for all 5,380 before this
    batch); re-running classifier on NULL records produces 0 new classifications
    (idempotence verified); 0 conflicts; 0 duplicate provenance rows.
- The catalog API returns `segment` populated for 46.3% of records; the remainder
  reports honestly as `null` / "unknown" in the build-intelligence module.
- Tests: 29 classifier unit tests added (`data/research/test_segment_classifier.py`);
  703 backend tests still passing; 572 frontend tests still passing.

## Re-measure command

```bash
python data/research/phase2_quality_audit.py
```
