# SPECTRA M2.5 — STAGING UI DISCREPANCY INVESTIGATION (INCIDENT UI-2511)

**Date:** 2026-11-15 · **Investigator:** release/QA agent · **Target:** `http://100.113.157.0:8096/` · **Expected release:** `dcfd7df`

## VERDICT: CONFIRMED_DEPLOYMENT_DEFECT

The category-tab discrepancy reported by the human reviewer is real, reproducible, and
**not a browser-cache issue**: the human was shown **production `:8080`** (or a tab bound
to it), which is a pre-M2.5 build that only offers CPU and GPU. The M2.5 staging
environment on `:8096` is deployed correctly and renders **all six** category tabs
in a fresh, cache-disabled browser.

---

## 1. Root cause

**Cross-origin confusion caused by port-number similarity, not a software defect.**

- The reviewer's browser session that exhibited "only CPU and GPU" matches the exact,
  deterministic rendering of **production `:8080`**, whose static bundle
  (`/assets/index-DG6KnBNx.js`, md5 `8d1efe7f…`) contains **zero** occurrences of the
  RAM/STORAGE/MOTHERBOARD/PSU category strings and renders exactly
  `All hardware / CPU 3501 / GPU 1879` type-filter buttons (fresh-context screenshot
  `evidence/ui25-PROD-8080.png`).
- The M2.5 staging origin `:8096` serves bundle `/assets/index-B5U1PO0u.js`
  (md5 `5f788cf0…`) which contains all six categories and renders
  `All hardware / CPU 3501 / GPU 1879 / RAM 3 / STORAGE 2 / MOTHERBOARD 2 / PSU 2`
  (fresh-context capture `evidence/ui25-M25-8096.png`, DOM JSON `evidence/ui25-out.json`).
- Staging was **redeployed/recreated at 16:27–16:36 WIB on 2026-11-15** (containers
  `Up`, StartedAt `10:27:30Z`), after the original acceptance run. If the human's
  visual review happened before that recreate against a **cached staging bundle** or
  the wrong port, the symptom matches what prod shows deterministically.
- Browser cache is explicitly **ruled out as the mechanism on 8096 today**: `index.html`
  is served `Cache-Control: no-cache`, hashed assets are `public, immutable`, no service
  worker is registered (`navigator.serviceWorker.controller === null`), and a brand-new
  Playwright context (empty storage) renders all six tabs.

## 2. Evidence summary

| Check | Result |
|---|---|
| Page URL / HTML | `:8096` serves 2712-byte index.html, `Last-Modified 09:35:40Z` (today), `Cache-Control: no-cache` |
| JS bundle (delivered) | `/assets/index-B5U1PO0u.js` (370,937 B), SHA-256 `238d95c1…` |
| CSS bundle (delivered) | `/assets/index-CKeX45bL.css` (123,718 B), SHA-256 `bd59e651…` |
| Container image | `spectra-frontend:m25-staging-dcfd7df`, ID `sha256:0ae625ae32fd…`, built 2026-11-15 16:35:50 WIB |
| In-container bundle md5 | `5f788cf0…` — byte-identical to what `:8096` delivers |
| Backend | `spectra-backend:m25-staging-dcfd7df` (healthy), `/api/release` → `git_sha dcfd7df3d…`, `version M2.5-staging` |
| `/api/ready` | `{"status":"ready","database":"reachable","migrations":"tracked-version-3"}` |
| DB catalog counts | CPU 3501 · GPU 1879 · RAM 3 · STORAGE 2 · MOTHERBOARD 2 · PSU 2 (total 5389) |
| `/api/hardware/facets` (8096) | Returns **all six** types with those counts |
| Fresh-browser DOM (8096) | All 6 type buttons + 6 build-slot cards + 6 "Browse X catalog" buttons; 0 console errors; 0 failed requests; all fetches 200 |
| Service worker | None registered (`sw_controlled: null`) |
| Asset cache headers | `index.html` → `no-cache`; `/assets/*` → `max-age=31536000, public, immutable` (correct cache-busting design) |
| Prod `:8080` fresh render | Only `All hardware / CPU / GPU` buttons; bundle contains no RAM/STORAGE/MOTHERBOARD/PSU strings |
| M2 staging `:8095` fresh render | All seven buttons (M2 build `abb2548` already has six categories) |
| Real-user log (8096) | 0 real-browser hits on 8096 in nginx logs — only HeadlessChrome + curl (all automated) |
| Real-user log (8080) | Windows Chrome/157 visited prod 10:59:12–11:00:37 UTC Nov 15; loaded bundle `index-DG6KnBNx.js` (the CPU/GPU-only UI); 160 requests |

**Interpretation:** the visual acceptance feedback describes prod's UI. Either (a) the
reviewer's tab was actually on `:8080`, or (b) it was on `:8096` before today's 16:27
recreate with a stale cached `index.html` (pre-recreate staging served an older M2.5
bundle whose hash differs; with `no-cache` on the HTML this is unlikely after reload,
but a PWA-style cached tab or an un-reloaded long-lived tab would persist the old UI
until a manual reload).

## 3. Acceptance-test gap (Phase 2)

The prior "24/24 DOM checks" verdict is **partially superseded**:

- The 24/24 pass came from `evidence/i25-part2.py`, which **did** target
  `http://100.113.157.0:8096` (confirmed by its `BASE` constant and output JSON).
- However, **none of the 24 assertions verify the category-tab strip** — the suite
  asserts build-planner slot cards (`.build-component-card` == 6), compatibility chips,
  rule rows, detail pages, reading order, mobile, and dark theme. It never asserts
  `.filter-buttons-type button` labels/counts.
- The screenshots captured for human review were full-page or build-section shots; the
  Explore/tab strip appears only incidentally.
- Part 1 (3/4, superseded) had a wrong selector for the compatibility chip but its
  "six slot cards" check was correct.
- Net: an environment that lacked the four new categories (e.g., prod, or a pre-fix
  staging build) would still score 24/24 because the suite never looks at the tab strip.

**Remediation of the gap (proposed, not yet applied):** add to the staging DOM suite:

```python
labels = page.locator(".filter-buttons-type button").all_inner_texts()
check("explore type tabs: all six categories",
      set(l.replace("\n","") for l in labels) ==
      {"All hardware","CPU3501","GPU1879","RAM3","STORAGE2","MOTHERBOARD2","PSU2"},
      str(labels))
```

plus a screenshot of the Explore section head (`#explore`).

## 4. Corrective action taken / proposed

**Taken (read-only, no mutation):** all evidence above; three fresh-context screenshots
saved under `evidence/` (`ui25-PROD-8080.png`, `ui25-M2-8095.png`, `ui25-M25-8096.png`).

**Proposed (requires authorization, none executed):**
1. No code fix is needed — frontend and backend at `dcfd7df` are correct; no fix branch.
2. Re-run visual review **on `http://100.113.157.0:8096/`** in a normal window after one
   hard reload (Ctrl+F5) — even though server headers make this unnecessary, it costs nothing.
3. Optional guardrails (staging-only, no redeploy required):
   - Add the missing tab-strip DOM assertion to the acceptance script (see §3).
   - Add a visible build/environment chip (e.g., `M2.5-staging · dcfd7df`) to the staging
     header so port confusion is immediately visible; requires a frontend change + rebuild
     + staging-only redeploy, so it needs explicit sign-off.

## 5. Production non-interference status

- `spectra-frontend`/`spectra-backend` (prod, `Up 5 days`) and
  `spectra-m2-staging-*` (`Up 3 days`): untouched, no restart, no image change.
- **Prod DB hash note:** the deployment-time baseline recorded prod DB
  `7d1dca46…`; a fresh read-only hash during this investigation reads
  `08334c91…`. Cause identified and **not** caused by this investigation:
  at `11:00:29 UTC` a real user (Windows Chrome/157, prod UI, referrer the prod origin)
  issued `POST /api/build/conversations`, which created build-conversation row id 7
  (`build_conversations` now has 7 rows; `hardware` remains 5380 rows, `users` 0).
  This is normal application usage of prod's build-chat feature, pre-dating this
  incident window; hardware catalog data is unchanged, and this investigation issued
  only GET requests to prod. M2 staging DB remains byte-identical at `1fa73add…`.

## 6. Artifacts

- `evidence/ui25-out.json` — full fresh-context DOM capture (8096)
- `evidence/ui25-compare.json` — three-origin comparison (assets, tabs, slot cards, SW)
- `evidence/ui25-PROD-8080.png` / `ui25-M2-8095.png` / `ui25-M25-8096.png` — screenshots
- `evidence/ui25-*.py` — read-only probe scripts (re-runnable)
- Local mirror: `C:\Users\user\AppData\Local\Temp\opencode\m25\` (same files)

*Investigation was strictly read-only against all three origins; no container, DB,
config, or deployment state was modified.*
