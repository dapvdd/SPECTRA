# SPECTRA Batch 016 — End-to-End Validation & UI Verification

Validation batch. No feature expansion. One reproducible defect was found,
fixed, and covered by a regression test.

---

## 1. Repository baseline

| Item | Value |
|---|---|
| Workspace | `C:\SPECTRA` (git repo) |
| Branch | `main` |
| Starting commit | `8eb9ee1` `feat(data): expose source provenance and attribution` |
| Recent commits | `8eb9ee1` (015), `819018b` (014), `fc424b5` (013), `d900b99`, `4178659`, `f403b43` |
| Working tree | Only the intended untracked artefacts (`.opencode/`, `data/backups/*`, prior `data/spectra.db.bak-*` backups) |
| DB path | `C:\SPECTRA\data\spectra.db` |
| DB SHA-256 (before) | `9aee08794eeaf0ddabcaaed3b0462e8116aa5f1a339414dd12244e1ecd7b0160` |

`git status --short` showed no *modified* tracked files at the start — Batch 015
left a clean tree on top of `8eb9ee1`.

## 2. Runtime capabilities discovered

| Capability | Status |
|---|---|
| Docker CLI | **Not available** (`docker` is not on PATH) |
| Playwright / Puppeteer / jsdom / vitest | **Not installed** (no dependency added) |
| Browser | **Chrome 155.0.8059.40 and Edge installed** |
| Browser automation | Chrome DevTools Protocol over the built-in `WebSocket` in Node 24 — no new toolchain |
| Python | `C:\Program Files\Python313\python.exe` — uvicorn 0.53.0, fastapi 0.141.1, sqlalchemy 2.0.52; pytest present |
| Node | v24.15.0, `node --test`, oxlint, vite 8.2.2 |
| AI provider | **Live** — real Gemini responses returned for `/comparison/explanation`, `/hardware/chat`, `/build/chat` |

Because a real browser was available, **all visual results in this report come
from actual Chrome renders and screenshots**, not from inference over a
successful build.

## 3. API smoke tests — 43/43 PASS

Run against a **live uvicorn instance** on `http://127.0.0.1:8000` backed by a
**disposable copy** of the database (`C:\...\opencode\spectra_b016.db`), so
nothing here could touch the production dataset. Script:
`api_smoke_test.py`, results `_api_smoke_result.json`.

Hardware catalog, detail, benchmarks, source transparency, and build/chat
workflows were all exercised. Notable results:

- `GET /hardware` → 5380 rows; CPU 3501, GPU 1879; type filters return exactly
  the requested type; unknown type → `[]`.
- Detail schema verified field-by-field for CPU (7 keys) and GPU (8 keys).
- Benchmarks correctly **distinguish Geekbench 7 single-core from multi-core**;
  filters for `test_type`, `source_id`, and `benchmark_name` all behave.
- `GET /hardware/999999/benchmarks` and `/provenance` → 404.
- GPUs with no benchmark data return `[]` — **no fabricated gaming benchmark data**.
- `GET /sources` → 9 sources, every `license_status` in the expected vocabulary.
- Licence metadata confirmed end-to-end: Wikipedia `CC BY-SA 4.0` (`clear`),
  GPU Ark `CC BY 4.0` (`clear`), PassMark (`restricted`).
- Provenance: multiple records per field rendered correctly (hardware 3350
  `architecture` → 2 records), and empty provenance reported honestly as
  `unattributed`/`unavailable` rather than fabricated attribution (9 of 9
  fields unattributed for hardware 15, a CPU with specs and no provenance).
- Build conversation create → fetch → append message → append turn → reset all
  pass; missing conversation → 404.

## 4. Browser verification — 42/42 PASS

`browser_verify.mjs` drives the real installed Chrome over CDP against the
running Vite dev server. Results `_browser_result.json`, screenshots in
`screenshots/`.

**Viewports** (390 / 768 / 1440 px) — all rendered with
`documentElement.scrollWidth <= innerWidth`, i.e. no horizontal overflow:

| Viewport | Screenshot |
|---|---|
| Mobile 390 | `mobile-390-landing.png` |
| Tablet 768 | `tablet-768-landing.png` |
| Desktop 1440 | `desktop-1440-landing.png` |

**Also verified in the real browser:**

- Catalog count is real: 5,380 records, `Showing 12 of 5380 hardware records`.
- Search, type filter, manufacturer filter, and load-more pagination (12 → 24).
- CPU detail renders with 7 spec rows; source disclosure expands and shows a
  real record ("Wikipedia (English) — Wikimedia Foundation / Wikipedia
  contributors — Verified source").
- Benchmark source footnote present with 10 licence tags.
- Comparison tray with 2 items, comparison table, and benchmark evidence kept
  **separate from spec evidence**.
- Dark / Light / System themes all apply correct `data-theme` +
  `data-theme-preference`.
- Keyboard: first Tab focuses the "Skip to main content" link with a visible
  `outline-style: solid; outline-width: 3px`.
- Reduced motion honoured: `transition-duration`/`animation-duration` both
  collapse to `1e-05s` under `prefers-reduced-motion: reduce`.
- **Zero console errors, zero page exceptions, zero failed network requests.**
- Out-of-scope question to hardware chat ("What is the weather in Paris
  tomorrow?") was answered, not crashed.

**Long names:** the longest catalog name (93 characters,
`Pentium 4 Processor Extreme Edition supporting HT Technology 3.46 GHz, 2M
Cache, 1066 MHz FSB`) was searched, opened, and rendered at 390 px with **no
horizontal overflow** — see `mobile-long-name-detail.png` and
`mobile-source-disclosure-open.png`.

## 5. The defect found and fixed

### Symptom

Every AI-generated answer crashed the React tree. In the browser run this
surfaced as:

```
ReferenceError: parseMarkdown is not defined
  at MarkdownContent (src/App.jsx:2550)
```

and the whole page went blank — which is why the first browser run reported
8 downstream failures (build chat, keyboard focus, reduced motion, exception
check) that were all symptoms of the same root cause.

### Cause

`frontend/src/App.jsx` defines `MarkdownContent`, which calls `parseMarkdown`
in three places: the comparison AI explanation, the hardware chat answer, and
the build chat assistant messages. `parseMarkdown` lives in
`frontend/src/markdown.js`, but **`App.jsx` never imported it**. Git history
shows the helper was extracted into its own module in `d60f71c` and the import
was never restored, so this had been broken since that commit.

### Fix

One line — the missing import:

```diff
 import { useEffect, useRef, useState } from "react";
 import "./App.css";
+import { parseMarkdown } from "./markdown.js";
```

### Regression test

`frontend/src/markdownRendering.test.js` (3 tests). There is no DOM renderer in
this project's test setup, so the defect is covered the way the suite already
covers the JSX/CSS contract (`buildChat.test.js`, `buildChatEvidence.test.js`,
and others read `App.jsx` as text): assert the import wiring exists, assert
`parseMarkdown` is not redeclared locally, and assert the imported helper
actually works.

This test would have failed immediately before the fix.

## 6. Re-verified after the fix

A second full browser run was executed after the fix, **42/42 PASS with zero
console errors and zero page exceptions**. The first run's 41/42 → 42/42 gap was
also a harness bug on my side: CDP's `Runtime.evaluate` with `returnByValue`
cannot serialise a DOM element, so every `waitFor` condition written as
`document.querySelector(...)` always returned `undefined` and timed out. That is
a flaw in the verification script, not in the application.

## 7. Test, lint, and build results

| Check | Baseline | After |
|---|---|---|
| Backend `pytest backend -q` | 661 passed | **661 passed** |
| Frontend `node --test src/*.test.js` | 544 passed | **547 passed** (+3) |
| `oxlint` | 1 warning | **1 warning (pre-existing, line 3107, unrelated)** |
| `vite build` | success | **success** |

The single oxlint warning (`react/set-state-in-effect` at `App.jsx:3107`) is
pre-existing and unrelated to this batch; it was left alone.

## 8. Database safety

All tests ran against a disposable copy (`C:\...\opencode\spectra_b016.db`).
Before/after for the live database:

| Table | Before | After |
|---|---|---|
| hardware | 5380 | 5380 |
| cpu_specifications | 3501 | 3501 |
| gpu_specifications | 1879 | 1879 |
| benchmark_results | 1040 | 1040 |
| external_identifiers | 3575 | 3575 |
| field_provenance | 36946 | 36946 |
| sources | 9 | 9 |
| build_conversations | 5 | 5 |
| build_messages | 10 | 10 |

- `PRAGMA integrity_check` → `ok`
- `PRAGMA foreign_key_check` → 0 violations
- SHA-256 **before and after identical**:
  `9aee08794eeaf0ddabcaaed3b0462e8116aa5f1a339414dd12244e1ecd7b0160`

No migration was needed, no schema change was made, no records were created in
the production database, and no backup was committed.

## 9. Independent audit — 34/34 PASS

`audit_batch016.py` re-derives everything independently rather than trusting
this batch's own harnesses. It verifies the staged/untracked boundaries, that
the fix is a single additive import with no data/licence/provenance token in
the diff, live DB integrity, counts, and hash, that the regression test
actually guards the defect, that the browser and API runs are clean, that no
secrets leaked into artefacts, and that no `.env` is tracked.
Output: `_audit_result.json`.

## 10. Unverified areas and environmental blockers

- **Docker**: `docker` is not installed, so the containerised deployment
  (Nginx + uvicorn on ports 8080/8000) was **not** verified.
- **Production build preview**: the production bundle was built successfully and
  the dev server was verified in Chrome; the built `dist/` output served via
  `vite preview` was not separately exercised.
- **Ask SPECTRA conversational memory across a reload**: build-chat persistence
  was verified at the API level (`/build/conversations/{id}/turn`), and the
  in-page restore was waited for, but a full reload-then-restore-visible-in-UI
  cycle was not separately screenshotted.
- **Edge**: only Chrome was driven; Edge is installed but not exercised.

## 11. Git

| Item | Value |
|---|---|
| Files changed | `frontend/src/App.jsx` (1 insertion) |
| New files | `frontend/src/markdownRendering.test.js`, `data/research/batch016/*` |
| Backups committed | None |
| `.opencode/` touched | No |
| Commit | The single commit on top of `8eb9ee1`; `git log --oneline -1`. The
HEAD recorded at audit time is stored in `_audit_result.json`. |
| Pushed | No |
| Independent audit | 34/34 PASS (`_audit_result.json`) |

Uncommitted working-tree noise after the commit is unchanged from the baseline:
`.opencode/opencode.json`, the historical `data/backups/*` files, the two
`data/spectra.db.bak-20261008*` backups, and
`data/research/batch001/09_independent_audit.md`. Nothing here was staged or
committed.
