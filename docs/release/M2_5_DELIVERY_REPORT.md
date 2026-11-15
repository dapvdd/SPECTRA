# M2.5 Delivery Report — Unified Build Experience

Branch: `feat/spectra-m2.5-unified-build-experience` · Base: `abb2548` (origin/main) · HEAD: `807bf2f` (pushed, remote SHA verified) · 2026-11-15
Review rounds (§7) covered the full code diff `abb2548..e622771`; the only
commit after the reviews is this documentation update.

## Verdict: **READY_FOR_MERGE_REVIEW**

All 8 planned tasks are complete, committed, pushed, and green. All five
independent review scopes returned READY_FOR_MERGE_REVIEW (§7); every
Critical/Important finding was verified against source and resolved or
corrected at the docs level (§7). Production (`main`, production DB) and the
M2 staging deployment were never touched.

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
| 8 | Delivery evidence + reports (this commit) | `7be9afd` | 43 DOM checks |
| 8b | Capture/seed scripts committed (evidence provenance) | `ae989de` | — |
| 8c | Power-semantics doc corrections (hardware review) | `7b8ed62` | — |
| 8d | Review minors: stale comment, constant doc, order pin | `e622771` | — |
| 8e | CI unblock: restore-rehearsal guard ordering (pre-existing main failure) | — | +1 regression assert |

Docs: `docs/design/M2_5_PRODUCT_AUDIT.md`, `docs/design/M2_5_UX_DECISIONS.md`,
`docs/build-planner/M2_5_POWER_SEMANTICS.md`,
`docs/build-planner/M2_5_AI_CONTEXT_CONTRACT.md`,
`docs/build-planner/M2_5_TEST_MATRIX.md`, this report.

## 2. Verification evidence

- **Backend:** `1247 passed, 2 skipped, 2 deselected` (M2 baseline 1228 → +19).
  CI-parity command with the four documented ignores/deselects, re-run at
  final HEAD (`e622771`).
- **Frontend:** `697 passed, 0 failed` (M2 baseline 664 → +33);
  `npm run build` ✓; `npm run lint` passes (pre-existing-style warnings only),
  re-run at final HEAD.

- **CI unblock (2026-11-15, commit `0099dbc` follow-up):** the branch's first
  CI run failed on `test_refuses_live_app_path`
  (`backend/app/scripts/test_restore_rehearsal.py`) — a **pre-existing main
  failure** (main @ `abb2548`, this PR's own base, ran red on 2026-11-12 with
  the identical `1 failed, 1227 passed`). Root cause:
  `restore_rehearsal()` ran `target.parent.mkdir()` **before** the live-path
  guard, so on the Linux runner `mkdir("/app/data")` raised
  `PermissionError` before the intended `ValueError`. It passed locally on
  Windows because the path resolves to a creatable `C:\app\data`. Fix: the
  guard (pure string inspection) now precedes every filesystem side effect,
  with a new deterministic regression assertion (`tmp_path/data` must not be
  created) that was observed RED before the fix on Windows too.
- **Browser evidence:** 15 PNGs + `dom-checks.json` (43/43) in
  `docs/design/evidence/m2-5/`, captured against a **disposable** local preview
  (backend :8010 on a fresh temp DB built by `Base.metadata.create_all` + 18
  `PREVIEW M25` fixtures; vite preview :4180). Production and staging were
  never contacted; both preview servers were stopped after capture. The
  evidence tooling is committed for reproducibility:
  `backend/app/scripts/capture_m2_5_preview.py` (capture + 43 DOM assertions,
  adapted from `capture_m2_preview.py`) and
  `backend/app/scripts/seed_m2_5_preview.py` (disposable fixture DB).
- **Suggested merge review focus:** `compatibility_rules.py::rule_psu_build_wattage`
  (two-tier semantics), `schemas/build_chat.py` + `build_chat_service.py` rule 14
  (digest contract), `App.jsx` compatibility effect + digest wiring, and the
  `buildHardening.test.js` reading-order guards.

## 3. Honest-limitation disclosures

1. **PNG pixel review:** the reviewing model cannot read PNG pixels. Every
   visual claim is backed by **43 DOM assertions** executed in the live page
   during capture (slot counts, chip text per build state, rule-row
   composition, wording bans, reading-order offsets, overflow, resolved theme
   attribute). The capture script and `dom-checks.json` are committed
   (`backend/app/scripts/capture_m2_5_preview.py`, `dom-checks.json`). **A
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
5. **Connector-gap naming (hardware-domain review):** the PSU rule lists
   populated PSU connector fields (`pcie_8pin_count`, `pcie_12vhpwr`) in
   `missing_information` on both branches, because the comparison they would
   feed is blocked by the unrecorded GPU connector needs — the fields are not
   absent, the *evaluation* is. The explanation states why
   (`compatibility_rules.py:361-364`); kept verbatim rather than special-cased.
6. **30% reference margin vs real transients (hardware-domain review):** real
   GPU transient spikes can approach ~2× listed TGP and turbo behavior exceeds
   labelled TDP, so the reference floor understates worst-case draw by design.
   The invariant that bounds this: the upper tier can never emit COMPATIBLE
   (UNKNOWN at best), so an undersized floor errs toward "unknown", never
   green. A measured-draw data model would be required to do better.
7. **Legacy client power-suggestion module (hardware-domain review):**
   `frontend/src/buildCompatibility.js` (`buildCompatibilityReport` /
   `buildPowerSuggestion`, 1.25× one-tier) is exported but referenced only by
   its own tests — it is dead code in the M2.5 planner, which renders server
   rule results exclusively. Not wired into the power path; removal is a
   trivial follow-up and deliberately out of M2.5 scope.

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

## 7. Independent review rounds (all completed 2026-11-14/15)

Five independent scopes reviewed the full branch code diff
(`abb2548..e622771`; commit `807bf2f` is documentation only). Every scope's
verdict: **READY_FOR_MERGE_REVIEW**.

**Security** — 0 Critical / 0 Important. One Minor accepted as designed: the
compatibility digest is a client-supplied pass-through (self-affecting only;
the invariant that keeps this Minor is that the digest never influences auth,
ownership, persistence, or conversation identity — if a future milestone
persists or scores it, it must become server-derived). Two Nits disclosed:
slot-key pattern not regex-restricted; no strip validators on
`rule_id`/`explanation` (bounded at 600 chars, consistency only).

**Backend correctness** — 0 Critical / 0 Important; 64 targeted tests pass.
Two Minor disclosed: the `+0.5` pre-floor term is inherited from the old
formula and makes the floor asymmetric (behavior intentional and pinned by
tests; doc example matches); a `tdp_w=0` edge case yields an all-UNKNOWN
power check rather than a floor violation (edge case, not a contract
breach). Two Nits fixed in `e622771`: stale `compatibility_service.py:220`
comment reworded; `COMPATIBILITY_STATES` documented as the canonical
vocabulary constant.

**Frontend regression** — 0 Critical / 0 Important; 697/0 + build OK.
One Minor disclosed: `buildHardening.test.js` source-string assertions pin
implementation names (acceptable tripwires, brittle beyond strict
necessity). Two Nits: reading-order pin hardened in `e622771`
(last-occurrence positions so a duplicate marker cannot silently weaken it);
manufacturer liveness on type change judges against the outgoing category's
facets (documented "still a live option" intent, not a regression).

**Hardware domain** — 0 Critical / 0 Important; 39 rule tests pass. The one
Important finding was a **doc defect, not a code defect**:
`M2_5_POWER_SEMANTICS.md` claimed the frontend "renders the same two-tier
meaning" while the live planner renders server rule results exclusively (the
1.25× one-tier client module is dead code, referenced only by its own
tests) — corrected in `7b8ed62`, plus the build B worked example now names
its own fixtures. Two Minor/Nit disclosed: populated PSU connector fields
are listed in `missing_information` because the *evaluation* is blocked by
unrecorded GPU connector needs (wording kept verbatim); the 30% margin can
understate real transients (~2× TGP) — bounded by the invariant that the
upper tier never emits COMPATIBLE (disclosure added to this report §5).

**Visual/UX structure** — 0 Critical / 0 Important. Verified statically and
via `dom-checks.json` (43/43): reading-order offsets strictly increasing,
dissolved wrappers fully deleted including their media-query overrides, no
orphaned selectors, token-only spacing, Intelligence 2px accent edge intact,
mobile 390px zero overflow, dark capture genuine
(`dataset.theme === "dark"`). One Nit disclosed: `.build-conversation`'s
section gap relies on margin-collapse through the wrapper (visually
equivalent, spacing ownership subtle). The Important provenance condition
(capture script not committed) was resolved in `ae989de` and withdrawn by
the reviewer.

**Remaining human step (disclosed):** the 15 PNGs remain un-reveted by any
automated pixel review (model limitation); a human eyeball pass is
recommended before merge — especially `15-build-planner-dark.png`.
