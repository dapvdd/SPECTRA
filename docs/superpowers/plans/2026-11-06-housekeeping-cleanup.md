# SPECTRA Housekeeping: legacy removal, normalizer dedup, docs, coverage, quality-doc

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Remove dead legacy code, eliminate parallel normalizer definition, make roadmap docs truthful, add high-value missing tests, and document the quality score's real scope.

**Architecture:** Five independent tasks ordered to avoid merge conflicts:
1. Delete `sprint18b/` dead code (0 external imports, self-contained legacy).
2. Dedup `cpu_normalizer.normalize_name` onto shared `normalization.primitives`.
3. Update roadmap/audit docs to reflect actual implementation state.
4. Add targeted tests for uncovered paths found by a fresh coverage run.
5. Document the benchmark-quality score's lack of sample/variance signal.

Tasks 1-2 are code, 3+5 are docs, 4 needs a verification run first. Each task commits independently on `main`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, pytest, pytest-cov (to add, dev-only). Node 20+Vite frontend untouched.

**Spec:** Backlog agreed from `docs/SPECTRA_V2_ROADMAP.md` + evidence-grounded audit (subagent `ses_e50114d8effeqNP0O5glYSprHF`). The roadmap lists 1.x/2.x as open but code shows them done; 3.x GPU-benchmark/price are intentionally license-blocked (not legal work). The 5 items below can all be legally done now.

## Global Constraints

- Commit/push to `main` directly (project convention; CI auto-run on push).
- Use `git commit -F file.txt` for messages (PowerShell mangles inline `${{ }}` and nested quotes).
- Never weaken tests; full `pytest backend -q` must keep passing after each task.
- Never modify prod DB `data/spectra.db`; tests use in-memory/scratch SQLite only.
- Only new dependency: `pytest-cov` (dev-only, NOT added to runtime `requirements.txt`).
- Docs edits are documentation-only; no fabricated statuses; every claim must be code-verifiable.
- Do NOT delete tracked `investigate_C_sensitivity.py` / `investigate_P3_revalidation.py` (V2 artifacts).

## Review Focus

- **Full suite regresses after a task** -> every code task ends with a `pytest backend -q` gate matching the current passcount (1015 passed, 2 skipped, 2 deselected, minus sprint18b tests after Task 1).
- **Removing sprint18b/ silently breaks an importer/script that imports it** -> Task 1 Step 1 greps the whole repo; CI integrity also re-verifies.
- **cpu_normalizer behavior changes because the shared primitive lacks the CPU replace-chain** -> Task 2 keeps behavior byte-identical by layering the replace-chain on top of the shared function, pinned by 2 new edge-case tests.
- **Roadmap updated to claim a feature is "done" that actually isn't** -> Task 3 only marks statuses verified by file:line proof in the audit (1.1, 1.3, 1.4, 2.x); 1.2 marked "partial (no sample/variance)"; 1.5 "partial"; 3.x kept open.
- **Coverage work targets hot paths nobody reaches** -> Task 4 picks gaps by (uncovered line x user-facing route) after the report, choosing real endpoints, not helpers.
- **Quality-doc overstates the score** -> Task 5 documents exactly: weights = attribution 0.35 / timestamp 0.25 / licence 0.20 / provenance 0.20, veto rules, and that sample-count/variance are deliberately absent (no schema change), pointing at the migration-plan note.

---

### Task 1: Remove dead legacy `sprint18b/` package

**Files:**
- Delete: `backend/app/sprint18b/` (8 tracked files incl. empty `__init__.py`)

**Interfaces:**
- Consumes: nothing.
- Produces: folder removed; repo-wide grep for `sprint18b` returns zero hits outside git history.

- [ ] **Step 1: Confirm zero external references**

Run: `git grep -n "sprint18b" -- backend tests`
Expected: only self-references inside `backend/app/sprint18b/` or empty.

- [ ] **Step 2: Run the 3 sprint18b test files to record their count (removed WITH the package)**

Run: `python -m pytest backend/app/sprint18b -q`
Expected: PASS (54 tests = 13 classifier + 9 evidence + 32 normalizer).

- [ ] **Step 3: Delete the package**

Run: `Remove-Item backend/app/sprint18b -Recurse -Force`

- [ ] **Step 4: Full suite still green (minus removed tests)**

Run: `python -m pytest backend -q --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py --deselect="backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_database_persistence_across_restart_cycle" --deselect="backend/app/test_deployment_config.py::PersistentStorageCycleTests::test_entrypoint_initialization_prevents_empty_volume_masking"`
Expected: (1015 - 54) passed, 2 skipped, 2 deselected.

- [ ] **Step 5: Commit & push**

`git add -A` then `git commit -F <msgfile>` with message `chore: remove dead sprint18b legacy package (0 external refs)`; `git push`. Verify CI green.

### Task 2: Dedup cpu_normalizer.normalize_name onto shared primitives

**Files:**
- Modify: `backend/app/importers/cpu_normalizer.py` (`normalize_name`, lines 8-24)
- Modify: `backend/app/normalization/test_primitives.py` (add 2 tests)

**Interfaces:**
- Consumes: `backend.app.normalization.primitives.normalize_name` (line 28) and `strip_invisible_characters` (line 19) - both already exist and are tested.
- Produces: `cpu_normalizer.normalize_name(value: str|None) -> str|None` keeps its exact public signature and behavior; internally calls the shared primitive after applying the CPU replace-chain. Consumers: cpu_normalizer internal rows (lines 116, 127, 138, 157), `data/research/batch010/identifier_source_audit.py`.

- [ ] **Step 1: Write 2 edge-case tests (baseline-pinning)**

Add to `backend/app/normalization/test_primitives.py`:

```python
def test_shared_normalize_does_not_invent_cpu_ark_strip():
    from backend.app.normalization.primitives import normalize_name as base
    # The shared primitive must stay generic: no ®/™/Â® strip.
    assert base("  Intel\u00c2\u00ae Core i7-9700K  ") == "Intel\u00c2\u00ae Core i7-9700K"

def test_cpu_normalizer_layers_ark_mojibake_strip_on_shared():
    from backend.app.importers.cpu_normalizer import normalize_name as cpu
    # The CPU importer keeps its historical mojibake-® strip.
    assert cpu("Intel\u00c2\u00ae Core i7-9700K") == "Core i7-9700K"
    assert cpu("AMD\u00c2\u00ae Ryzen 5 5600") == "Ryzen 5 5600"
```

NOTE: the exact mojibake characters live in `cpu_normalizer.py` lines 13-18 (`IntelÂ®`, `AMDÂ®`, `Â®`, `â„¢`, `™`, `®`). The implementer must copy them verbatim from the file, not from this plan (terminal rendering may differ).

- [ ] **Step 2: Run to confirm current code already passes (pins behavior)**

Run: `python -m pytest backend/app/normalization/test_primitives.py -q`
Expected: PASS (current cpu_normalizer already strips; tests pin it).

- [ ] **Step 3: Refactor `cpu_normalizer.normalize_name` (import + body)**

Add at top of `cpu_normalizer.py` (if not present): `from backend.app.normalization import primitives` (use the same import style the file already uses for facades).
Replace function body with a version that runs the EXACT original replace-chain (copied verbatim from current lines 12-19) then returns `primitives.normalize_name(value)` (which collapses whitespace + strips invisible chars):

```python
def normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    # CPU importer layer: strip encoding-mojibake Ark brand tokens before the
    # shared whitespace/invisible-char collapse. Layered so the generic
    # primitive stays behavior-identical for benchmark/gpu paths.
    value = (
        value.replace("IntelÂ®", "Intel")
        .replace("AMDÂ®", "AMD")
        .replace("Â®", "")
        .replace("â„¢", "")
        .replace("™", "")
        .replace("®", "")
    )
    return primitives.normalize_name(value)
```

CRITICAL: copy the exact character bytes from the current file — do not retype from this plan if the terminal has mangled them.

- [ ] **Step 4: Run normalization + importer test suites**

Run: `python -m pytest backend/app/normalization backend/app/importers/test_gpu_normalizer.py backend/app/importers/test_benchmark_importer.py backend/app/importers/test_data_quality_rules.py -q`
Expected: ALL PASS (behavior byte-identical).

- [ ] **Step 5: Full suite green**

Run the full backend command from Task 1 Step 4.
Expected: same passcount as Task 1.

- [ ] **Step 6: Commit & push**

`git add backend/app/importers/cpu_normalizer.py backend/app/normalization/test_primitives.py`; `git commit -F <msgfile>` (`refactor: dedup cpu normalizer onto shared primitives`); push; verify CI green.

### Task 3: Update roadmap & audit docs to actual state

**Files:**
- Modify: `docs/SPECTRA_V2_ROADMAP.md`
- Modify: `docs/SPECTRA_V2_AUDIT.md` and/or `docs/SPECTRA_SYSTEM_AUDIT.md` (only if they carry the same status table)

**Interfaces:**
- Consumes: audit findings (subagent `ses_e50114d8effeqNP0O5glYSprHF`) with verified file:line.
- Produces: truthful, code-verifiable statuses.

- [ ] **Step 1: Read the roadmap + audit status sections fully**

Read `docs/SPECTRA_V2_ROADMAP.md`; read status/verdict sections of `docs/SPECTRA_V2_AUDIT.md` and `docs/SPECTRA_SYSTEM_AUDIT.md`.

- [ ] **Step 2: Mark verified-done items with the proof line**

Edit roadmap adding `**DONE (verified)**` + file:line proof for: 1.1 (`backend/app/services/comparison_service.py`, `POST /comparison/gpu`, `test_gpu_comparison_api.py`, `frontend/src/comparisonGpu.js` -> App.jsx GPU-to-backend), 1.3 (`main.py` `get_hardware` q/limit/offset + `/hardware/facets`), 1.4 (`main.py` `/ready` DB+migrations, `middleware/request_id.py` mounted, structured JSON logs; note `/metrics` optional-unimplemented), 2.2/2.3 (if not already marked done).
Edit 1.2 to: `1.2 Benchmark quality: PARTIAL - implemented weights attribution 0.35 / timestamp 0.25 / licence 0.20 / provenance 0.20; no sample-count/variance (see Task 5)`.
Edit 1.5 to: `1.5 Normalizer: PARTIAL - primitives promoted; cpu_normalizer still has a CPU-specific layer (see Task 2)`.

- [ ] **Step 3: Keep 3.x honestly open**

Leave `3.1 GPU benchmark integration` and `3.4 Price/perf-to-price` marked `OPEN - license-blocked` with note "no licensed source yet".

- [ ] **Step 4: Verify doc-only change**

Run: `git status -s` -> only the doc file(s) modified, no code.

- [ ] **Step 5: Commit & push**

`git add` the edited docs only; `git commit -F <msgfile>` (`docs: update roadmap/audit statuses to verified state`); push.

### Task 4: Add targeted tests for uncovered user-facing paths

**Files:**
- Add: `pytest-cov` (dev tooling)
- Create: one new test file `backend/app/test_<gap>_coverage.py` (name reflects the gap found)
- Possibly modify existing test file

**Interfaces:**
- Consumes: coverage run output (`pytest-cov`).
- Produces: coverage report + 2-3 new tests targeting the highest-value real gaps.

- [ ] **Step 1: Install dev cov tooling**

Run: `pip install pytest-cov` (do NOT add to `requirements.txt`).

- [ ] **Step 2: Run coverage on the core app modules**

Run: `python -m pytest backend -q --cov=backend.app.main --cov=backend.app.services --cov-report=term-missing --cov-report=html --ignore=backend/app/test_benchmark_matching.py --ignore=backend/app/importers/test_benchmark_cpu_import.py <existing deselects>`
Expected: per-function missing lines; save HTML to `htmlcov/`.

- [ ] **Step 3: Select the highest-value gaps (2-3)**

From `term-missing`, choose the most user-facing functions/endpoints that are reachable routes or service branches and currently uncovered. Document the selection in the commit message. Candidates the audit flagged: error/404/edge branches in `main.py` route handlers, `recommendation_service`/`comparison_service` guard branches. Do NOT target `/comparison/cpu` (roadmap says backend CPU comparison is out of scope; frontend remains client-side).

- [ ] **Step 4: Write the new tests asserting the uncovered branches**

For each chosen gap write a focused test using TestClient on in-memory SQLite (as existing API tests do). Assert exact branch behavior (status code, body, or raised error).

- [ ] **Step 5: Run the new test file**

Run: `python -m pytest backend/app/test_<gap>_coverage.py -q`
Expected: PASS.

- [ ] **Step 6: Full suite green + re-run coverage to confirm chosen lines now covered**

Run the full backend command (expected same passcount as Task 2), then re-run the coverage command and confirm the chosen lines show covered.

- [ ] **Step 7: Commit & push**

`git add backend/app/test_<gap>_coverage.py`; `git commit -F <msgfile>`; push; verify CI green.

### Task 5: Document benchmark-quality score scope

**Files:**
- Modify: `docs/SCORING_METHODOLOGY.md` (quality-score section)
- Possibly modify: `docs/COVERAGE_VERIFIED.md` if it mentions the quality score

**Interfaces:**
- Consumes: the quality-scoring function (audit: `backend/app/services/` quality scorer, weights 0.35/0.25/0.20/0.20, veto excluded/unmatched -> None) - read it to confirm before writing.
- Produces: accurate documentation only.

- [ ] **Step 1: Confirm the score formula + veto from code**

Read the quality-scoring function; record exact weights and veto rule. Find the migration-plan note that says "no schema change" scoped out sample/variance.

- [ ] **Step 2: Add a "Known scope" paragraph to SCORING_METHODOLOGY.md**

State precisely: score uses existing data only (provenance attribution quality, record timestamp, source licence clarity, provenance completeness); deliberately excludes sample-count and variance because those need new DB columns (documented in migration plan - no schema change adopted); excluded/unmatched never scored; formula deterministic. Note the roadmap 1.2 keeps the honest "partial" status.

- [ ] **Step 3: Verify docs-only change**

Run: `git status -s` -> only doc modified.

- [ ] **Step 4: Commit & push**

`git add docs/SCORING_METHODOLOGY.md`; `git commit -F <msgfile>` (`docs: document benchmark quality score scope (no sample/variance)`); push.

---

## Execution Handoff

Plan complete. Recommend **subagent-driven** because Task 2's behavior-pinning tests and Task 4's gap selection both benefit from a fresh reviewer's eyes, and Tasks 1/2/4 touch the test suite whose CG is the whole `pytest backend -q` run. But **native** works too since the tasks are largely independent and each commits separately.

Which execution approach would you prefer - subagent-driven or native?

---

## Completion (2026-11-06)

**Status: PLAN COMPLETE — all 5 tasks delivered, reviewed, and merged to `main`.**

Execution: subagent-driven (user choice), with controller rulings to run Tasks 3-5 inline after
repeated subagent context-confusion (see ledger `.superpowers/sdd/housekeeping-cleanup/progress.md`).

| # | Commit | Task |
|---|---|---|
| 1 | `c08e8b5` | Delete dead `sprint18b/` (8 files, 1437 lines, 54 tests, 0 external refs) |
| 2 | `5594ab8` | Dedup `cpu_normalizer.normalize_name` onto shared `primitives.normalize_name` (chain byte-identical) |
| 3 | `46c303e` | Roadmap statuses truthful (1.1/1.3/1.4 DONE verified, 1.2/1.5 PARTIAL, 3.1/3.4 OPEN) |
| 4 | `d291c7a` | 8 coverage tests closing 3 user-facing gaps (recommendation empty-branch, single-cat 404, star bounds) |
| 5 | `b4fb5b6` | SCORING_METHODOLOGY.md Section 7: benchmark quality scope (no sample/variance) |

Final gate: **971 passed, 2 skipped, 2 deselected, 0 failed** (verified on final tree).
CI green on every commit. Final whole-branch review: **Ready to finish**. Work committed
directly to `main` per plan + user authorization. Prod DB untouched; no test weakened;
`pytest-cov` added dev-only.
