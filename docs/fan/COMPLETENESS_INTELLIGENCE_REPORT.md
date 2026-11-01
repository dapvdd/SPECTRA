# COMPLETENESS_INTELLIGENCE_REPORT — Stage 1

**Mission**: OPERATION SPECTRA: DATA DOMINANCE — Stage 1
**Database**: `data/dev/spectra_dev.db` (isolated dev copy of prod `data/spectra.db`, hash-verified)
**Tool**: `backend/app/scripts/completeness_intelligence.py` (read-only)
**Machine-readable snapshot**: `docs/fan/completeness_intelligence.json`
**Baseline tests**: backend 862 passed / 2 skipped (was 855 → +7 new audit tests)

Every figure below is derived from the database by a deterministic, read-only
audit. Nothing is estimated or invented.

---

## 1. Catalogue totals

| Type | Rows |
|---|---|
| CPU | 3,501 |
| GPU | 1,879 |
| **Total** | **5,380** |

## 2. Vendor coverage

Queried per (manufacturer, type). Included in the machine-readable snapshot
(`vendor_coverage.rows`); no unexpected vendor token was found.

## 3. Missing spec fields (impact-ranked)

CPU (`cpu_specifications`, n=3,501 rows with a spec row):

| Field | Missing | Impact |
|---|---|---|
| cores | 5 | 9 |
| threads | 461 | 8 |
| boost_clock_ghz | 1,076 | 8 |
| tdp_w | 277 | 6 |
| base_clock_ghz | 229 | 5 |
| socket | 190 | 4 |
| process_node_nm | 1,028 | 2 |

GPU (`gpu_specifications`, n=1,879):

| Field | Missing | Impact |
|---|---|---|
| memory_gb | 341 | 7 |
| memory_bus_width_bits | 436 | 7 |
| memory_type | 0 | 6 |
| core_clock_mhz | 4 | 6 |
| boost_clock_mhz | 755 | 3 |
| vram_bandwidth_gbps | 341 | 5 |
| tdp_w | 204 | 5 |
| interface | 1,030 | 2 |
| length_mm | 1,113 | 1 |

Impact is the audit's stable ordinal weight (see `rate_missing_field_impact`)
measuring how much a gap costs the suitability engine — gaps are ranked by impact,
not raw count.

## 4. Benchmark coverage

| Type | With benchmarks | Coverage |
|---|---|---|
| CPU | 518 | 14.8% |
| GPU | 0 | 0.0% |

All benchmark rows are `Geekbench 7` (`multi-core` + `single-core`). **GPU
benchmarks remain at 0%** — no GPU performance evidence exists in this dataset.

## 5. Duplicate & alias conflicts

**0** duplicate (name, manufacturer, type) groups. The hardware identity key is
clean. Unit inconsistency: **none** — a single benchmark family (`Geekbench 7`,
unit `points`) with two test types.

## 6. Provenance

| Metric | Value |
|---|---|
| Hardware with ≥1 provenance row | 5,372 / 5,380 |
| Provenance rows | 39,440 |
| Verified | 39,378 |
| Excluded | 58 |
| Unmatched | 4 |

8 hardware rows carry no provenance at all (attributable to the `unresolved`
source 7 legacy rows — see below).

## 7. Licensing

| Status | Sources |
|---|---|
| clear | 3 (GPU Ark CC BY 4.0, Wikipedia CC BY-SA, derived-naming) |
| restricted | 2 (PassMark, TechPowerUp) |
| unknown | 4 (Geekbench Browser, Intel ARK, Intel/AMD csv snapshots) |
| unresolved | 1 (legacy unknown source) |

Restricted/unknown sources are reference-only, never bulk-reused. They block GPU
benchmark ingestion (no clear-license GPU benchmark source) — documented as a
blocker in Stages 2–3.

## 8. Prioritised gaps

Ranked by engine impact (see `priority_gaps.cpu` for the full sample list; GPU
coverage is 0 by definition):

1. **GPU gaming / AI-ML evidence** — 0% GPU benchmarks; the highest-impact hole.
   Blocked on a clear-license GPU benchmark source.
2. **CPU boost_clock_ghz** (1,076 missing) — a primary suitability signal for
   spec-based ratings; source license `unknown` (Intel ARK).
3. **CPU benchmark expansion** — raise 14.8% → more benchmark-driven ratings.
4. **GPU spec fields** (interface, length, boost clock, bandwidth) — restricted
   TechPowerUp source; partially fillable from clear-license GPU Ark.

## 9. Recommended acquisition priorities (carried into Stage 2)

- Clear-license GPU benchmark dataset (highest impact; currently none licensed).
- Fill CPU boost_clock/process_node from a licensed architecture→node mapping or
  a clear-license manufacturer snapshot.
- Close the 8 no-provenance hardware rows via evidence reconciliation from
  clear-license sources only.
