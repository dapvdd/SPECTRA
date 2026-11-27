# M4 Intelligence Architecture

**Milestone:** M4 — Explainable intelligence layer
**Branch:** `feat/m4-intelligence` (base `5c2c7d9` = origin/main)
**Date:** 2026-11-26
**Status:** Implemented, CI-parity green (see `M4_RELEASE_READINESS.md`)

---

## 1. Purpose

M4 adds an explainable decision-support layer on top of the existing SPECTRA
engines. It answers three user questions with explicit evidence:

1. *How good is this component for my scenario?* → scenario scoring
   (`M4-SCORING-v2.0`, four scenarios, star ratings + confidence).
2. *What should I pick for my workload?* → workload profiles +
   intelligent recommendations (`M4-REC-v2.0`) and bounded build optimization
   (`M4-OPT-v1.0`).
3. *What does this build look like as a system?* → build intelligence
   (`M4-BUILD-v1.0`: balance, power reference, compatibility summary,
   workload suitability, upgrade hints).

The layer **extends, never replaces**, the proven engines:

| Existing engine | Version | Role in M4 |
|---|---|---|
| `suitability_service.py` | v1 (M3.1) | anchor arithmetic (`_score_to_stars`), spec-cap policy reused |
| `recommendation_service.py` | v1 (M3.x) | v1 functions byte-identical; M4 adds an additive v2 layer |
| `compatibility_service.py` / `compatibility_rules.py` | M32-RULES-v2 | delegated verbatim; M4 only maps its report to a summary |
| frontend `buildIntelligence.js` | M2.5 | signal list untouched; M4 panel is additive |

## 2. Module map

```
backend/app/services/
  intelligence_features.py      M4-FEATURES-v1     feature layer (pure)
  scenario_scoring.py           M4-SCORING-v2.0    scenario engine (pure)
  workload_profiles.py          M4-PROFILES-v1.0   8 profiles + preferences
  recommendation_service.py     M4-REC-v2.0        additive v2 ranking layer
  build_intelligence_service.py M4-BUILD-v1.0      build composition
  build_optimizer.py            M4-OPT-v1.0        bounded single-swap engine
  build_chat_service.py         (M1 + M4 Task 8)   AI digest (rules 43-45)

backend/app/schemas/intelligence.py                wire models (all additive)
backend/app/main.py             new routes (additive):
  GET  /hardware/recommend/v2
  POST /hardware/recommend/v2
  GET  /hardware/{id}/scenarios
  POST /build/intelligence
  POST /build/optimize

backend/tests/evaluation_fixtures.py               evaluation catalog
backend/app/test_m4_evaluation.py                  evaluation suite (21 tests)
backend/app/scripts/m4_emit_evaluation.py          deterministic results emitter

frontend/src/
  intelligenceDisplay.js         profile registry mirror (pure, node --test)
  recommendationV2.js            v2 payload formatting (pure, node --test)
  hooks/useScenarioRatings.js    per-hardware scenario loader
  hooks/useBuildIntelligence.js  build intelligence loader
  components/ScenarioRatings.jsx detail-view scenario panel
  components/BuildIntelligencePanel.jsx build-view panel
  App.jsx                        additive mounts only (no redesign)
```

## 3. Data flow

```
Hardware row (ORM)
      │  features_from_hardware()
      ▼
M4 feature vector ──► scenario_scoring.score_scenarios()
      │                        │
      │ anchors (derived        │
      │ percentiles of the      │
      │ live benchmark          │
      │ population)             │
      ▼                        ▼
workload_profiles ────► recommendation_service.recommend_intelligent()
                                 │
                                 ▼
                    ranked candidates + exclusion ledger + constraints echo
                                 │
buildOptimizer ──► single-swap suggestions (bounded, evidence-gated)
                                 │
build_intelligence_service ──► balance / power / workload / compat summary
                                 │
build_chat_service ──► AI digest (authoritative engine facts, rules 43-45)
                                 │
                                 ▼
                    frontend panels (ScenarioRatings, BuildIntelligencePanel)
```

## 4. Design invariants (enforced by tests)

1. **UNKNOWN is first-class.** A scenario without its evidence family returns
   `score=None, confidence="unknown"` plus a limitation naming the gap. It is
   never rendered as 0 stars and never estimated.
2. **Derived anchors, not invented.** `derive_anchors()` computes p10/p25/p50/
   p75/p90 from the observed population with linear interpolation
   (rank `k = (n-1)*p/100`, floor/ceil interpolation). Empty population →
   `None`; single element → all anchors equal.
3. **Evidence gates everywhere.** No benchmark of the scenario's family →
   spec-based path capped at 3.0 with medium confidence. No evidence at all →
   exclusion from recommendations (`insufficient_data:no_evidence`) or UNKNOWN
   scenarios.
4. **VALUE is price-gated.** This dataset carries no price columns, so VALUE
   is always UNKNOWN; `score_scenarios(evidence={"price_usd": ...})` is the
   only path to a value score.
5. **Determinism.** Identical inputs produce byte-identical outputs
   (ranking tie-break by hardware id ascending).
6. **Compatibility stays engine-owned.** `compatibility_summary.overall` is a
   mapping of `evaluate_rules` output; the only added rule is that a partial
   build (required slots missing) downgrades COMPATIBLE to UNKNOWN.
7. **No recency bias.** release_date/architecture are not scoring features
   (asserted in `test_m4_evaluation.py`).
8. **Additive frontend.** New panels mount beside existing sections; no
   shared infra file changes; no route refactor.

## 5. Versions

| Component | Version |
|---|---|
| Feature layer | `M4-FEATURES-v1` |
| Scenario scoring | `M4-SCORING-v2.0` |
| Workload profiles | `M4-PROFILES-v1.0` |
| Recommendations | `M4-REC-v2.0` |
| Build intelligence | `M4-BUILD-v1.0` |
| Optimizer | `M4-OPT-v1.0` |
| Compatibility (unchanged) | `M32-RULES-v2` |

## 6. What M4 deliberately does not do

- No price data (no columns in schema) → no value scores, no budget filtering.
- No GPU benchmark rows → GPU scenario scores are spec-based and capped.
- No game FPS, no thermals, no measured power, no availability data.
- No multi-swap simulation; the optimizer is single-swap per suggestion.
- No production DB writes, no deployment, no merge without owner review.
