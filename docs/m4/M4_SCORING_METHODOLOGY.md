# M4 Scoring Methodology

**Version:** `M4-SCORING-v2.0` (extends `docs/SCORING_METHODOLOGY.md` v1.0.0 — that document remains the normative v1 baseline and is unchanged)

---

## 1. Scope

Four scenarios: `gaming`, `workstation`, `daily`, `value`
(`SCENARIOS` in `backend/app/services/scenario_scoring.py`).

Inputs:

- one M4 feature vector (`M4-FEATURES-v1`, from `intelligence_features.py`),
- anchors per benchmark family (derived, §2),
- an optional workload profile (`M4-PROFILES-v1.0`),
- optional evidence (currently `price_usd` + `price_as_of` only).

## 2. Anchors — derived, not invented

`derive_anchors(scores)` returns the percentile tuple
`(p10, p25, p50, p75, p90)` computed with linear interpolation:
sort ascending, rank `k = (n-1)·p/100`, interpolate between
`floor(k)` and `ceil(k)`.

Edge cases (tested):

- empty population → `None`;
- one element → all five anchors equal that element;
- anchors are a pure function of the passed population.

**Reference population** (payload field `reference_population`): Geekbench 7
scores of benchmarked CPUs in the dataset. For the M3.3 production-like
snapshot (518 CPUs × single/multi-core), the Task 0 audit measured:

| family | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|
| single-core | 666.6 | 982.2 | 1324.5 | 1637.0 | 2016.4 |
| multi-core | 1408.1 | 2792.0 | 4996.5 | 7999.0 | 12311.2 |

**Documented calibration drift:** the multi-core p90 measured in M3.3
(12311.2) sits ~24.7% below the v1 methodology's example p90 (16346.0); the
M4 engine does not hardcode either value — it recomputes anchors from
whatever population it is given. Consumers that pin v1's example anchors will
observe this drift as a multi-core star shift at the top of the range; the
engine's own payload always carries its anchors' provenance via
`reference_population`.

## 3. Scenario weights

Present features only; weights are per scenario (`_BASE_WEIGHTS`):

| Scenario | Feature → weight |
|---|---|
| gaming | multi_core_score 0.5 · single_core_score 0.2 · efficiency 0.2 · memory_gb 0.1 |
| workstation | multi_core_score 0.45 · single_core_score 0.2 · cores 0.2 · efficiency 0.15 |
| daily | single_core_score 0.6 · efficiency 0.4 |
| value | (price-gated; see §6) |

Benchmark-derived stars are the spine; spec features modulate the score by
at most ±10% (`score = stars · (0.9 + 0.2·blend)`), clamped to [0, 5].
Normalization ranges per feature are in `_RANGES` (catalog-observed spreads).

## 4. Evidence gates

| Evidence state | Path | Ceiling | Confidence |
|---|---|---|---|
| Benchmark of the family present | measured stars from `_score_to_stars` (v1 arithmetic) | 5.0 | high (coverage ≥ 0.6) else medium |
| No benchmark, specs present | spec-based proxy (`_SPEC_PROXY`, per type) | **3.0 hard cap** (`_SPEC_BASED_MAX_SCORE`) | medium |
| No benchmark, no usable specs | UNKNOWN (`score=None`) | — | unknown |

A spec-based score always carries the limitation
`spec_based: no workload-appropriate benchmark data; score capped at 3.0`.

## 5. Confidence semantics

- `high` — benchmark-derived and feature coverage ≥ 0.6.
- `medium` — benchmark-derived with lower coverage, or any spec-based score.
- `low` — value scores with unverifiable staleness.
- `unknown` — no evidence; `score` is `None`.

Spec-only vectors can never reach `high`
(asserted: `test_m4_evaluation.py::test_spec_only_confidence_never_high`).

## 6. VALUE scenario (price-gated)

- `evidence` without `price_usd` → UNKNOWN with limitation
  `missing_data:price …`. **This dataset has no price columns, so VALUE is
  always UNKNOWN here** (asserted across six fixture rows in the evaluation
  suite).
- With a price: `score = performance / price` (ratio, 4 dp), `stars=0`
  (not a 0–5 scale), confidence `low`, limitation that the ratio is
  relative (no market calibration), plus a staleness note when
  `price_as_of` is absent.

## 7. Resolution & gaming

A `resolution` preference (1080p/1440p/4k) adds an advisory limitation to the
gaming payload when gaming is scored — it never changes the numeric score
(no GPU gaming benchmark evidence exists in this dataset).

## 8. Determinism & anti-gaming properties

- Pure functions; no clocks, no randomness, no I/O.
- Outlier robustness: scores are clamped to [0, 5]; a 10× p90 outlier
  saturates at 5 and never goes negative (tested).
- Conflicting benchmark records: the feature layer takes the max per family,
  deterministically (tested).
- No recency bias: release_date/architecture are absent from every weight
  table (tested).

## 9. Versioning

Every payload carries `scoring_version: M4-SCORING-v2.0`. Any change to
weights, caps, or anchor arithmetic must bump this version and extend
`docs/m4/M4_EVALUATION_REPORT.md`.
