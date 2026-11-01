# SCORING_METHODOLOGY v1.0.0 — Hardware Suitability & Evidence Quality

**Status:** implemented · deterministic · versioned
**Scope:** SPECTRA Hardware Decision Intelligence (Objectives B & C)

This document specifies exactly how SPECTRA rates hardware suitability for a
workload and how it scores the trustworthiness (evidence quality) of the data
behind each rating. Both dimensions are deliberately **separate**:

- **Suitability (0–5 stars)** — *how good is this hardware for this workload.*
- **Evidence quality (0–1 float + confidence)** — *how trustworthy is our data
  for this hardware + workload pair.*

A suitability rating is **never** confused with the quality of its evidence: a
strong 5-star rating built on weak evidence is possible and is clearly labelled
as such.

Reference implementation: `backend/app/services/suitability_service.py`.

---

## 1. Workload vocabulary

Closed vocabulary shared by the service and the API:

| Category | Title |
|---|---|
| `gaming` | Gaming |
| `workstation` | Workstation |
| `productivity` | Productivity |
| `content_creation` | Content creation |
| `ai_ml` | AI / ML |

---

## 2. Evidence quality (Objective C)

`score_evidence_quality(hardware, workload) -> dict`

A deterministic, heuristic **0..1** score built from four weighted **0/1**
signals. It is a normalised weight of observable signals — **not** a
statistically calibrated probability.

### 2.1 Signals and weights (sum = 1.0)

| Signal | Weight | Meaning |
|---|---|---|
| `attribution` | 0.35 | A benchmark of the workload's family exists |
| `spec` | 0.25 | The workload's key spec fields are non-null |
| `provenance` | 0.20 | A `verified` `field_provenance` row exists |
| `workload_match` | 0.20 | A benchmark of the workload's family exists |

> **Note on collinearity:** `attribution` and `workload_match` are both
> benchmark-family specific and move together. They are kept as two separate
> signals so the payload transparently reports both facets; the weights are
> fixed exactly as the sum-to-1.0 composition above.

### 2.2 Workload → benchmark family

| Workload | Benchmark family | Notes |
|---|---|---|
| `gaming` | `multi-core` | |
| `workstation` | `multi-core` | |
| `content_creation` | `multi-core` | |
| `productivity` | `single-core` | |
| `ai_ml` | *none* | no GPU/VRAM benchmark family exists in this dataset |

`ai_ml` has no supported benchmark family, so `attribution` and
`workload_match` are always **False** for it. Its evidence quality is at most
`spec` + `provenance` and is never `high` in this dataset.

### 2.3 Key spec fields per hardware type

- **CPU:** `cores`, `threads`, `base_clock_ghz`
- **GPU:** `memory_gb`, `memory_type`, `core_clock_mhz`

The `spec` signal is True only when **all** of the type's key fields are
non-null.

### 2.4 Confidence thresholds

| Score | Confidence |
|---|---|
| `>= 0.6` | `high` |
| `>= 0.35` | `medium` |
| `< 0.35` | `low` |

### 2.5 Determinism

The function is a pure function of its inputs: the same `(hardware, workload)`
always returns the identical payload. There is no randomness, time dependence,
or external state.

---

## 3. Suitability rating (Objective B)

`rate_suitability(hardware, workload) -> dict`

A deterministic **0–5 star** rating mapping an observed signal (a benchmark
score, or a spec-only estimate) to suitability for the workload, with explicit
rationale and caveats. Stars are an **ordinal** indicator, not a calibrated
probability of satisfaction.

### 3.1 Output shape

| Field | Type | Meaning |
|---|---|---|
| `stars` | int 0–5 | 0 when unrated |
| `raw_score` | float 0–5 | continuous pre-round score |
| `confidence` | `high`/`medium`/`low`/`unrated` | |
| `evidence_quality` | dict | the Section 2 payload |
| `spec_based` | bool | true when only specs contributed |
| `category` | str | the workload key |
| `rationale` | list[str] | why this rating |
| `caveats` | list[str] | evidence limitations |
| `unrated_reason` | str \| None | set when `unrated` |

### 3.2 Unrated states

| Condition | `unrated_reason` |
|---|---|
| workload is `ai_ml` | `insufficient_data:no_gpu_benchmarks` |
| evidence score is 0.0 (no spec, benchmark, or provenance) | `insufficient_data:no_evidence` |

### 3.3 Star mapping — benchmark-driven

Reference anchors are percentile baselines derived from the **observed
Geekbench 7 population** in this dataset (not invented):

**Single-core** (used for `productivity`):

| Stars | Anchor (score) |
|---|---|
| 1 | 667 (p10) |
| 2 | 983 (p25) |
| 3 | 1,325 (p50) |
| 4 | 1,637 (p75) |
| 5 | 2,020 (p90) |

**Multi-core** (used for `gaming`, `workstation`):

| Stars | Anchor (score) |
|---|---|
| 1 | 1,409 (p10) |
| 2 | 2,809 (p25) |
| 3 | 5,001 (p50) |
| 4 | 8,017 (p75) |
| 5 | 16,347 (p90) |

Scores between anchors interpolate linearly; scores below p10 clamp to 1 star,
above p90 clamp to 5. **`content_creation`** is a blend of the two families:
`0.6 × multi-core stars + 0.4 × single-core stars`.

### 3.4 Spec-based path

When no benchmark of the workload's family exists, the rating falls back to
specifications only and:

- `spec_based` is `True`
- stars are **capped at 3**
- confidence is capped at `medium` and is `low` when the evidence quality
  confidence is `low`
- a caveat states the rating is spec-based

Spec-only estimates use memory capacity + clock speed for GPUs (log-scaled VRAM
weight 0.6 / clock weight 0.4) and cores + boost clock for CPUs.

### 3.5 Confidence for rated states

- Benchmark-driven: `high` when the evidence quality is `high`, else `medium`.
- Spec-based: `medium` when evidence quality is `medium`/`high`, else `low`.

### 3.6 Rationale & caveats

Rationale always states whether the rating came from benchmark evidence or
specifications. Caveats explicitly name evidence limitations, such as:

- no workload-appropriate benchmark data (spec-based)
- no verified field-level provenance
- "reflects raw compute suitability, not a measured FPS figure" (gaming)
- GPU rating describes the GPU alone, not a complete laptop/PC

---

## 4. Recommendation engine (Objective E)

`recommend(hardware_type, workload, budget_max=None, limit=10)`

1. Query hardware filtered by `hardware_type` (CPU/GPU).
2. Rate each hardware for `workload`.
3. **Filter** by evidence threshold: keep candidates where
   `confidence != "unrated"` **and** (`confidence == "high"` **or**
   `stars >= 3`).
4. **Rank** by stars (descending), then evidence-quality score (descending).
5. Return the top `limit`.

`budget_max` is **accepted but has no effect**: this dataset carries no price
data (`budget_max` is documented as deferred in `docs/EVIDENCE_GAPS.md`).

---

## 5. Reproducibility guarantee

- Same input → identical output, across runs and processes.
- All anchors, weights, thresholds and vocabularies are constants in
  `suitability_service.py`.
- A regression/sensitivity suite pins determinism and invariants:
  `test_suitability_scoring.py`.

---

## 6. Insufficient-data rules per category

| Category | What counts as insufficient |
|---|---|
| `gaming` | No multi-core benchmark and no CPU/GPU spec |
| `workstation` | No multi-core benchmark and no CPU/GPU spec |
| `productivity` | No single-core benchmark and no CPU/GPU spec |
| `content_creation` | No multi-core or single-core benchmark and no spec |
| `ai_ml` | Always — no GPU/VRAM benchmark family in this dataset |
