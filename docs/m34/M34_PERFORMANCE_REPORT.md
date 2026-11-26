# M3.4 Performance Report (Task 6)

**Date**: 2026-11-26
**Branch**: `feat/m34-fortress`
**Method**: measured production evidence (read-only probes against the live M3.3 backend) → targeted fix → regression-pinned optimization. No scoring/recommendation logic touched (M4 boundary respected).

## 1. Baseline measurements (production, 2026-11-26, inside backend container)

| Probe | Size | Latency | Notes |
|---|---|---|---|
| `GET /hardware` unfiltered, plain | **1,022,879 B (0.98 MB)** | 0.350 s | the "≈1 MB response" |
| `GET /hardware` unfiltered, `Accept-Encoding: gzip` | **1,022,879 B** | 0.239 s | **backend applied NO compression** — identical bytes |
| `GET /hardware?limit=50` | 8,754 B | 0.009 s | pagination exists and is fast |
| `GET /hardware?verified=1` | 13,615 B | 0.011 s | verified subset is small |

nginx evidence (production logs, 24 h): **8 × `upstream response is buffered to a temporary file`** warns, all on `GET /api/hardware` — each unfiltered catalog load spills ~1 MB to disk in the frontend container.

## 2. Root causes

1. **No compression anywhere**: backend had no `GZipMiddleware`; frontend nginx had no `gzip` for proxied JSON. JSON catalog data compresses extremely well (repetitive field names/values → typically 85–95% reduction).
2. **Disk temp-file spill**: default `proxy_max_temp_file_size` (1 GB) + default buffers (8×4k=32k) force ~1 MB responses through `/var/cache/nginx/proxy_temp/` — disk write+read per unfiltered load, plus the log noise M3.3 documented.
3. **Not a query/serialization problem**: 0.35 s for 5444 rows is server-side acceptable; the cost is transfer size, not DB time (limit=50 → 9 ms for the same query shape).

## 3. Fixes implemented (additive, compatibility-preserving)

| Layer | Change | Effect |
|---|---|---|
| Backend (`main.py`) | `GZipMiddleware(minimum_size=1024)` before other middlewares | `/hardware` (1 MB) → gzip on the wire for any client sending `Accept-Encoding: gzip`; probes/small JSON unaffected; non-gzip clients byte-identical |
| Frontend nginx (`Dockerfile.frontend`) | `proxy_max_temp_file_size 0` + raised `proxy_buffers 16 16k` + `gzip on/gzip_types application/json` in `/api/` | temp-file spill eliminated (in-memory buffers hold compressed payloads); gzip as defense-in-depth |

## 4. Expected production effect (to be confirmed at next deployment)

| Metric | Before | Expected after |
|---|---|---|
| Wire size, unfiltered catalog | 1,022,879 B | **~100–150 KB** (gzip on JSON catalog data; exact ratio measured post-deploy) |
| nginx temp-file warns | 8/day | **0** (`proxy_max_temp_file_size 0`) |
| Frontend disk I/O per catalog load | ~1 MB write+read | 0 |
| Time-to-interactive for catalog | dominated by 1 MB transfer | dominated by ~120 KB transfer |

The backend already returns the full catalog in ~0.24–0.35 s; compression is CPU-cheap (single gzip pass) relative to transfer savings on the tailscale link.

## 5. API compatibility (regression-pinned)

`backend/app/test_m34_performance.py` (6 tests):

- gzip requested → `Content-Encoding: gzip`, raw ASGI body starts with gzip magic, decodes to 40 items.
- No `Accept-Encoding` → **no** `content-encoding` header (raw ASGI test); payload unchanged.
- Decoded compressed body == plain body (byte-equal); `X-Total-Count` preserved.
- Small responses (`/health`) not compressed (threshold 1024 B).

Full suite: **1591 passed / 2 skipped** — zero regressions, including the default-shape catalog tests (byte-compatible unfiltered behavior).

## 6. Deliberately NOT done

- **No pagination-by-default**: the unfiltered response remains byte-compatible (frontend `requestHardwareCatalog` contract); pagination exists opt-in (`limit`/`offset`, used by the paged frontend entry point). Changing the default would break API compatibility.
- **No response-field pruning**: `HardwareCatalogItem` projection is the verified contract; shrinking fields is an API change, not an optimization.
- **No caching layer**: same-origin nginx serves one user; server gzip removes the transfer cost that caching would have masked. Revisit only with measured multi-user load.
- **No changes to `recommendation_service` / `suitability_service`** (M4 boundary).
