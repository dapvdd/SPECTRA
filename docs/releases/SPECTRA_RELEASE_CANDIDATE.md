# SPECTRA Release Candidate — `feature/spectra-delivery-20261028`

**Git SHA:** `92e808c67012bba242004d1ab3232e6586d828d4`
**Branch:** `feature/spectra-delivery-20261028` → `main`
**Date:** 2026-11-05
**Release Gate Status:** READY FOR MERGE REVIEW

---

## Release Summary

SPECTRA V2 delivery: GPU hardware fit engine, build conversation ownership,
quality star-rating provenance, and evidence-based recommendation system.
174 commits ahead of main. Both branches share orphan root `cc63a6b` with no
subsequent shared history — merge requires `--allow-unrelated-histories`.

> ⚠️ **Critical pre-deployment requirement:** the production database must be
> migrated before deploying this release. See **Deployment Procedure** below.

---

## Implemented Capabilities

| Capability | Files | Status |
|---|---|---|
| Evidence-threshold GPU/CPU ranking engine | `recommendation_service.py`, `suitability_service.py` | ✅ |
| Build conversation ownership (auth) | `auth.py`, `build_conversation_service.py`, `migrations/runner.py` | ✅ |
| Quality star-rating provenance tracking | `benchmark_quality_service.py`, `benchmark_quality.py` | ✅ |
| GPU identity normalization (safe resolution) | `gpu_identity.py`, `test_gpu_identity.py` | ✅ |
| Sentinel value defense (reject fabricated data) | `source_acquisition.py`, `normalization/primitives.py` | ✅ |
| Calibration anchor system (5-point geometric) | `calibration_verify.py`, `emit_calibration.py` | ✅ |
| Hardware segment classification (desktop/mobile/server) | `suitability_service.py` | ✅ |
| Data completeness intelligence | `completeness_intelligence.py` | ✅ |
| Versioned migration runner | `migrations/runner.py` | ✅ |
| Coverage verification | `coverage_verification.py` | ✅ |
| Workload evidence analysis | `workload_evidence.py` | ✅ |
| Enrichment pipeline (source-adapter framework) | `enrichment_pipeline.py` | ✅ |
| Full auth + IDOR security model | `auth.py`, `test_auth_security.py` | ✅ |
| Hardware Fit modal + recommendation hooks (frontend) | `HardwareFitModal.jsx`, `useSuitability.js`, `useRecommendation.js` | ✅ |
| Benchmark quality badge | `BenchmarkQualityBadge.jsx` | ✅ |
| Rate limiting middleware | `middleware/rate_limit.py` | ✅ |
| Request ID middleware | `middleware/request_id.py` | ✅ |

---

## Verified Test Results

### Backend — Full Suite
```
pytest backend/ -q
1017 passed, 2 skipped, 1 warning
Execution: python -m pytest backend/ --tb=no -q
```

### Frontend — Regression
```
npm run test
611 passed, 0 failed
Duration: ~600ms
```

### Frontend — Production Build
```
npm run build
✓ 50 modules transformed
dist/assets/index.css   92.97 kB (gzip: 15.31 kB)
dist/assets/index.js   341.03 kB (gzip: 97.99 kB)
Built in 276ms
```

### Frontend — Lint
```
npm run lint (oxlint)
3 warnings (pre-existing: setState-in-effect in hooks)
0 errors
EXIT: 0
```

### Backend — Migration Runner Regression
```
pytest backend/app/test_migration_runner.py
14 passed in 3.47s
EXIT: 0
```

### Backend — Auth + IDOR Security
```
pytest backend/app/test_auth_security.py
19 passed, 1 warning
EXIT: 0
```

### Backend — Data Scripts Regression
```
pytest backend/app/scripts/
111 passed in 0.67s (sentinel 60 + identity 25 + enrichment 15 + other 11)
EXIT: 0
```

### E2E Smoke Suite — 43 Cases
```
python data/research/batch016/api_smoke_test.py
TOTAL 43/43 passed
Base URL: http://127.0.0.1:8774
DB: spectra_e2e_migrated.db (schema v2, owner_id present)
```

### Backend — Lint (baseline characterization)
```
ruff check backend/app/
279 findings — ALL pre-existing, NOT introduced by stabilization commit
No errors (E/F-level) in stabilization-critical files
```
See `backend/app/migrations/runner.py` and `backend/app/services/build_conversation_service.py`
for verified clean lint on critical migration/auth files.

---

## Known Limitations

| Limitation | Severity | Note |
|---|---|---|
| **Calibration anchor drift** | Medium | 80.2 % of benchmark rows show ≥0.01-star shift. Multi-core ceiling anchor displaced −24.74 %. Mitigation: run `emit_calibration.py` to refresh anchors. Full report: `data/dev/PHASE3_CALIBRATION_SENSITIVITY_REPORT.md`. |
| **Gemini model deprecation** | Medium (external) | `models/gemini-2.0-flash` deprecated → `models/gemini-3.8-flash`. Chat endpoints return 502. Fix: update model name in `explanation_service.py`. Outside scope of this merge. |
| **Feature branch vs main: no shared history** | High (process) | Both branches descend from orphan root `cc63a6b` with no common commits after. Merge to main requires `--allow-unrelated-histories`. This is intentional (parallel development tracks). |
| **Build conversation backward compatibility** | Low | New `owner_id` field added to response. Existing clients consuming `id/cpu_hardware_id/gpu_hardware_id/created_at/updated_at` are unaffected. New clients can use `owner_id`. |
| **Hardware list backward compatibility** | Low | API now returns 7 fields per hardware item (was 4 in stale tests). All fields present in production DB `data/spectra.db` — this is a test expectation fix, not a schema change. |

### Honest Assessment: GPU Performance Ratings

Do not claim evidence-based GPU performance ratings where benchmark evidence is
unavailable. The calibration sensitivity analysis found:
- 80.2 % drift rate under current anchor system
- Multi-core max error: 24.74 %
- Single-core max error: 9.36 %

These are cosmetic (star-rating display) and do not affect build recommendation
correctness, but should be disclosed to users when star ratings are displayed.

---

## Database Migration Requirements

### What changed

| Version | Migration | DDL |
|---|---|---|
| 1 | baseline-current-schema | None (documents current state; no DDL) |
| 2 | auth-tables | `CREATE TABLE users (...)`, `ALTER TABLE build_conversations ADD COLUMN owner_id INTEGER`, `CREATE INDEX ix_build_conversations_owner_id` |

### Pre-deployment checklist

Before deploying this release to any environment with existing data:

- [ ] Backup `data/spectra.db` (or equivalent prod DB path)
- [ ] Compute SHA256 of backup and record it
- [ ] Copy the DB to a disposable rehearsal path: `cp data/spectra.db data/spectra_copy.db`
- [ ] Run the migration rehearsal (see below)
- [ ] Apply migration to the actual production DB
- [ ] Verify `schema_version.version = 2` and `build_conversations.owner_id` column exists
- [ ] Run smoke test against the migrated DB

### Deployment Procedure

```bash
# 1. Backup
cp data/spectra.db data/spectra_backup_$(date +%Y%m%d).db

# 2. Rehearsal (copy-first, never the original)
cp data/spectra.db data/spectra_rehearsal.db
python backend/app/migrations/runner.py --database data/spectra_rehearsal.db
# Expected: {"status": "upgraded", "from_version": 0, "to_version": 2, ...}

# 3. Verify rehearsal
python backend/app/migrations/runner.py --verify --database data/spectra_rehearsal.db
# Expected: {"status": "verified", "version": 2, "name": "auth-tables"}

# 4. Apply to production (only after step 3 passes)
python backend/app/migrations/runner.py --database data/spectra.db
# Expected: same upgrade output as rehearsal

# 5. Verify production
python backend/app/migrations/runner.py --verify --database data/spectra.db

# 6. Smoke test
# Start server with SPECTRA_DATABASE_URL=sqlite:///data/spectra.db
# Run: python data/research/batch016/api_smoke_test.py
# Expected: 43/43 passed
```

### Rollback and Recovery Plan

If the migration causes issues:

```bash
# Stop the service immediately

# Restore from backup
cp data/spectra_backup_YYYYMMDD.db data/spectra.db

# Verify restored state
python backend/app/migrations/runner.py --report --database data/spectra.db
# Expected: {"current_version": 0, "pending_count": 2, "pending": [...v1...v2]}
```

The migration runner's v2 downgrade is reversible (documented in `--target 1`):
```bash
python backend/app/migrations/runner.py --target 1 --database data/spectra.db
# Reverts: DROP INDEX ix_build_conversations_owner_id,
#          ALTER TABLE build_conversations DROP COLUMN owner_id,
#          DROP TABLE users
```

---

## Merge Risk Analysis

### P0 — Critical (release blockers)

| Risk | Description | Mitigation |
|---|---|---|
| **Prod DB at schema v0** | `data/spectra.db` has no `schema_version` table, no `owner_id` column. Deploying the app (which now requires `owner_id`) against the unmigrated DB will cause HTTP 500 on all build conversation endpoints. | Run migration before deploying. Not resolved by the merge — requires ops action. |

### P1 — High

| Risk | Description | Mitigation |
|---|---|---|
| **Unrelated git histories** | Feature branch and main share only orphan root `cc63a6b`. `git merge-base` returns empty. Standard merge will fail; requires `--allow-unrelated-histories`. | Use `git merge --allow-unrelated-histories origin/main` or `git merge origin/main` after confirming unrelated is intentional. |
| **No shared test baseline** | CI on main uses `pytest backend -q` (1019 tests not present on main). Cannot re-run full gate on main to confirm merge is safe. | Review test additions in the diff. All new tests have been run against the feature branch. |

### P2 — Moderate

| Risk | Description | Mitigation |
|---|---|---|
| **API contract expansion** | Hardware list now returns 7 fields (was 4), GPU detail now returns 9 spec keys (was 8), benchmark rows now include `quality` field. Existing API consumers may break if they parse all keys. | All added fields are nullable (`release_date`, `segment`, `architecture` can be null). `memory_bus_width_bits` is nullable. Clients that iterate all keys may see new null fields. Document in API changelog. |
| **Calibration anchor drift** | 80.2% drift in star ratings. Not a build correctness defect, but visible in UI if star ratings are shown. | Document to users. Plan anchor refresh. |
| **Gemini model deprecation** | `gemini-2.0-flash` deprecated by Google AI API. Chat endpoints return 502. | Update `explanation_service.py` to use `gemini-3.8-flash`. Outside this merge scope. |

### P3 — Low

| Risk | Description | Mitigation |
|---|---|---|
| **schema_version table: `name` vs `applied_at`** | The v2 migration registers `name="auth-tables"` but the table stores `applied_at`. The runner reads `version` and `applied_at` correctly. This is an internal implementation detail. | None required — runner works correctly. |
| **Research artifacts in diff** | 35 untracked files (investigation scripts, research outputs) are not committed. No risk to production. | Confirm they are not staged before PR. |
| **bcrypt 5.0.0 dependency** | New Python package. Verify it is available in deployment environment. | Standard pip install from PyPI. |

---

## Pre-Merge Review Checklist

- [ ] Confirm `--allow-unrelated-histories` merge strategy is intentional
- [ ] Verify reviewer has read the deployment procedure
- [ ] Confirm backup of prod DB has been taken before any deployment
- [ ] Verify migration rehearsal was run on a copy and passed
- [ ] Confirm `data/spectra.db` will be migrated before the app is deployed
- [ ] Note calibration drift limitation for anyone displaying star ratings
- [ ] Track the Gemini model deprecation update as a separate follow-up PR
- [ ] Frontend `npm run build` passes (verified in this gate)
- [ ] All 43 smoke tests pass on migrated DB (verified in this gate)
- [ ] Auth + IDOR regression passes (19/19, verified in this gate)

---

## Release Recommendation

**CONDITIONAL**: Merge is safe with caveats.

The code changes are well-tested (1017 backend, 611 frontend, 43 smoke, 33 auth/migration). The only release blocker is the requirement to run the DB migration before deploying. This merge itself does not modify production data — it only adds migration code that must be explicitly executed.

**Required before deployment:**
1. Run the migration on the production DB (copy-first procedure documented above)
2. Verify `schema_version.version = 2` post-migration
3. Run smoke test against the migrated DB

**Recommended follow-up:**
1. Refresh calibration anchors (`emit_calibration.py`) to reduce the 80.2% drift rate
2. Update Gemini model name from `gemini-2.0-flash` to `gemini-3.8-flash`
3. Add CI gate: fail if any calibration anchor displacement exceeds 15%
