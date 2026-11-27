# SPECTRA M4 — Explainable Hardware Recommendation & Build Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native execution — the mission mandates executing now, no stop after planning). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Evolve SPECTRA into an explainable hardware decision-support platform: scenario scoring, workload profiles, deterministic recommendations, build intelligence, and bounded build optimization — evidence-gated, versioned, deterministic.

**Architecture:** Extend existing deterministic engines (suitability_service v1, recommendation_service v1, compatibility engine M32-RULES-v2, frontend buildIntelligence) rather than replacing them. New pure feature layer (`intelligence_features.py`) normalizes catalog fields; scenario-scoring engine v2 composes features + evidence into versioned explainable scenario ratings; workload profiles parameterize it; recommendation + optimization engines consume scenario scores plus the existing compatibility engine; the Gemini chat service gains a structured digest of engine outputs (deterministic fallback stays authoritative).

**Tech Stack:** FastAPI 0.128.1 / SQLAlchemy 2.0.52 / pydantic 2.12.5 / pytest; React 19 + Vite 8 + `node --test`; SQLite isolated dev DB (`data/spectra.db` copied from M3.3 rehearsal snapshot — production untouched).

**Spec:** Mission brief TASK 0–10 + global constraints; methodology baseline `docs/SCORING_METHODOLOGY.md` v1.0.0 (extended, never mutated).

## Global Constraints

- No fabricated benchmarks, prices, FPS, specs, or evidence; no false precision (UNKNOWN is first-class).
- No evidence-gate bypass; no production DB writes; no deployment; no force-push; no merge (draft PR only).
- No interference with M3.4 or shared infra files (deployment/auth config, `.github/workflows/ci.yml`, compose files, `backend/app/auth.py`, `release.py`).
- Backward compatibility: existing v1 API payloads keep their shape; all M4 additions are additive fields/endpoints.
- Determinism: pure functions, versioned constants, `SCORING_VERSION = "M4-SCORING-v2.0"`, tie-breaking by (score desc, evidence desc, id asc).
- Budget/value scoring: dataset has NO price columns → VALUE always returns UNKNOWN with `missing_data:["price"]`. Never estimate.
- Working dir: `C:\Users\user\spectra-m4` (worktree `feat/m4-intelligence`, base 5c2c7d9). Backend venv `backend\.venv`; DB env var: `SPECTRA_DATABASE_URL=sqlite:///data/spectra.db` (absolute).

## Review Focus (failure modes → owning tests)

1. **Missing-vs-zero conflation** — a CPU with `boost_clock_ghz=NULL` must never score as "0 GHz"; feature layer must emit `None` + `missing` flag. Test: Task 2.
2. **Confidence inflation on incomplete data** — spec-only ratings must stay capped (≤3 stars, ≤medium confidence) even when normalized features look strong. Test: Task 3.
3. **Fabricated prices/derived FPS** — value scoring and resolution-tier logic must return UNKNOWN/qualitative only. Tests: Tasks 4, 5.
4. **Determinism under ties & repeated runs** — identical catalog state → identical ranking, including id-asc tie-break. Test: Task 6.
5. **Partial-build honesty** — builds missing components must never be declared COMPATIBLE; optimization must return partial results with named gaps, not fake complete builds. Test: Task 7.

## Task 0 (complete): Intelligence audit

Audited (evidence in session, recorded in `docs/m4/M4_INTELLIGENCE_ARCHITECTURE.md` §2):
- Catalog: 5380 hardware rows (3501 CPU, 1879 GPU; segments mobile/server/workstation on 2494), 1040 Geekbench 7 rows (518 CPUs × single/multi-core), 39,378 verified provenance rows.
- Spec coverage (M3.3 snapshot): CPU boost 2425/3501, socket 3311, tdp 3224, node 2473; GPU memory_gb 1538, bandwidth 1538, tdp 1675, interface 849.
- Gaps: **zero price data** (no price columns in any table), GPU benchmarks = 0, recorded_at NULL, RAM/storage/motherboard/PSU spec tables empty in snapshot (manifests exist in data/research, not loaded).
- Existing engines: suitability v1 (5 workloads, anchors p10–p90, spec-cap 3★), recommendation v1 (threshold + stars/evidence rank, budget accepted-but-inert), compatibility M32-RULES-v2 (9 rules, 4-state model), benchmark_quality (4-signal + veto), comparison (CPU/GPU metrics + AI explanation), build chat (15+35+42-rule prompt, JSON response), provenance (verified/uncertain/excluded/unmatched).
- Baselines: backend 1544 passed/2 skipped/2 deselected (60s); frontend 693 tests pass, build OK, oxlint pre-existing warnings only.
- AI: Gemini via `explanation_service.generate_chat_response`; 503 + deterministic path when unconfigured.

## File Structure (M4 additions)

```
backend/app/
  services/intelligence_features.py      # T1: pure feature layer (normalize, missing≠zero, provenance)
  services/scenario_scoring.py           # T2: scenario engine v2 (gaming/workstation/daily/value)
  services/workload_profiles.py          # T3: 8 workload profiles + preferences dataclass
  services/recommendation_service.py     # T4: EXTEND (constraints, alternatives, exclusions, confidence)
  services/build_intelligence_service.py # T5: balance/workload/compat/upgrades/power (extends M32-RULES-v2 use)
  services/build_optimizer.py            # T6: bounded deterministic candidate search
  schemas/intelligence.py                # T2-T6: wire models (additive)
  main.py                                # T4-T7: new routes only (no edits to existing routes)
frontend/src/
  intelligence.js                        # T7: pure display layer + node --test tests
  components/ScenarioRatings.jsx         # T7: expandable scoring explanation panel
  components/BuildIntelligencePanel.jsx  # T7: build panel extension
  hooks/useScenarioRatings.js            # T7: fetch hook
docs/m4/ M4_*.md                         # T8: seven deliverable docs
backend/tests/ (new files)               # per-task test files
```

**Interfaces (locked):**
- `features_from_hardware(hw_row: dict) -> FeatureVector` (dict of `value|None`, `missing:[...]`, `coverage:0..1`)
- `score_scenarios(features: FeatureVector, evidence: EvidenceBundle, profile: WorkloadProfile) -> ScenarioSet` (dict with `scenarios:{name:{score,stars,confidence,contributing_factors[],limitations[],data_coverage}}`, `scoring_version`, `reference_population`)
- `score_workload_features(features, weights: dict, anchors: tuple, family: str) -> (score0..5, factors)`
- `recommend_intelligent(session, constraints: RecommendationConstraints) -> RecommendationResult`
- `analyze_build(component_ids: dict) -> BuildIntelligenceReport`
- `optimize_build(session, objective: str, constraints) -> OptimizationResult`
- Profile registry: `PROFILES: dict[str, WorkloadProfile]` keys: esports_gaming, aaa_gaming, general_productivity, software_development, video_editing, rendering_3d, virtualization_homelab, ai_ml_experimentation.

## Implementation Tasks

### Task 1 (Mission T1): Feature layer — `intelligence_features.py`

**Files:** Create `backend/app/services/intelligence_features.py`; Test `backend/app/test_intelligence_features.py`.

**Interfaces (Produces):** `FEATURE_VERSION="M4-FEATURES-v1"`; `features_from_hardware(hw) -> dict` where `hw` is a duck-typed Hardware (or dict); returns:
```
{
  "type": "CPU"|"GPU",
  "features": {"single_core_score": float|None, "multi_core_score": float|None,
               "cores": int|None, "threads": int|None, "base_clock_ghz": ..., "boost_clock_ghz": ...,
               "tdp_w": ..., "memory_gb": ..., "vram_bandwidth_gbps": ..., "core_clock_mhz": ...,
               "boost_clock_mhz": ..., "memory_bus_width_bits": ..., "efficiency": float|None,
               "architecture": str|None, "segment": str|None, "release_date": ...},
  "missing": [str, ...],          # names of features that are None (absent)
  "coverage": float,              # 0..1 non-null share of the applicable feature set
  "provenance_verified_fields": [str, ...],
  "benchmark_families": [str, ...],  # e.g. ["single-core","multi-core"]
  "data_freshness": {"recorded_at_present": bool, "latest_recorded_at": str|None}
}
```
- `normalise(v, lo, hi) -> float|None`: min-max to 0..1; None passes through as None; value outside [lo,hi] clamps (never extrapolates).
- `derive_efficiency(multi_core_score, tdp_w) -> float|None`: score/tdp, None when either missing or tdp<=0.
- Rules: missing ≠ zero — every absent value stays None and is listed in `missing`; benchmark scores picked as MAX per family; only families observed on the row appear in `benchmark_families`.

- [ ] Step 1: Write failing tests: missing-vs-zero (boost NULL → `missing` contains "boost_clock_ghz", value None); GPU feature set applies only to type GPU; coverage math (3 of 6 CPU features → 0.5); efficiency None on tdp=0; normalise clamps; determinism (same input twice identical).
- [ ] Step 2: Run `python -m pytest backend/app/test_intelligence_features.py -q` → FAIL (module missing).
- [ ] Step 3: Implement per the contract above.
- [ ] Step 4: Re-run → PASS. Also run `test_suitability_scoring.py` to prove no v1 regression.
- [ ] Step 5: Commit `feat(m4): T1 deterministic feature layer (missing≠zero, coverage, provenance)`.

### Task 2 (Mission T2): Scenario scoring engine v2 — `scenario_scoring.py`

**Files:** Create `backend/app/services/scenario_scoring.py`; Test `backend/app/test_scenario_scoring.py`.

**Interfaces (Consumes: T1 features; Produces):** `SCORING_VERSION="M4-SCORING-v2.0"`; constants:
- `REFERENCE_POPULATION = "Geekbench 7 scores of the 518 benchmarked CPUs in the M3.3 production-like snapshot; percentile anchors p10/p25/p50/p75/p90 recomputed deterministically from benchmark_results"`
- Anchors are DERIVED, not hardcoded: `derive_anchors(scores: list[float]) -> tuple5` = linear interpolation of percentiles (10,25,50,75,90) over sorted scores. For the M3.3 snapshot these land near the v1 documented values — assert closeness in tests (tolerance ±10%) to show continuity, then use derived values.
- Scenario registry `SCENARIOS = ("gaming","workstation","daily","value")` each with: feature weights (gaming: multi_core 0.5, single_core 0.2, memory 0.1(vram or none), efficiency 0.2; workstation: multi 0.45, single 0.2, cores 0.2, efficiency 0.15; daily: single 0.6, efficiency 0.4; value: price required → else UNKNOWN).
- `score_scenarios(features, evidence_bundle, profile=None) -> dict` returns per scenario:
```
{"score": 0..5 float, "stars": int 0..5, "confidence": "high|medium|low|unknown",
 "data_coverage": 0..1, "contributing_factors": [{"feature","weight","normalized","present"}...],
 "limitations": [str...], "spec_based": bool, "scoring_version": "M4-SCORING-v2.0"}
```
- Evidence gates (all must hold or scenario → `"score": None, "confidence": "unknown", "limitations": [reason]`):
  1. Benchmark-driven (spec_based=False) requires the scenario's family in `benchmark_families`; stars = anchor interpolation (reuse v1 `_score_to_stars` semantics via import, not reimplementation).
  2. Spec-based fallback: allowed only when the type's key specs are non-null; capped ≤3.0 score AND ≤"medium" confidence (strengthens v1: explicit cap on continuous score, matching `SPEC_BASED_MAX_STARS`).
  3. VALUE: requires price in evidence_bundle; dataset has none → always UNKNOWN with `limitations=["missing_data:price"]`. Tests pin that value NEVER returns a numeric score from this dataset.
- Resolution handling: gaming accepts profile resolution; WITHOUT GPU benchmark data it can only add a *limitation string* ("no GPU gaming evidence; resolution tier not applied to measured performance") — never changes the numeric CPU score. Test pins this.
- Monotonicity: score is non-decreasing in the primary family score (property test over a synthetic ladder).
- No recency bonus: two CPUs differing only in release_date get identical scores. Test pins.

- [ ] Step 1: Failing tests: anchors derivation + v1-continuity; gaming/workstation/daily weighted composition; spec-cap; value UNKNOWN; unknown-when-no-evidence; monotonicity property; no-recency-bias; confidence mapping; contributing_factors include only present features; version string in payload.
- [ ] Step 2: Run → FAIL. Step 3: Implement. Step 4: Run → PASS + full v1 suites still green.
- [ ] Step 5: Commit `feat(m4): T2 scenario scoring engine v2 (derived anchors, evidence gates, value=UNKNOWN w/o price)`.

### Task 3 (Mission T3): Workload profiles — `workload_profiles.py`

**Files:** Create `backend/app/services/workload_profiles.py`; Test `backend/app/test_workload_profiles.py`.

**Interfaces (Consumes: T2; Produces):**
```
@dataclass(frozen=True) WorkloadProfile: key, label, description, scenario_weights (dict scenario→0..1),
  feature_weight_overrides (dict), evidence_requirements (tuple of str), assumptions (tuple of str),
  supported_preferences (tuple of str)
PROFILES: dict[str, WorkloadProfile]  # 8 keys per mission
PROFILE_KEYS = tuple(PROFILES)
resolve_profile(key: str | None) -> WorkloadProfile  # None → default general_productivity; unknown → KeyError with friendly msg
apply_preferences(profile, prefs: dict) -> WorkloadProfile  # validated subset; unknown prefs raise ValueError
```
- Eight profiles with scenario_weights summing to 1.0 (validated in test) mapping to T2 scenarios; e.g. esports_gaming {gaming:0.85, daily:0.15, value:0.0}, video_editing {workstation:0.7, gaming:0.0, daily:0.1, value:0.2}, ai_ml_experimentation {workstation:0.8, daily:0.2} with an assumption string stating GPU-compute evidence absent in this dataset.
- Preferences: `resolution` (1080p/1440p/4k, gaming profiles only), `budget_max` (accepted; only affects value scenario which is UNKNOWN without price data — documented), `power_limit_w` (advisory only, adds limitation when tdp unknown), `priority` (performance|efficiency|balanced → reweights within documented bounds), `existing_components` (dict, passed through to recommendations).
- Every profile carries `assumptions` naming exactly which evidence the profile relies on and which claims it does NOT make (e.g., esports_gaming: "uses CPU multi-core as proxy; no game-specific FPS data exists in this dataset").

- [ ] Step 1: Failing tests: 8 keys; weights sum to 1.0 per profile; resolve default; unknown profile raises; preference validation (resolution on non-gaming → ValueError; priority reweight bounded; budget_max accepted); every profile has non-empty assumptions; profile→T2 integration (score_scenarios accepts profile).
- [ ] Step 2: FAIL → Step 3: Implement → Step 4: PASS.
- [ ] Step 5: Commit `feat(m4): T3 eight workload profiles with documented assumptions + preferences`.

### Task 4 (Mission T4): Intelligent recommendations — extend `recommendation_service.py`

**Files:** Modify `backend/app/services/recommendation_service.py` (additive); Create `backend/app/schemas/intelligence.py` (RecommendationConstraints, RecommendationResult wire models); Test `backend/app/test_recommendation_intelligent.py`.

**Interfaces (Consumes: T1-T3; Produces):**
```
@dataclass RecommendationConstraints: hardware_type, profile_key|None, budget_max|None,
  resolution|None, power_limit_w|None, priority|None, limit=10, existing_components: dict
recommend_intelligent(session_factory, constraints) -> dict:
{
 "candidates": [{hardware_id, hardware_name, hardware_type, scenario_scores, stars, confidence,
                 evidence, rank_explanation: [str], trade_offs: [str], provenance_refs: [..]}...],
 "alternatives": [...same shape, ranked 11..20 or evidence-boundary cases...],
 "excluded": [{hardware_id, reason_code, reason}...top 5],
 "constraints_echo": {...with classification: hard|soft|unknown|estimated per field},
 "profile": {key, label, assumptions}, "ranking_version": "M4-REC-v2.0", "deterministic": true
}
```
- Constraint classification: hardware_type+profile = hard; budget_max = soft (value UNKNOWN w/o price → stated, never filters); power_limit_w = soft-advisory (filters only when tdp_w present AND exceeds limit + documented margin; else UNKNOWN note); resolution = soft; existing_components = context for compatibility notes.
- Hard incompatibility exclusion: when existing_components contains a motherboard, candidates whose socket (both sides present) mismatches are EXCLUDED with reason_code `SOCKET_MISMATCH` (reuse M32-RULES-v2 rule fn — do not duplicate logic). Missing socket data → NO exclusion, UNKNOWN noted.
- Ranking: scenario-weighted score desc, then evidence-quality desc, then hardware_id asc (deterministic tie-break). Alternatives = next ranked + one contrasting trade-off pick (e.g., highest-efficiency candidate outside top-5).
- Exclusion ledger: unrated-by-evidence-gate candidates appear with `insufficient_data:*` reason codes; count summary included.
- v1 `recommend()`/`recommend_response()` stay byte-identical in behavior (existing tests must pass untouched).

- [ ] Step 1: Failing tests: ranking determinism incl. tie-break by id; budget constraint classified soft and never filters; power filter only with tdp evidence; socket-mismatch exclusion via existing motherboard; UNKNOWN socket does not exclude; exclusion ledger with reason codes; alternatives shape; v1 functions unchanged (run existing test_recommendation* files); empty result → helpful filter_reason.
- [ ] Step 2: FAIL → Step 3: Implement (extend file; new code paths only) → Step 4: PASS + all prior backend suites green.
- [ ] Step 5: Add routes in `main.py` (ADDITIVE): `GET /hardware/recommend/v2` (query params mirror constraints) and `POST /hardware/recommend/v2` (JSON body). Wire models in `schemas/intelligence.py`. Commit `feat(m4): T4 intelligent recommendations (constraints, alternatives, exclusions, /v2 endpoint)`.

### Task 5 (Mission T5): Build intelligence — `build_intelligence_service.py`

**Files:** Create `backend/app/services/build_intelligence_service.py`; Test `backend/app/test_build_intelligence_service.py`.

**Interfaces (Consumes: T2 features + compatibility_service.check_build_compatibility; Produces):**
```
analyze_build(component_ids: dict[str, int|None]) -> dict:
{
  "component_presence": {slot: bool}, "missing_slots": [str],
  "balance": {"classification": "cpu_bound|gpu_bound|balanced|unknown",
              "explanation": str, "basis": "multi_core_score_ratio|spec_proxy|insufficient",
              "uncertainty": "high|medium|low"},
  "workload_suitability": {profile_key: {score, confidence, limitations} for available profiles},
  "compatibility": <full M32-RULES-v2 report dict, verbatim from check_build_compatibility>,
  "compatibility_summary": {"aggregate_state": ..., "incompatible_rules": [ids], "unknown_rules": [ids],
                            "overall": "COMPATIBLE|INCOMPATIBLE|UNKNOWN|NOT_EVALUATED"},
  "power": {"mode": "measured|reference|unknown", "reference_w": int|None,
            "basis": "M2.5 PSU_TDP_REFERENCE_FRACTION policy", "limitations": [...]},
  "upgrades": [{"target_slot": "cpu|gpu", "direction": "upgrade",
                "rationale": [str], "evidence": str, "candidate_hint": str|None}],
  "budget_alternatives": [],  # empty + limitation string when no price data (this dataset)
  "build_intelligence_version": "M4-BUILD-v1.0", "deterministic": true
}
```
- Balance: with benchmark evidence on both sides → ratio-based classification (bands pinned in tests: ratio within [0.66, 1.5] → balanced, outside → bound toward the stronger side, uncertainty from coverage); one side benchmarked, other spec-only → classification allowed but uncertainty=high + limitation; neither → "unknown" (never a fake percentage).
- NO universal bottleneck percentage is ever emitted (test asserts no key contains "bottleneck_percent" and no float labeled as such).
- Upgrade suggestions: for the weaker side, pick top-3 catalog candidates by scenario score for that slot that (a) pass the evidence gate, (b) are compatible with the build's motherboard per M32-RULES-v2 where evaluable (UNKNOWN → suggested with explicit unknown-compat caveat); rationale cites the score delta and evidence basis.
- Power: reuse the M2.5 TDP-reference policy verbatim (`PSU_TDP_REFERENCE_FRACTION`); label as reference, never "measured"; missing TDPs → unknown + limitation.
- Compatibility: NEVER claim COMPATIBLE when components are missing — `overall` maps: any INCOMPATIBLE→INCOMPATIBLE; else any UNKNOWN among applicable rules→UNKNOWN; else all applicable COMPATIBLE AND all six slots present→COMPATIBLE; else UNKNOWN/NOT_EVALUATED with missing_slots listed. Test pins partial-build behavior.

- [ ] Step 1: Failing tests: balanced/bound classification bands; spec-only uncertainty=high; unknown when no evidence; no bottleneck percent key; compatibility passthrough + partial-build never COMPATIBLE; power reference labeling; upgrade suggestions respect evidence gate + socket rule; budget_alternatives empty with reason; determinism.
- [ ] Step 2: FAIL → Step 3: Implement → Step 4: PASS + compatibility regression suites green.
- [ ] Step 5: Additive route `POST /build/intelligence` in main.py. Commit `feat(m4): T5 build intelligence (balance, workload fit, upgrades, M32-RULES-v2 passthrough)`.

### Task 6 (Mission T6): Bounded optimization engine — `build_optimizer.py`

**Files:** Create `backend/app/services/build_optimizer.py`; Test `backend/app/test_build_optimizer.py`.

**Interfaces (Consumes: T4 recommend + T5 analyze + compatibility; Produces):**
```
OBJECTIVES = ("workload_performance", "budget", "efficiency", "upgradeability", "compatibility", "evidence_confidence")
optimize_build(session_factory, objective: str, constraints: RecommendationConstraints,
               max_iterations: int = 500) -> dict:
{
  "objective": str, "objective_supported": bool,  # budget→False in this dataset (no prices)
  "builds": [{ "components": {slot: {hardware_id, name}}, "completeness": "complete|partial",
               "missing_slots": [...], "compatibility_state": "COMPATIBLE|UNKNOWN|INCOMPATIBLE",
               "objective_score": float|None, "score_explanation": [...],
               "trade_offs": [str], "evidence_confidence": 0..1, "workload_scores": {...}}...max 5],
  "search": {"strategy": "bounded_greedy_slot_scan", "candidate_pool_sizes": {...},
             "iterations_used": int, "max_iterations": 500, "truncated": bool},
  "gaps": [{"slot|evidence", "reason"}...],  # named missing components/evidence
  "optimizer_version": "M4-OPT-v1.0", "deterministic": true
}
```
- Strategy: per-slot top-K (K=4) pre-ranked by scenario score (T4) → greedy slot-ordered assembly (cpu→motherboard→ram→gpu→storage→psu) with incremental compatibility filtering (drop candidates whose rules vs already-picked parts are INCOMPATIBLE; UNKNOWN passes with caveat recorded) → objective scoring of the assembled build → deterministic tie-break (score desc, evidence desc, component id tuple asc). Iteration counter hard-bounds work; exceeding → truncated=true + note (test pins bounded behavior with a synthetic large pool using max_iterations=25).
- Objective scoring: workload_performance = profile-weighted scenario score of cpu+gpu (None→unknown); efficiency = normalized efficiency feature (None when missing); compatibility = share of applicable rules COMPATIBLE (UNKNOWN-heavy builds score low, never fake); upgradeability = categorical from upgrade pathways documented in T5 (documented-only); budget → objective_supported=False, builds still returned ranked by workload_performance with limitation (no price fabrication).
- Alternatives: exactly the distinct trade-off builds (best overall, best per secondary objective when different, one evidence-conservative pick).
- Incomplete catalog: when a slot has zero evidence-passing candidates → that slot stays empty, completeness=partial, gap named; NEVER a fabricated placeholder.

- [ ] Step 1: Failing tests: bounded iterations (truncated flag, iterations_used <= max); deterministic order incl. tie-break; compatibility-aware pruning (incompatible candidate dropped, unknown kept + caveat); partial build when pool empty (gap named, completeness=partial); budget objective unsupported + no price fabrication; objectives vocabulary enforcement; max 5 builds.
- [ ] Step 2: FAIL → Step 3: Implement → Step 4: PASS.
- [ ] Step 5: Additive route `POST /build/optimize` + `GET /build/optimize/objectives`. Commit `feat(m4): T6 bounded deterministic build optimizer with partial-build honesty`.

### Task 7 (Mission T7+T8): API integration + frontend experience + AI digest

**Files:** Modify `frontend/src/App.jsx` (minimal additive mounts), `frontend/src/spectra.css`/`experience.css` (new tokens/classes only); Create `frontend/src/intelligence.js`, `frontend/src/intelligence.test.js`, `frontend/src/components/ScenarioRatings.jsx`, `frontend/src/components/BuildIntelligencePanel.jsx`, `frontend/src/hooks/useScenarioRatings.js`, `frontend/src/recommendationWorkspace.js`, `frontend/src/recommendationWorkspace.test.js`; Modify `backend/app/services/build_chat_service.py` (digest injection), Test `backend/app/test_build_chat_digest.py`.

**Backend AI digest (T8):** extend `build_prompt_payload` to include `"intelligence": {"scenario_scores": <per selected component>, "build_intelligence": <analyze_build summary>, "recommendations": <top3>}` when components are selected (omitted when empty — prompt rules already handle absent context). Extend SYSTEM_PROMPT with rules 43-45: intelligence digests are authoritative SPECTRA facts; never override compatibility states or confidence; when digest is absent, do not claim scenario scores exist. Deterministic fallback: when provider unavailable (existing ProviderUnavailableError → 503 path), extend the existing deterministic response to carry `intelligence_summary` built purely from engine outputs (test pins both paths). The deterministic engine remains source of truth; no fabrication.

- [ ] Step 1: Failing tests (backend): digest appears with components; absent when none; prompt contains rule 43-45 text; deterministic fallback includes intelligence_summary; no provider call attempted when unconfigured.
- [ ] Step 2: Implement backend digest → PASS.
- [ ] Step 3: Frontend failing tests (`node --test`): `intelligence.js` — scenario score → star-string + confidence badge class mapping; UNKNOWN rendering; missing-data indicator mapping; `recommendationWorkspace.js` — constraint form state → query serialization (v2 endpoint), alternatives/exclusions display shaping; ScenarioRatings expandable a11y contract (button + aria-expanded, keyboard reachable).
- [ ] Step 4: Implement `intelligence.js`, hooks, components: ScenarioRatings on CPU/GPU detail sections (below existing SuitabilityCard usage — reuse `.suitability-card` tokens + new `.scenario-*` classes); workload selector chip row (reuse existing chip patterns); Recommendation workspace section in explore view using v2 endpoint; BuildIntelligencePanel extension on build view consuming `/build/intelligence` + `/build/optimize`; confidence/missing-data badges from existing `BUILD_SIGNAL_*` vocab.
- [ ] Step 5: Preserve Neural Luxury identity — only additive classes using existing CSS custom properties (var(--...)); no shared infra files. Run `npm run lint` → no NEW warnings; `npm run build` OK.
- [ ] Step 6: Backend + frontend full suites green; commit `feat(m4): T7+T8 intelligence API integration, frontend panels, AI digest + deterministic fallback`.

### Task 8 (Mission T9): Validation & evaluation

**Files:** Create `backend/app/test_m4_evaluation.py`, `backend/tests/evaluation_fixtures.py`, `docs/m4/M4_EVALUATION_REPORT.md` (data), `data/research/m4/evaluation_results.json` (emitted).

- [ ] Step 1: Fixtures: synthetic catalog rows covering every mission edge: missing benchmarks, missing prices, conflicting specs (duplicate benchmarks w/ different scores), incompatible pairs, partial builds, budget constraints, extreme outliers (score 10x p90), workload-specific ranking inversions (a CPU ranked above b at workstation but below at daily).
- [ ] Step 2: Evaluation tests: determinism (two runs byte-identical ranking); confidence calibration (spec-only never high); score monotonicity (primary feature ↑ → score ↑, no-recency); recommendation stability (adding an unrelated low-evidence CPU does not reorder top-5); compatibility regressions (existing suites still green); API integration smoke (v2 endpoints via TestClient: 200 shapes, 404s, 422s); value scenario UNKNOWN everywhere; misleading-recommendation guard: assert no candidate is recommended for a profile whose evidence_requirements it fails.
- [ ] Step 3: Emit `data/research/m4/evaluation_results.json` via a small runner (deterministic counters only).
- [ ] Step 4: Full CI-parity suite + frontend suite + build. Commit `test(m4): T9 evaluation suite + fixtures + emitted results`.

### Task 9 (Mission T10): Delivery docs + draft PR

**Files:** Create in `docs/m4/`: `M4_INTELLIGENCE_ARCHITECTURE.md`, `M4_SCORING_METHODOLOGY.md`, `M4_WORKLOAD_PROFILES.md`, `M4_RECOMMENDATION_ENGINE.md`, `M4_EVALUATION_REPORT.md`, `M4_RESIDUAL_RISKS.md`, `M4_RELEASE_READINESS.md`. Each includes: exact formulas/weights, anchors + reference population, confidence semantics, test evidence (exact counts/commands), limitations, versions.

- [ ] Step 1: Write docs from implemented code (no invented values; formulas copied from the modules).
- [ ] Step 2: `M4_RELEASE_READINESS.md` ends with verdict: READY_FOR_MERGE_REVIEW / CONDITIONAL_REVIEW / PARTIAL_DELIVERY / BLOCKED — chosen from actual evidence.
- [ ] Step 3: Commit docs; push branch; `gh pr create --draft` with body summarizing verdicts + evidence; do NOT merge.

## Proportionality note
Nine implementation tasks, each independently testable; T1→T2→T3 are strictly sequential (data → engine → profiles); T4/T5 depend on T1-T3; T6 on T4+T5; T7 integrates all; T8/T9 close. Frontend changes are additive panels into the existing single-view App.jsx; no route refactor (that would violate "no broad redesign").

