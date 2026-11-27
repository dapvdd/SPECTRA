# M4 Release Readiness

**Version:** `M4-READINESS-v1.0`
**Branch:** `feat/m4-intelligence` (base `5c2c7d9` = origin/main)
**Date:** 2026-11-26

---

## 1. Scope of this release

Explainable hardware decision-support layer, additive to all existing engines:

| Deliverable | Status | Evidence |
|---|---|---|
| Feature layer (`M4-FEATURES-v1`) | Done | `test_intelligence_features.py` 15/15 |
| Scenario scoring (`M4-SCORING-v2.0`) | Done | `test_scenario_scoring.py` 19/19 |
| Workload profiles (`M4-PROFILES-v1.0`) | Done | `test_workload_profiles.py` 15/15 |
| Intelligent recommendations (`M4-REC-v2.0`, `/hardware/recommend/v2`) | Done | `test_recommendation_intelligent.py` 13/13 |
| Build intelligence (`M4-BUILD-v1.0`, `POST /build/intelligence`) | Done | `test_build_intelligence_service.py` 18/18 |
| Bounded optimizer (`M4-OPT-v1.0`, `POST /build/optimize`) | Done | `test_build_optimizer.py` 12/12 |
| AI digest rules 43–45 (`build.intelligence` payload) | Done | `test_build_chat_digest.py` 5/5 |
| Frontend panels (ScenarioRatings, BuildIntelligencePanel, hooks, display layer) | Done | 14 pure-module tests + build + lint + browser acceptance 13/13 |
| Evaluation suite + emitted results | Done | `test_m4_evaluation.py` 21/21; `data/research/m4/evaluation_results.json` |
| Seven delivery docs (`docs/m4/`) | Done | This document completes the set |
| Browser acceptance (real backend + snapshot data) | Done | 13/13 PASS; found+fixed 1 integration defect (`50516eb`) |

## 2. Test evidence (all commands run in this worktree)

```
Backend M4 subset (8 files):        118 passed
Backend full CI-parity:             1662 passed, 2 skipped, 2 deselected
Frontend node --test:               707 pass, 0 fail (693 baseline + 14 M4)
Frontend build (vite):              OK
Frontend lint (oxlint):             pre-existing warnings only; none new
Browser acceptance (Playwright):    13/13 PASS (see M4_EVALUATION_REPORT.md §6)
```

CI-parity command (exact, from worktree root):

```
.\backend\.venv\Scripts\python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle --deselect=backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking
```

## 3. Mission-constraint compliance

| Constraint | Status | Enforcement |
|---|---|---|
| No fabricated benchmarks/prices/FPS/specs | Met | Value UNKNOWN everywhere (evaluated); profiles' non-claims tested; docs copy code values |
| UNKNOWN first-class | Met | `score=None + confidence=unknown + limitation`; never rendered 0 stars (frontend `formatScenarioEntry` + eval tests) |
| Evidence gates | Met | Spec-only cap 3.0 (`_SPEC_BASED_MAX_SCORE`), never `high`; exclusion ledger `insufficient_data:no_evidence` |
| v1 engines byte-identical | Met | v1 `recommend`/`recommend_response` untouched (regression-tested); suitability anchors reused; compatibility M32-RULES-v2 verbatim |
| No production DB writes / deployment | Met | Dev DB untouched; snapshot copy used for acceptance is a temp throwaway |
| No force-push, no merge without owner | Enforced | Branch pushed once; draft PR only |
| No interference with M3.4 | Met | No M3.4 files touched |
| Frontend additive only | Met | New modules + additive mounts in App.jsx; no shared-infra redesign |
| Budget never filters | Met | Soft/unknown classification, echo notes (no price data) |

## 4. Known gaps that do not block

Tracked in `M4_RESIDUAL_RISKS.md` (R1–R12). The two user-visible ones:

- **R11:** the v2 recommendation workspace and optimizer have no UI consumer
  yet — API-complete, UI follow-up. The plan's Task 7 mentioned a
  recommendation workspace section; the delivered Task 7 scope covers the
  detail/build panels and both hooks + formatters for v2, but the workspace
  section itself is not mounted.
- **R1:** multi-core anchor drift (~24.7% at p90 vs v1 doc example) is
  documented, not silently re-anchored.

## 5. Review evidence

- Whole-branch fresh-context review (review package
  `.superpowers/sdd/2026-11-26-m4-intelligence/review-5c2c7d9..HEAD.diff`,
  13 commits): findings and dispositions recorded below (§7).
- Browser acceptance: `backend/app/scripts/m4_browser_acceptance.py`, 13/13.

## 6. Rollback

Single-branch additive change: reverting to `5c2c7d9` removes the layer with
no data migrations involved (no schema changes; `data/spectra.db` untouched;
no new tables/columns).

## 7. Final review dispositions

(Filled after the final review — see verdict.)

## 8. Verdict

(See end of document.)
