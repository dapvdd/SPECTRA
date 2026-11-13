# M2.5 Delivery Report — Unified Build Experience

Branch: `feat/spectra-m2.5-unified-build-experience` · Base: `abb2548` (origin/main) · HEAD: `8f86a1d` · 2026-11-13

## Verdict: **CONDITIONAL_REVIEW**

All 8 planned tasks are complete, committed, and green. Independent review
passes and the push are still pending (§7) — release recommendation withheld
until they complete. Production (`main`, production DB) and the M2 staging
deployment were never touched.

## 1. Scope executed (8/8 tasks)

| # | Task | Commit | Tests added |
|---|---|---|---|
| — | Phase A product audit + plan | `02418f9` | — |
| 1 | P0 PSU power semantics (two-tier TDP reference) | `f8bf90e` | +7 backend |
| 1b | Registry description wording ban follow-up | `8f86a1d` | +1 backend |
| 2 | Category-aware manufacturer filters + honest Compare gating | `3873b6d` | +2 backend, +4 frontend |
| 3 | Unified six-slot summary + workspace copy | `ad652d9` | +3 frontend |
| 4 | Honest, deduplicated Build Intelligence panels | `ce65b87` | +5 frontend |
| 5 | Verified six-component compatibility context for build chat | `672109f` | +12 backend, +11 frontend |
| 6 | Hardening: stale-closure restore, fetch hygiene, a11y | `aebc688` | +9 frontend |
| 7 | Reading-order hierarchy + density polish | `9489197` | +2 frontend |
| 8 | Delivery evidence + reports (this commit) | — | 43 DOM checks |

Docs: `docs/design/M2_5_PRODUCT_AUDIT.md`, `docs/design/M2_5_UX_DECISIONS.md`,
`docs/build-planner/M2_5_POWER_SEMANTICS.md`,
`docs/build-planner/M2_5_AI_CONTEXT_CONTRACT.md`,
`docs/build-planner/M2_5_TEST_MATRIX.md`, this report.

## 2. Verification evidence

- **Backend:** `1247 passed, 2 skipped, 2 deselected` (M2 baseline 1228 → +19).
  CI-parity command with the four documented ignores/deselects, re-run after
  the final code change.
- **Frontend:** `697 passed, 0 failed` (M2 baseline 664 → +33);
  `npm run build` ✓; `npm run lint` passes (pre-existing-style warnings only).
- **Browser evidence:** 15 PNGs + `dom-checks.json` (43/43) in
  `docs/design/evidence/m2-5/`, captured against a **disposable** local preview
  (backend :8010 on a fresh temp DB built by `Base.metadata.create_all` + 18
  `PREVIEW M25` fixtures; vite preview :4180). Production and staging were
  never contacted; both preview servers were stopped after capture.
- **Suggested merge review focus:** `compatibility_rules.py::rule_psu_build_wattage`
  (two-tier semantics), `schemas/build_chat.py` + `build_chat_service.py` rule 14
  (digest contract), `App.jsx` compatibility effect + digest wiring, and the
  `buildHardening.test.js` reading-order guards.

## 3. Honest-limitation disclosures

1. **PNG pixel review:** the reviewing model cannot read PNG pixels. Every
   visual claim is backed by **43 DOM assertions** executed in the live page
   during capture (slot counts, chip text per build state, rule-row
   composition, wording bans, reading-order offsets, overflow, resolved theme
   attribute). The capture script and `dom-checks.json` are committed. **A
   human should still eyeball the 15 PNGs before merge** — especially
   `15-build-planner-dark.png` (theme verified via
   `document.documentElement.dataset.theme === "dark"`, not by reading
   colors).
2. **Aggregate still never reads COMPATIBLE for full builds (by design):** the
   GPU-slot rule stays UNKNOWN (motherboards store a slot count, not a PCIe
   generation) and the PSU rule at/above the reference is now advisory-UNKNOWN
   (Task 1). Build A: 5 compatible + 2 UNKNOWN → aggregate UNKNOWN. This is the
   designed honest outcome, not a regression.
3. **Compatibility data is fixture-only:** preview DB fixtures are
   `PREVIEW M25`-prefixed and disposable; no real-world power, BIOS, XMP/QVL,
   M.2-keying, or connector claim is made anywhere — each rule's explanation
   states its boundary verbatim.
4. **No prices, benchmarks of unrecorded workloads, or measured power exist:**
   nothing was fabricated to fill gaps; gaps are named (Task 4 copy rules,
   prompt rules 37–40).

## 4. Contract compliance

- ✅ No merge to main; no deploy; no production DB migration or container
  restart; no prod/staging secret changes; no worktree deleted; no force-push.
- ✅ Existing M2 staging (`spectra-m2-staging` @ :8095) left running and
  unmodified for comparison.
- ✅ TDD: every added test was observed RED before the implementation change
  (per-task commits); full suites green at each commit.
- ✅ No fabricated data; PSU language invariant ("draw"/"covers" banned) is
  test-enforced down to registry metadata.
- ✅ Auth/ownership on `/build/chat` and `/build/conversations*` unchanged
  (`Depends(require_auth)` everywhere it was before).

## 5. Known limitations / follow-ups (non-blocking)

1. Chat token still keys on `cpuId:gpuId:use_case:resolution` only; a
   compatibility verdict change rides in with the next question's payload
   rather than resetting the conversation (documented decision,
   `M2_5_AI_CONTEXT_CONTRACT.md`).
2. Cooling and case remain out of scope; the platform gap copy says so.
3. PSU sizing still ignores RAM/storage draws (unrecorded in the schema).
4. The compatibility panel re-fetches on every slot change without debounce —
   deliberate: AbortController already makes rapid switching correct.
5. Local DBs lack the six-slot spec tables; browser evidence required a fresh
   disposable DB (script + fixture set documented in §2).

## 6. Task 8 evidence inventory

`docs/design/evidence/m2-5/`: `01-landing-light.png`,
`02-build-planner-six-slots-empty-light.png`,
`03-compatibility-empty-light.png`, `04-build-full-compatible-light.png`,
`05-compatibility-compatible-light.png`, `06-compatibility-incompatible-light.png`,
`07-compatibility-unknown-light.png`, `08-build-reading-order-light.png`
(full page), `09-detail-ram-light.png`, `10-detail-motherboard-light.png`,
`11-detail-storage-light.png`, `12-detail-psu-light.png`,
`13-build-mobile-390.png`, `14-build-mobile-390-full.png`,
`15-build-planner-dark.png`, `dom-checks.json` (43/43).

## 7. Outstanding before release recommendation

1. **Push the branch** and verify the remote SHA.
2. **Independent review passes** — backend correctness (power semantics,
   digest contract), frontend regression (App.jsx effects), security
   (auth/ownership unchanged, bounded digest), hardware-domain (PSU/TDP
   semantics), visual (human PNG pass).
3. Prod non-interference verification immediately before handoff (container
   IDs `fb2f3aa8bb46` / `8bb67a872fdd`; prod DB sha `7d1dca46…`; staging @
   :8095 untouched).
