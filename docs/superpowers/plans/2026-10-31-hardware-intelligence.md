# SPECTRA Hardware Decision Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform SPECTRA into an explainable Hardware Decision Intelligence Platform with
workload-aware suitability ratings, evidence-quality scoring, a deterministic recommendation
engine, and an interactive Hardware Fit experience.

**Architecture:**
- **Evidence quality** (Objective C) is a *separate output dimension* from **suitability
  ratings** (Objective B): evidence quality answers "how trustworthy is our data for this
  hardware + workload?" (float 0–1 + confidence label); suitability answers "how good is
  this hardware for this specific workload?" (stars 0–5 + confidence + caveats).
- Both dimensions are deterministic, versioned, and documented. Neither fabricates values
  when evidence is absent — both return `unrated` with explicit reason strings.
- **GPU benchmarks = 0** (1,040 rows are all CPU Geekbench 7, 0 GPU rows). GPU
  gaming/AI/ML suitability is spec-based only and declared with `spec_based: true` +
  reduced confidence.
- **AI/ML category**: cannot be rated — no VRAM benchmarks, no CUDA-core benchmarks.
  Returns `unrated: "insufficient_data_no_gpu_benchmarks"`.
- Recommendation is deterministic ranking by suitability + evidence threshold; AI
  explanations are a separate, grounded layer on top.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy) / React 18 / Vite 5 / TypeScript

**Spec:** MISSION block in conversation (Hardware Intelligence Expansion, 2026-10-31).

---

## Global Constraints

- **No fabricated values**: benchmark scores, specifications, prices, provenance
  evidence, or source licences are never invented. A field is `null` or `unrated` —
  never a made-up number.
- **No GPU benchmark data** exists: 1,040 benchmark rows are all CPU Geekbench 7,
  covering 518/3,501 CPUs (0 GPU benchmarks).
- **Benchmark evidence only for CPUs**: only Geekbench 7 single-core/multi-core.
- **Production DB never mutated**: all enrichment/reconciliation scripts run on
  disposable copies only.
- **Auth stays OFF**: no activation without explicit approval.
- **Preserve existing tests**: all 815 backend + 599 frontend tests must remain green.
- **Determinism**: all scoring functions are pure and versioned; same input always
  yields identical output.

---

## Review Focus (five failure modes most likely to bite)

1. GPU hardware returns a numeric star rating with no evidence when there are zero
   GPU benchmarks — must be `unrated` with `insufficient_data` reason.
2. CPU hardware without any benchmark rows returns a high star rating because its
   specs look good — evidence quality must gate the suitability score.
3. A workload category returns a rating when only one type of evidence exists (e.g.
   AI/ML for CPU returns a rating when it needs GPU data) — each category's minimum
   evidence bar must be enforced.
4. Recommendation endpoint returns an empty list without explaining why — must
   surface the filtering reason to the caller.
5. Frontend displays a star rating without showing the evidence coverage/confidence
   — the two-panel display (rating + evidence) must never be separated.

---

## File Map

### New files to create

| Path | Responsibility |
|---|---|
| `backend/app/services/suitability_service.py` | Core scoring engine: evidence quality + suitability ratings per category |
| `backend/app/services/recommendation_service.py` | Deterministic recommendation/ranking logic |
| `backend/app/schemas/suitability.py` | Pydantic wire models for suitability API |
| `backend/app/schemas/recommendation.py` | Pydantic wire models for recommendation API |
| `backend/app/test_suitability_service.py` | Scoring formula tests, boundary cases, regression |
| `backend/app/test_recommendation_service.py` | Filter/rank logic tests, edge cases |
| `backend/app/scripts/completeness_audit.py` | Objective A: read-only audit + before/after metrics |
| `docs/SCORING_METHODOLOGY.md` | Objective C: versioned, documented scoring methodology |
| `docs/EVIDENCE_GAPS.md` | Remaining evidence gaps report (Objective F) |
| `frontend/src/components/SuitabilityCard.jsx` | Renders one suitability category (stars + evidence + caveat) |
| `frontend/src/components/HardwareFitModal.jsx` | Full Hardware Fit interactive experience |
| `frontend/src/hooks/useSuitability.js` | Fetches suitability data for a hardware ID |
| `frontend/src/hooks/useRecommendation.js` | Fetches recommendation results |

### Files to modify

| Path | Change |
|---|---|
| `backend/app/main.py` | Add suitability + recommendation GET endpoints |
| `backend/app/schemas/__init__.py` | Export new schemas |
| `frontend/src/App.jsx` | Wire HardwareFitModal trigger + detail page integration |
| `frontend/src/components/ChatView.jsx` | Add Hardware Fit button in hardware detail section |
| `frontend/package.json` | No changes (existing deps sufficient) |

---

---

## Task 1: Completeness Audit (Objective A)

**Files:**
- Create: `backend/app/scripts/completeness_audit.py`
- Test: none (read-only diagnostic script)

**Interfaces:**
- Consumes: `data/spectra.db` (read-only, copy)
- Produces: `docs/fan/completeness_audit.json` (before/after JSON)

- [ ] **Step 1: Write the audit script** (`backend/app/scripts/completeness_audit.py`)

The script reads from a disposable copy and emits structured JSON (deterministic, `sort_keys=True`). It writes nothing to the production DB.

The audit computes:
1. Per-type spec completeness: fraction of CPU/GPU rows with complete specs (all core spec fields non-null).
2. Per-type benchmark coverage: fraction with at least one benchmark row.
3. Per-segment benchmark coverage (CPU only â€” GPU has 0 benchmarks).
4. Benchmark name distribution (confirm only Geekbench 7 CPU).
5. Number of hardware rows with zero specs and zero provenance (the "no evidence" tier).
6. Priorities: hardware with high-demand signals (segment + newer release) but low spec completeness or no benchmarks.

- [ ] **Step 2: Run the audit against the current copy**

Run: `python backend/app/scripts/completeness_audit.py --database data/spectra.db > docs/fan/completeness_audit.json`
Expected: JSON with per-type/per-segment completeness percentages; GPU benchmark coverage 0% (expected); CPU benchmark coverage ~14.8% (518/3501).

- [ ] **Step 3: Commit**

`git add backend/app/scripts/completeness_audit.py docs/fan/completeness_audit.json`
`git commit -m "feat(completeness): read-only catalog completeness audit pipeline"`

---

## Task 2: Evidence Quality Scoring (Objective C)

**Files:**
- Create: `backend/app/services/suitability_service.py` (contains `score_evidence_quality`)
- Test: `backend/app/test_suitability_service.py`

**Interfaces:**
- Consumes: `Hardware`, `CPUSpecification`, `GPUSpecification`, `BenchmarkResult` objects
- Produces: `score_evidence_quality(hardware, workload) -> dict` with keys:
  - `score` (float 0â€“1)
  - `confidence` (`"high"` | `"medium"` | `"low"`)
  - `signals` dict (per-signal booleans)
  - `benchmark_present` (bool)
  - `spec_complete` (bool)
  - `reason` (str | None)

- [ ] **Step 1: Write the failing test** (`backend/app/test_suitability_service.py`)

```python
def test_evidence_quality_high_for_benchmarked_complete_hardware():
    hw = make_hardware(type="CPU", cpu_spec=full_spec(), benchmarks=[benchmark()])
    result = score_evidence_quality(hw, "gaming")
    assert result["score"] == 1.0
    assert result["confidence"] == "high"

def test_evidence_quality_low_when_no_benchmarks_and_no_specs():
    hw = make_hardware(type="CPU")
    result = score_evidence_quality(hw, "gaming")
    assert result["score"] == 0.0
    assert result["confidence"] == "low"
```

- [ ] **Step 2: Run test to verify it fails** â€” `pytest backend/app/test_suitability_service.py -k evidence` â€” expected FAIL (module missing).

- [ ] **Step 3: Implement `score_evidence_quality(hardware, workload) -> dict` in `backend/app/services/suitability_service.py`**

Weighted signals (sum = 1.0), each a 0/1 contribution:
- `_ATTR_WEIGHT` 0.35 â€” hardware has â‰¥1 benchmark row for the workload's benchmark family (benchmark_present)
- `_SPEC_WEIGHT` 0.25 â€” hardware has its spec row present and the workload's key fields non-null
- `_PROVENANCE_WEIGHT` 0.20 â€” hardware has â‰¥1 verified field_provenance row
- `_WORKLOAD_MATCH_WEIGHT` 0.20 â€” the benchmark family is directly relevant to the workload (e.g. multi-core for workstation, single-core for productivity)

Confidence mapping: `>=0.6` â†’ `"high"`, `>=0.35` â†’ `"medium"`, else `"low"`.

- [ ] **Step 4: Run test to verify it passes** â€” `pytest backend/app/test_suitability_service.py -k evidence` â€” expected PASS.

- [ ] **Step 5: Commit**

`git add backend/app/services/suitability_service.py backend/app/test_suitability_service.py`
`git commit -m "feat(suitability): evidence quality scoring (objective C)"`

---

## Task 3: Suitability Rating Engine (Objective B)

**Files:**
- Create: `backend/app/services/suitability_service.py` (add `rate_suitability`)
- Test: `backend/app/test_suitability_service.py`

**Interfaces:**
- Consumes: `score_evidence_quality` output, `Hardware`, spec objects
- Produces: `rate_suitability(hardware, workload, detail=None) -> dict` with:
  - `stars` (int 0â€“5)
  - `raw_score` (float 0â€“5)
  - `confidence` (`"high"` | `"medium"` | `"low"` | `"unrated"`)
  - `evidence_quality` (the `score_evidence_quality` output)
  - `spec_based` (bool â€” true when no benchmark contributed, only specs)
  - `category` (the workload key)
  - `rationale` (list of str â€” explainable reasons)
  - `caveats` (list of str â€” limitations/missing evidence)

- [ ] **Step 1: Write the failing tests**

```python
def test_gaming_rating_rejects_gpu_with_no_benchmarks():
    hw = make_hardware(type="GPU", gpu_spec=full_gpu_spec())
    result = rate_suitability(hw, "gaming")
    # GPU has zero gaming benchmarks -> spec-based rating
    assert result["spec_based"] is True
    assert result["confidence"] in ("low", "medium")

def test_ai_ml_rating_is_unrated_when_no_gpu_benchmarks():
    hw = make_hardware(type="GPU", gpu_spec=full_gpu_spec())
    result = rate_suitability(hw, "ai_ml")
    assert result["confidence"] == "unrated"
    assert result["stars"] is 0...  # see implementation
    assert "insufficient_data" in result["caveats"][0]

def test_suitability_is_deterministic():
    hw = make_hardware(type="CPU", cpu_spec=full_spec(), benchmarks=[benchmark()])
    a = rate_suitability(hw, "gaming")
    b = rate_suitability(hw, "gaming")
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails** â€” expected FAIL (`rate_suitability` not defined).

- [ ] **Step 3: Implement `rate_suitability(...)` in `suitability_service.py`**

Workload categories and their signals:
- `gaming`: benchmark family = multi-core Geekbench 7; CPU signal = multi-core score (if present), else spec-derived (cores/threads/boost clock). GPU â€” spec-based only: memory_gb, core_clock, boost_clock.
- `workstation`: benchmark family = multi-core; signal = multi-core score + cores/threads.
- `productivity`: benchmark family = single-core; signal = single-core score + base clock.
- `content_creation`: benchmark family = multi-core + single-core (VRAM for GPU).
- `ai_ml`: requires GPU benchmark/VRAM evidence â†’ `unrated: "insufficient_data"` for both CPU and GPU in this dataset.

Rating: map a normalized percentile of the workload-relevant signal to stars 0â€“5:
- Compute `raw_score` between 0 (weakest evidence tier) and 5 (strongest).
- When evidence quality is `low` AND spec_based, cap stars at 3 (never 4â€“5 on weak evidence).
- Return `spec_based`, `rationale`, `caveats`, `confidence`, `evidence_quality` inline.

- [ ] **Step 4: Run test to verify it passes** â€” `pytest backend/app/test_suitability_service.py` â€” expected PASS.

- [ ] **Step 5: Commit**

`git add backend/app/services/suitability_service.py backend/app/test_suitability_service.py`
`git commit -m "feat(suitability): workload-aware 0-5 suitability ratings"`

---

## Task 4: Suitability API Schemas

**Files:**
- Create: `backend/app/schemas/suitability.py`
- Modify: `backend/app/schemas/__init__.py`

**Interfaces:**
- Consumes: `rate_suitability` and `score_evidence_quality` output dicts
- Produces: Pydantic models for the wire contract

- [ ] **Step 1: Write the Pydantic schemas** (`backend/app/schemas/suitability.py`)

```python
class EvidenceQualityResponse(BaseModel):
    score: float          # 0-1
    confidence: Literal["high", "medium", "low"]
    signals: dict[str, bool]
    benchmark_present: bool
    spec_complete: bool
    reason: str | None

class SuitabilityRatingResponse(BaseModel):
    category: str
    stars: int            # 0-5 (0 when unrated)
    raw_score: float      # 0-5
    confidence: Literal["high", "medium", "low", "unrated"]
    spec_based: bool
    rationale: list[str]
    caveats: list[str]
    evidence_quality: EvidenceQualityResponse | None
    unrated_reason: str | None = None  # set when confidence == "unrated"

class HardwareSuitabilityResponse(BaseModel):
    hardware_id: int
    hardware_name: str
    hardware_type: str
    ratings: list[SuitabilityRatingResponse]

class WorkloadRequest(BaseModel):
    category: Literal["gaming", "workstation", "productivity", "content_creation", "ai_ml"]
    resolution: Literal["1080p", "1440p", "4k"] | None = None
    target_fps: int | None = Field(default=None, ge=30, le=240)
```

- [ ] **Step 2: Export from `__init__.py`** â€” add the new models to the schemas `__init__.py` exports.

- [ ] **Step 3: Write a basic round-trip test**

```python
def test_suitability_response_round_trip():
    r = SuitabilityRatingResponse(
        category="gaming", stars=4, raw_score=4.0,
        confidence="medium", spec_based=True,
        rationale=["Strong 8-core CPU with 4.2 GHz boost"],
        caveats=["No gaming-specific benchmark data available"],
        evidence_quality=EvidenceQualityResponse(
            score=0.5, confidence="medium",
            signals={"benchmark_present": False, "spec_complete": True, ...},
            benchmark_present=False, spec_complete=True, reason=None
        ),
        unrated_reason=None
    )
    assert r.model_validate(r.model_dump()) == r
```

- [ ] **Step 4: Commit**

`git add backend/app/schemas/suitability.py backend/app/schemas/__init__.py`
`git commit -m "feat(schemas): suitability API Pydantic wire models"`

---

## Task 5: Suitability API Endpoints

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/app/test_suitability_api.py`

**Interfaces:**
- Consumes: `rate_suitability`, `score_evidence_quality` from `suitability_service`
- Produces: `GET /hardware/{id}/suitability`, `GET /hardware/{id}/suitability/{category}`

- [ ] **Step 1: Write the failing API tests** (`backend/app/test_suitability_api.py`)

```python
def test_suitability_returns_unrated_for_gpu_ai_ml(client, gpu_hardware):
    resp = client.get(f"/hardware/{gpu_hardware.id}/suitability")
    assert resp.status_code == 200
    ai_ratings = [r for r in resp.json()["ratings"] if r["category"] == "ai_ml"]
    assert ai_ratings[0]["confidence"] == "unrated"

def test_suitability_is_spec_based_when_no_benchmark(client, cpu_no_benchmark):
    resp = client.get(f"/hardware/{cpu_no_benchmark.id}/suitability")
    assert any(r["spec_based"] for r in resp.json()["ratings"])

def test_suitability_detail_single_category(client, cpu_hardware):
    resp = client.get(f"/hardware/{cpu_hardware.id}/suitability/workstation")
    assert resp.status_code == 200
    assert resp.json()["category"] == "workstation"
```

- [ ] **Step 2: Run test to verify it fails** â€” expected FAIL (endpoint not defined).

- [ ] **Step 3: Implement the endpoints in `main.py`**

```python
@app.get(
    "/hardware/{hardware_id}/suitability",
    response_model=HardwareSuitabilityResponse,
)
def get_hardware_suitability(hardware_id: int) -> HardwareSuitabilityResponse:
    """Workload-aware suitability ratings with evidence quality for all categories."""
    with SessionLocal() as session:
        hardware = session.get(Hardware, hardware_id,
                              options=[selectinload(Hardware.cpu_specification),
                                       selectinload(Hardware.gpu_specification),
                                       selectinload(Hardware.benchmark_results)])
        if not hardware:
            raise HTTPException(status_code=404, detail="Hardware not found")

    categories = ["gaming", "workstation", "productivity", "content_creation", "ai_ml"]
    ratings = [rate_suitability(hardware, cat) for cat in categories]
    return HardwareSuitabilityResponse(
        hardware_id=hardware.id,
        hardware_name=hardware.name,
        hardware_type=hardware.type,
        ratings=ratings,
    )

@app.get(
    "/hardware/{hardware_id}/suitability/{category}",
    response_model=SuitabilityRatingResponse,
)
def get_hardware_suitability_category(
    hardware_id: int,
    category: str,
) -> SuitabilityRatingResponse:
    VALID = {"gaming", "workstation", "productivity", "content_creation", "ai_ml"}
    if category not in VALID:
        raise HTTPException(status_code=422, detail=f"Invalid category: {category}")
    # ... same hardware loading logic ...
    result = rate_suitability(hardware, category)
    return SuitabilityRatingResponse(**result)
```

- [ ] **Step 4: Run tests to verify they pass** â€” `pytest backend/app/test_suitability_api.py -q` â€” expected PASS.

- [ ] **Step 5: Commit**

`git add backend/app/main.py backend/app/test_suitability_api.py`
`git commit -m "feat(api): suitability rating endpoints (all categories + per-category)"`

---

## Task 6: Recommendation Engine (Objective E)

**Files:**
- Create: `backend/app/services/recommendation_service.py`
- Create: `backend/app/schemas/recommendation.py`
- Test: `backend/app/test_recommendation_service.py`

**Interfaces:**
- Consumes: `rate_suitability`, `score_evidence_quality`; `hardware_catalog_service`
- Produces: `recommend(hardware_type, workload, budget_max=None, limit=10) -> list[dict]`

The recommendation service filters and ranks hardware without fabricating scores.

- [ ] **Step 1: Write the failing tests** (`backend/app/test_recommendation_service.py`)

```python
def test_recommend_excludes_unrated_for_ai_ml():
    result = recommend("GPU", "ai_ml", limit=10)
    assert len(result) == 0
    # All GPU AI/ML ratings are unrated in this dataset (no GPU benchmarks)

def test_recommend_respects_evidence_threshold():
    # Hardware with high evidence quality AND score >= 3 stars gets recommended
    result = recommend("CPU", "gaming", limit=5)
    for item in result:
        assert item["suitability"]["confidence"] in ("high", "medium")
        assert item["suitability"]["stars"] >= 3

def test_recommend_ranks_by_stars_then_evidence():
    result = recommend("CPU", "gaming", limit=10)
    stars = [r["suitability"]["stars"] for r in result]
    assert stars == sorted(stars, reverse=True)

def test_recommend_filters_by_hardware_type():
    result = recommend("GPU", "gaming", limit=10)
    for item in result:
        assert item["hardware"]["type"] == "GPU"

def test_recommend_empty_when_no_candidates_pass_threshold():
    result = recommend("GPU", "ai_ml", limit=10)
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails** â€” expected FAIL.

- [ ] **Step 3: Implement `recommend(...)` in `recommendation_service.py`**

Algorithm:
1. Query hardware catalog filtered by `hardware_type` (CPU or GPU).
2. For each hardware, load specs + benchmarks + evidence quality.
3. Compute `rate_suitability(hw, workload)`.
4. Filter: keep only candidates where `confidence != "unrated"` AND (`confidence == "high"` OR `stars >= 3`).
5. Rank: primary key = stars (descending), secondary key = evidence quality score (descending).
6. Return top `limit` results with: hardware summary, suitability rating, evidence quality, explanation reasons.

Note: budget filtering is not implemented in this delivery (no pricing data). The `budget_max` parameter is accepted but has no effect (documented as deferred).

- [ ] **Step 4: Run tests to verify they pass** â€” `pytest backend/app/test_recommendation_service.py -q` â€” expected PASS.

- [ ] **Step 5: Commit**

`git add backend/app/services/recommendation_service.py backend/app/schemas/recommendation.py backend/app/test_recommendation_service.py`
`git commit -m "feat(recommend): deterministic recommendation engine with evidence threshold"`

---

## Task 7: Recommendation API Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/schemas/recommendation.py`
- Test: `backend/app/test_suitability_api.py` (add recommendation tests)

**Interfaces:**
- Consumes: `recommend` from `recommendation_service`
- Produces: `GET /hardware/recommend`

- [ ] **Step 1: Write the failing test**

```python
def test_recommend_returns_empty_for_gpu_ai_ml(client):
    resp = client.get("/hardware/recommend", params={"type": "GPU", "workload": "ai_ml"})
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []
    assert "no candidates passed evidence threshold" in resp.json()["filter_reason"]
```

- [ ] **Step 2: Implement the endpoint**

```python
@app.get(
    "/hardware/recommend",
    response_model=RecommendationResponse,
)
def get_recommendations(
    type: str = Query(..., alias="type"),
    workload: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
) -> RecommendationResponse:
    """Ranked hardware recommendations for a workload, filtered by evidence quality."""
```

- [ ] **Step 3: Run tests** â€” `pytest backend/app/test_suitability_api.py -k recommend -q` â€” expected PASS.

- [ ] **Step 4: Commit**

`git add backend/app/main.py backend/app/schemas/recommendation.py`
`git commit -m "feat(api): GET /hardware/recommend endpoint"`

## Task 8: Frontend â€” SuitabilityCard Component

**Files:**
- Create: `frontend/src/components/SuitabilityCard.jsx`
- Create: `frontend/src/hooks/useSuitability.js`
- Test: `frontend/src/suitability.test.js`

**Interfaces:**
- Consumes: `/hardware/{id}/suitability` API response (`HardwareSuitabilityResponse`)
- Produces: React `<SuitabilityCard>` sub-component

- [ ] **Step 1: Write the failing test** (`frontend/src/suitability.test.js`)

```javascript
import { render, screen } from '@testing-library/react';
import SuitabilityCard from './components/SuitabilityCard';

test('shows stars when rating has stars', () => {
  render(SuitabilityCard({ category: 'gaming', stars: 4, confidence: 'medium', spec_based: false }));
  expect(screen.getByText('4')).toBeInTheDocument();
});

test('shows unrated with reason when confidence is unrated', () => {
  render(SuitabilityCard({ category: 'ai_ml', stars: 0, confidence: 'unrated', unrated_reason: 'insufficient_data_no_gpu_benchmarks' }));
  expect(screen.getByText(/insufficient data/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails** â€” `node --test src/suitability.test.js` â€” expected FAIL.

- [ ] **Step 3: Implement `useSuitability.js` hook**

```javascript
// frontend/src/hooks/useSuitability.js
export function useSuitability(hardwareId) {
  // fetches GET /hardware/{id}/suitability
  // returns { data, loading, error }
}
```

- [ ] **Step 4: Implement `SuitabilityCard.jsx`**

Displays one category's rating:
- Star rating (0â€“5 filled/empty stars) when `confidence !== "unrated"`.
- Evidence quality badge (high/medium/low colored indicator).
- `spec_based` indicator (icon/label when no benchmarks contributed).
- Rationale bullets (first 2â€“3 reasons).
- Caveats (shown as warning/info text when present).
- Missing evidence indicators (which signals were false).
- Accessible: uses `<abbr>` for star ratings, aria-label per WCAG.

- [ ] **Step 5: Run tests to verify they pass** â€” `node --test src/suitability.test.js` â€” expected PASS.

- [ ] **Step 6: Commit**

`git add frontend/src/components/SuitabilityCard.jsx frontend/src/hooks/useSuitability.js frontend/src/suitability.test.js`
`git commit -m "feat(frontend): SuitabilityCard component with star rating + evidence display"`

---

## Task 9: Frontend â€” HardwareFitModal (Objective D)

**Files:**
- Create: `frontend/src/components/HardwareFitModal.jsx`
- Create: `frontend/src/hooks/useRecommendation.js`
- Test: `frontend/src/hardware-fit-modal.test.js`

**Interfaces:**
- Consumes: `useSuitability` hook + `/hardware/recommend` endpoint
- Produces: Full-screen modal with interactive Hardware Fit experience

- [ ] **Step 1: Write the failing test** (`frontend/src/hardware-fit-modal.test.js`)

- [ ] **Step 2: Implement `useRecommendation.js` hook**

```javascript
// frontend/src/hooks/useRecommendation.js
export function useRecommendation({ hardwareType, workload, limit }) {
  // fetches GET /hardware/recommend?type=GPU&workload=gaming&limit=10
  // returns { data, loading, error }
}
```

- [ ] **Step 3: Implement `HardwareFitModal.jsx`**

The modal allows the user to:
1. Select primary workload (5 categories as tabs/buttons).
2. Optionally select gaming resolution (1080p/1440p/4k) â€” passed as query param.
3. Optionally select target FPS â€” passed as query param.
4. See the current hardware's suitability cards (one per category).
5. See top-3 alternatives from the recommendation engine with comparison rationale.
6. See evidence coverage and confidence for each option.
7. "Compare" button pre-populates the comparison view.

Layout: full-width modal, responsive (mobile collapses to stacked cards), accessible (focus trap, ESC closes, aria-modal).

- [ ] **Step 4: Run tests to verify they pass** â€” `node --test src/hardware-fit-modal.test.js` â€” expected PASS.

- [ ] **Step 5: Commit**

`git add frontend/src/components/HardwareFitModal.jsx frontend/src/hooks/useRecommendation.js frontend/src/hardware-fit-modal.test.js`
`git commit -m "feat(frontend): HardwareFitModal â€” interactive workload selection + recommendations"`

---

## Task 10: Frontend Integration â€” Detail Page + Comparison View

**Files:**
- Modify: `frontend/src/App.jsx`, `frontend/src/components/ChatView.jsx`
- Add: suitability panel in hardware detail section

**Interfaces:**
- Consumes: `SuitabilityCard`, `HardwareFitModal`, `useSuitability`
- Produces: Hardware Fit button appears on hardware detail pages

- [ ] **Step 1: Add "Hardware Fit" button in hardware detail section of `App.jsx`**

In the hardware detail rendering area (near the benchmark section or below the spec table), add a "Hardware Fit" button that opens the `HardwareFitModal` for the currently viewed hardware.

```javascript
// Inside hardware detail panel
<button onClick={() => setShowFit(true)} className="hardware-fit-btn">
  Hardware Fit
</button>
{showFit && (
  <HardwareFitModal
    hardwareId={hardware.id}
    hardwareName={hardware.name}
    onClose={() => setShowFit(false)}
  />
)}
```

- [ ] **Step 2: Add suitability summary to comparison view**

In the comparison detail view (`App.jsx`), add a `SuitabilitySummary` row below the spec comparison table showing side-by-side ratings for the selected workload (switchable via a dropdown).

- [ ] **Step 3: Verify tests pass** â€” `node --test src/*.test.js -q` â€” expected PASS (no new regressions).

- [ ] **Step 4: Build** â€” `npm.cmd run build` â€” expected green.

- [ ] **Step 5: Commit**

`git add frontend/src/App.jsx`
`git commit -m "feat(frontend): integrate HardwareFitModal into hardware detail and comparison views"`

---

## Task 11: Regression + Sensitivity Tests

**Files:**
- Extend: `backend/app/test_suitability_service.py`
- Add: `backend/app/test_suitability_scoring.py`

- [ ] **Step 1: Add boundary/sensitivity tests**

```python
def test_suitability_same_input_always_same_output():
    # Run the same hardware through 100 iterations
    for _ in range(100):
        assert rate_suitability(hw, "gaming") == rate_suitability(hw, "gaming")

def test_all_categories_return_valid_stars():
    for cat in CATEGORIES:
        r = rate_suitability(hw, cat)
        assert 0 <= r["stars"] <= 5

def test_evidence_quality_score_in_0_to_1():
    r = score_evidence_quality(hw, "gaming")
    assert 0.0 <= r["score"] <= 1.0
```

- [ ] **Step 2: Run full suite** â€” `pytest backend -q` â€” expected 815+ PASS.

- [ ] **Step 3: Commit**

`git add backend/app/test_suitability_service.py backend/app/test_suitability_scoring.py`
`git commit -m "test(suitability): sensitivity and regression test suite"`

---

## Task 12: Documentation + Final Verification

**Files:**
- Create: `docs/SCORING_METHODOLOGY.md`
- Create: `docs/EVIDENCE_GAPS.md`
- Modify: `docs/SPECTRA_V2_ROADMAP.md` (add Phase H status)

- [ ] **Step 1: Write `docs/SCORING_METHODOLOGY.md`**

Documents (for each of the 5 workload categories):
- Evidence quality formula (weighted signals, weights, confidence thresholds)
- Suitability scoring formula (stars mapping, spec_based logic, rationale generation)
- Version string (e.g., `v1.0.0`)
- Reference baseline (Geekbench 7 multi-core, percentile calculation)
- Reproducibility guarantee (same input â†’ identical output)
- What constitutes insufficient data for each category

- [ ] **Step 2: Write `docs/EVIDENCE_GAPS.md`**

Lists:
- GPU benchmark coverage: 0 / 1,879 (0%)
- CPU benchmark coverage: 518 / 3,501 (14.8%)
- Fields without provenance by category
- AI/ML: why it cannot be rated (no VRAM benchmarks, no CUDA/OpenCL benchmark data)
- Remaining data collection priorities (ranked by impact)
- Licensing notes (Geekbench 7: restricted/clear boundary, GPU Ark: CC BY 4.0)

- [ ] **Step 3: Full regression** â€” `pytest backend -q` + `node --test src/*.test.js` + `npm.cmd run build` + `npx.cmd oxlint src`

Expected:
- Backend: 815+ PASS, 2 skipped, 1 warning (pre-existing)
- Frontend: 599+ PASS, 0 fail
- Vite build: green
- Oxlint: 1 pre-existing warning only

- [ ] **Step 4: Commit**

`git add docs/SCORING_METHODOLOGY.md docs/EVIDENCE_GAPS.md`
`git commit -m "docs: scoring methodology v1.0.0 + evidence gaps report"`

---

## Execution Summary (for the agent)

After all tasks are done, push to `feature/spectra-delivery-20261028` and verify the remote SHA.

**Final commit sequence** (12 tasks = 12 commits or logical groups):
1. `feat(completeness): read-only catalog completeness audit pipeline`
2. `feat(suitability): evidence quality scoring (objective C)`
3. `feat(suitability): workload-aware 0-5 suitability ratings (objective B)`
4. `feat(schemas): suitability API Pydantic wire models`
5. `feat(api): suitability rating endpoints`
6. `feat(recommend): deterministic recommendation engine with evidence threshold`
7. `feat(api): GET /hardware/recommend endpoint`
8. `feat(frontend): SuitabilityCard component with star rating + evidence display`
9. `feat(frontend): HardwareFitModal â€” interactive workload selection + recommendations`
10. `feat(frontend): integrate HardwareFitModal into hardware detail and comparison views`
11. `test(suitability): sensitivity and regression test suite`
12. `docs: scoring methodology v1.0.0 + evidence gaps report`

**Status table (final report format):**

| Objective | Status | Notes |
|---|---|---|
| A â€” Completeness audit | âœ… Fully implemented | Read-only script + audit doc |
| B â€” Suitability engine | âœ… Fully implemented | 5 categories, stars + evidence + caveats |
| C â€” Evidence scoring | âœ… Fully implemented | Separate dimension, versioned, deterministic |
| D â€” User experience | âœ… Fully implemented | HardwareFitModal + SuitabilityCard + detail + comparison |
| E â€” Recommendation engine | âœ… Fully implemented | Deterministic rank, evidence threshold filter |
| F â€” Validation & delivery | âœ… Fully implemented | Tests, docs, scoring methodology, gaps report |
| GPU gaming | âš ï¸ Evidence-limited | Spec-based only, declared, confidence reduced |
| GPU AI/ML | âš ï¸ Evidence-limited | No GPU benchmarks â†’ unrated, documented |
| CPU gaming | âœ… Tested | Benchmark-driven for 518 hardware |
| CPU workstation | âœ… Tested | Multi-core benchmark signals |
| Recommendation | âœ… Tested | Evidence threshold, rank stability |
| Production DB | ðŸ”’ Preserved | No writes, copy-only |
| Auth | ðŸ”’ Preserved | Not activated |
| Existing tests | âœ… Green | 815+ backend / 599+ frontend |
