# M4 Evaluation Report

**Version:** `M4-EVAL-v1.0`
**Branch:** `feat/m4-intelligence`
**Date:** 2026-11-26
**Evidence file:** `data/research/m4/evaluation_results.json` (committed, emitted deterministically)

---

## 1. What was evaluated

Eight evaluation properties, each enforced by tests in
`backend/app/test_m4_evaluation.py` (21 tests) against synthetic fixtures in
`backend/tests/evaluation_fixtures.py`:

| # | Property | Test |
|---|---|---|
| 1 | Recommendation determinism (two runs byte-identical) | `test_recommendation_determinism_byte_identical` |
| 2 | Optimizer determinism (two runs byte-identical) | `test_optimizer_determinism_byte_identical` |
| 3 | Scenario scoring determinism | `test_scenario_scoring_deterministic` |
| 4 | Confidence calibration (spec-only never `high`) | `test_spec_only_confidence_never_high` |
| 5 | Outlier robustness (10× p90 caps at 5.0, never negative) | `test_outlier_caps_at_five_never_negative` |
| 6 | Conflicting benchmark records take max, deterministically | `test_conflicting_benchmarks_take_max_deterministically` |
| 7 | Score monotonic in primary feature; no recency feature | `test_score_monotonic_in_primary_feature`, `test_no_recency_feature_anywhere` |
| 8 | Recommendation stability (unrelated low-evidence row does not reorder top-5) | `test_unrelated_low_evidence_row_does_not_reorder_top5` |
| 9 | VALUE scenario UNKNOWN everywhere | `test_value_scenario_unknown_everywhere` |
| 10 | Misleading-recommendation guard (no candidate recommended for a profile whose `evidence_requirements` it fails) | `test_no_candidate_recommended_when_evidence_requirements_fail` |
| 11 | AI/ML profile never scores GPU compute | `test_ai_ml_profile_never_scores_gpu_compute` |
| 12 | Compatibility engine stays authoritative (M32-RULES-v2 passthrough) | `test_compatibility_engine_still_authoritative`, `test_socket_incompatible_pair_detected` |
| 13 | API integration smokes (200 shapes, 404s) across all four M4 routes | `test_api_v2_recommend_smoke` … `test_api_scenarios_404` (7 tests) |

## 2. Fixtures (synthetic catalog)

18 CPU rows · 2 GPU rows · 1 motherboard row, deliberately including:

- 1 evidence-free row (coverage 0, no benchmarks) → must gate-exclude;
- 1 outlier row (score 10× p90) → must cap at 5.0;
- 1 conflicting-benchmark row (duplicate records, different scores) → max per family;
- 1 incompatible socket pair (CPU 910 + motherboard 920);
- a workload-inversion pair (930 vs 931: 930 wins gaming 4.74 > 2.85,
  931 wins daily 4.84 > 1.99 — inversion follows from profile weights).

## 3. Exact commands and results

```
# M4 subset (8 files)
.\backend\.venv\Scripts\python -m pytest backend/app/test_intelligence_features.py `
  backend/app/test_scenario_scoring.py backend/app/test_workload_profiles.py `
  backend/app/test_recommendation_intelligent.py backend/app/test_build_intelligence_service.py `
  backend/app/test_build_optimizer.py backend/app/test_build_chat_digest.py `
  backend/app/test_m4_evaluation.py -q
→ 119 passed, 1 warning in 8.08s

# Full CI-parity suite
.\backend\.venv\Scripts\python -m pytest backend -q `
  --ignore=backend/app/test_benchmark_matching.py `
  --ignore=backend/app/importers/test_benchmark_cpu_import.py `
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle `
  --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking
→ 1663 passed, 2 skipped, 2 deselected, 3 warnings in 78.14s

# Frontend
npm test      → ✔ pass 704, fail 0
npm run build → ✓ built (no errors)
npm run lint  → pre-existing warnings only; no NEW warnings from M4 files

# Emitted results
.\backend\.venv\Scripts\python backend\app\scripts\m4_emit_evaluation.py
→ wrote data/research/m4/evaluation_results.json
```

Per-file M4 test counts: `intelligence_features` 15 · `scenario_scoring` 19 ·
`workload_profiles` 15 · `recommendation_intelligent` 14 ·
`build_intelligence_service` 18 · `build_optimizer` 12 ·
`build_chat_digest` 5 · `m4_evaluation` 21 = **119**.

## 4. Emitted results (read from `evaluation_results.json`, not invented)

**Versions:** features `M4-FEATURES-v1` · scoring `M4-SCORING-v2.0` ·
profiles `M4-PROFILES-v1.0` · recommendation `M4-REC-v2.0` ·
build intelligence `M4-BUILD-v1.0` · optimizer `M4-OPT-v1.0` ·
compatibility `M32-RULES-v2`.

**Determinism:** `recommendation_deterministic: true`,
`optimizer_deterministic: true` (byte-identical repeat runs in-process).

**VALUE UNKNOWN everywhere:** `value_unknown_everywhere: true` — every
sampled row returns `score: null, confidence: "unknown"` for the value
scenario (no price columns exist in this dataset).

**Spec-based capping (observed):**

| Row | Type | Path | gaming | workstation | daily |
|---|---|---|---|---|---|
| 300 | GPU | spec-based | 2.23 | 2.30 | 2.30 |
| 301 | GPU | spec-based | 1.54 | 1.47 | 1.47 |
| 900 | CPU | measured (outlier) | 5.00 | 4.98 | 5.00 |
| 901 | CPU | measured gaming, spec daily | 3.83 | 3.58 | 1.46 |
| 930 | CPU | measured | 4.74 | 4.65 | 1.99 |
| 931 | CPU | measured | 2.85 | 2.71 | 4.84 |

Spec-based scores stay ≤ 3.0 (hard cap); the outlier row saturates at 5.0
without going negative; all sampled confidences are `medium` (fixture
coverage < 0.6) — never `high` for spec-only rows.

**Ranking:** top-8 ids `[112, 900, 111, 931, 110, 910, 109, 108]`,
`excluded_count: 1` (the evidence-free row, reason code
`insufficient_data:no_evidence`).

**Optimizer:** 4 swaps suggested for the fixture build
(cpu 101 + gpu 301, profile `software_development`) — all evidence-gated,
bounded at 3 per slot.

**Compatibility passthrough:** pair (cpu 910, motherboard 920) →
`engine_state: "INCOMPATIBLE"`, `incompatible_rules: ["cpu-motherboard-socket"]`
— produced by the M32-RULES-v2 engine verbatim, mapped not re-judged.

## 5. What this evaluation does not cover

- Fixtures are synthetic; no sweep over the 518-CPU production-like snapshot
  was performed as part of this suite (the snapshot is a read-only fixture at
  `data/dev/m4_snapshot.db`).
- No load/performance testing of the new endpoints.
- Frontend display modules are tested as pure functions (`node --test`,
  14 new tests); the rendered app is covered by the browser acceptance pass
  below, not by DOM unit tests.
- The AI digest's LLM path is prompt-rule-tested and fallback-tested; no
  provider was called during evaluation.

## 6. Browser acceptance (real backend, real UI)

Playwright (headless chromium) drove the production build path
(`vite dev` + `uvicorn`) against a throwaway copy of the M3.3 snapshot
(`data/dev/m4_snapshot.db` → temp file; the snapshot and CI DBs untouched).
Script: `backend/app/scripts/m4_browser_acceptance.py`. Result: **13/13 PASS**:

```
PASS  app_renders                     PASS  build_intelligence_panel_visible
PASS  nav_present                     PASS  build_intelligence_version_shown
PASS  explore_cards                   PASS  panel_card_balance
PASS  scenario_panel_visible          PASS  panel_card_power
PASS  gaming_stars_positive           PASS  panel_card_compatibility
PASS  value_unknown_rendered          PASS  panel_names_missing_slots_or_unknown
PASS  no_unexpected_console_errors
```

Verified in the live UI: scenario ratings render with positive gaming stars
for a benchmarked CPU, VALUE renders its unknown/price gap, and the build
intelligence panel shows `M4-BUILD-v1.0` with balance/power/compatibility
cards and visible gap naming.

**Defect found and fixed by this pass** (integration-level, invisible to the
service/API suites): `useBuildIntelligence` POSTed
`{"components": {…full hardware objects…}}` while
`BuildIntelligenceRequest` requires top-level slot ids with
`extra="forbid"` → every panel request 422'd. Fixed by extracting
`buildIntelligenceRequestBody` into the pure module (normalizes objects →
ids, drops null slots, no wrapper), pinned by 3 contract tests
(`intelligenceDisplay.test.js`), commit `50516eb`.

## 9. Risks (browser acceptance)

- The acceptance pass runs one happy-path build (CPU added from a detail
  view). GPU-first flows, motherboard/PSU slots, and the optimizer UI are
  exercised at service/API level only (see §5).
- One integration defect was found and fixed by this pass (§6); it
  demonstrates the value of the pass and the residual risk of UI paths that
  only the browser exercises.

## 10. Verdict

All 21 evaluation tests pass; the emitted JSON confirms determinism,
evidence gating, UNKNOWN-first-class semantics, spec-cap enforcement, and
compatibility passthrough. No property regressed against v1 suites
(1663 backend + 707 frontend green). Detailed limitations are tracked in
`M4_RESIDUAL_RISKS.md`.
