# SPECTRA V3 — Live Deployment Discrepancy Investigation

**Date:** 2026-11-10 (UTC)
**URL under investigation:** <http://100.113.157.0:8080/>
**Expected release:** `75eba50b1f09052f40409f6066a2ac030344d1a0`
**Mode:** read-only diagnostics; no rebuild, redeploy, migration, or database change
**Final verdict: V3_VISIBLE_AND_VERIFIED**

---

## 1. Result in one line

The exact production URL serves the approved V3 release and a fresh browser renders
it identically to the committed Phase G evidence. The reported absence is not
reproducible from DavidLab or from the Windows client. The only remaining
explanation for a user seeing something different is a stale client tab/cache
(most likely) or visiting the Tailscale HTTPS root, which serves DavidLab Control
Center rather than SPECTRA.

## 2. Port and container ownership

- Host port `100.113.157.0:8080` is owned by `spectra-frontend`
  (`fb2f3aa8bb46…`), image `sha256:6dec82c38484fc93e3d55f2a0e1fb3c4b2694b0558ae46c928124e0e5ff5e233`,
  tag `spectra-frontend:75eba50…`, label
  `org.opencontainers.image.revision=75eba50b1f09052f40409f6066a2ac030344d1a0`.
- The backend is `spectra-backend` (`8bb67a872fdd…`), image
  `sha256:8cb02c8b7e18d95df5af80ae3601d76dfcf403bb9df5764dc158a3a21c77bcd5`,
  running and healthy.
- The only listener on 8080 is the Docker proxy bound to `100.113.157.0:8080`.
  There is no second container, no system nginx (inactive), and no other process
  on that port.
- `localhost:8080` on DavidLab is **not** a valid route: the port is bound only
  to the Tailscale IP. Connection refused is expected, not a deployment fault.
- Nginx document root is `/usr/share/nginx/html`; the served config is the
  released config (SPA fallback, `/api/` proxy to `backend:8000`, hashed-asset
  caching, `index.html` no-cache).

## 3. HTTP evidence

| Source | Result |
|---|---|
| DavidLab → `http://100.113.157.0:8080/` | 200; index SHA256 `7b71b1396050828edadf4710184d18a040652d974a325a58188f7b0928473e01` |
| Windows client → `http://100.113.157.0:8080/` | 200; same SHA256 |
| Windows client → `http://david-lab:8080/` | 200; same SHA256 (`david-lab` resolves to `100.113.157.0`) |
| Cache-busted `/?cachebust=20261110` | 200; same SHA256 |
| DavidLab → `http://localhost:8080/` | connection refused (expected Tailscale-IP-only bind) |

Served index references:

- `/assets/index-DG6KnBNx.js` — SHA256 `b55cce21e86e65335159d8b822f35185636dbf2de5b8fba8214ea3dfd3d73d81`,
  355,880 bytes, `application/javascript`.
- `/assets/index-BNoD5QdN.css` — SHA256 `5ec97163b088d8c2c009c0171c028288bf42956c847753d01998e66d44186b96`,
  122,723 bytes.

Both hashes match the files inside the running container byte-for-byte. The
served JS contains the V3 markers `hero-stage`, `build-component-slot`,
`comparison-header-type`, `Know your hardware`, and `Beyond the specs`.

The pre-V3 asset `/assets/index-qdrmLzgf.js` returns **404**. The old frontend
container is gone; only the rollback image remains, unstarted.

## 4. Service worker / proxy / alternate route checks

- No service worker is registered; `navigator.serviceWorker.controller` is false.
- The served JS contains zero `serviceWorker` references; repository history has
  no PWA/workbox/service-worker implementation.
- Windows WinHTTP proxy: direct, no proxy. Browser proxy setting disabled.
- Tailscale Serve exposes three HTTPS routes, none of which is SPECTRA on 8080:
  - `https://david-lab.tail8abd21.ts.net/` → `127.0.0.1:49152` — **DavidLab Control Center** (`<title>DavidLab Control Center</title>`), not SPECTRA.
  - `:8443` → OpenCode (`127.0.0.1:4096`).
  - `:9443` → Nextcloud (`127.0.0.1:8081`).
- SPECTRA is reachable only at the explicit port-8080 URL.

## 5. Browser verification (fresh context)

Headless Chromium against the exact URL, 1440×900 and 390×844:

- Hero headline: **“Know your hardware. Beyond the specs.”**
- Hero hardware artwork: `.hero-stage` SVG present (`data-testid="hero-stage"`).
- Catalog: 12 cards rendered; facets `CPU 3501`, `GPU 1879`.
- GPU-first comparison: table rendered, headers `GPU`/`GPU`, 11 metric rows.
- Detail: `i752 Graphics`; Build produced a ready slot for the same GPU with
  specs (VRAM, clocks, bandwidth, TDP, architecture).
- Loaded assets: `/assets/index-DG6KnBNx.js` and `/assets/index-BNoD5QdN.css`.
- Console errors: **0**; page errors: **0**; failed requests: **0**.
- Themes and 390px layout were verified in the deployment acceptance run.

### Visual match to approved evidence

A production dark-theme screenshot at 1440px was compared with the committed
Phase G after-evidence `docs/design/evidence/phase-g/after/after--catalog-default--dark--desktop-1440.png`:

- Both images: `1440 × 4533`.
- Mean absolute pixel difference: **0.03 / 255**.
- Pixels differing by more than 10/255: **0.11%** (anti-aliasing/font rasterization).

This is a pixel-level match to the approved Phase G page, not merely a matching
image tag.

## 6. Root-cause classification

Server-side causes are excluded by direct evidence:

| Candidate | Result |
|---|---|
| B. Wrong container/port mapping | Excluded — only `spectra-frontend` owns 8080; correct image/tag |
| C. Stale frontend image | Excluded — running image is the V3 SHA-tagged image; served files match |
| D. Incorrect Nginx document root | Excluded — root and config are correct; assets resolve |
| E. Reverse proxy/service worker cache | Excluded on the server — no SW, no proxy, no other listener |
| F. Tailscale routing/access | Excluded for port 8080 — DavidLab and Windows receive identical V3 index; but the HTTPS root serves DCC, not SPECTRA |
| A. Browser cache / stale client tab | **Most likely for the exact 8080 URL** — not inspectable from the server; an old tab keeps pre-deploy JS in memory and cached old assets are immutable |
| G. Expectation vs actual V3 appearance | Possible secondary factor — the deployed page is the approved Phase G design |

**Conclusion:** the deployment is correct and V3 is visibly served. The user’s
observation is consistent with a stale client session (old tab or cached pre-V3
bundle) or with opening the Tailscale HTTPS root instead of port 8080.

## 7. Corrective action

No server-side correction was made or is warranted: the server is already
serving the approved release, and rebuilding/redeploying would not fix a client
cache. Minimum user-side correction:

1. Use the exact URL <http://100.113.157.0:8080/> (not the HTTPS Tailscale root).
2. Close the old SPECTRA tab and reopen it, or hard-reload with `Ctrl+Shift+R`.
3. If a stale page persists, clear site data for `100.113.157.0:8080`.

A cache-busted request (`/?cachebust=20261110`) was verified to return the same
V3 index, so a fresh navigation cannot receive an old server response.

## 8. Acceptance status

| Criterion | Status |
|---|---|
| Exact URL serves approved V3 assets | Pass — hashes match the V3 image |
| Browser renders V3 homepage | Pass — fresh Chromium render |
| Hero and hardware visuals match approved release | Pass — 0.03 mean pixel difference vs Phase G evidence |
| Catalog, Build, Comparison load without critical errors | Pass — 0 console/page/network errors |
| Direct host and Tailscale access consistent | Pass for port 8080 from DavidLab and Windows |

**V3_VISIBLE_AND_VERIFIED**

The only unresolved item is the user’s existing browser session, which cannot be
inspected remotely; the documented hard-reload/URL guidance is the remedy.
