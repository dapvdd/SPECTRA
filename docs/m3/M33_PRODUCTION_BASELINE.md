# M3.3 Production Baseline — DavidLab (Phase 1)

**Date**: 2026-11-25 (captured via ssh david-lab, read-only)
**Captured by**: M3.3 release engineering (autonomous gate run)

## 1. Running production identity

| Item | Value (evidence) |
|---|---|
| Compose project | `spectra` — `/home/david/releases/spectra-75eba50-ops/compose-m25.json` |
| Containers | `spectra-backend` (healthy), `spectra-frontend` (up) |
| Images | `spectra-backend:m25-prod-dcfd7df-s1`, `spectra-frontend:m25-prod-dcfd7df-s1` |
| Release identity | version=`M2.5-production`, git_sha=`dcfd7df3d77ba011bb92d8a3144615c5c3d373ec`, built_at=2026-11-16T06:52:00Z, digest=`sha256:cf19a3ec…` |
| Auth | `SPECTRA_AUTH_ENABLED` unset → auth disabled (identity module: auth_enabled=False) |
| AI | unconfigured (GEMINI_API_KEY empty) |

## 2. Database state (inside container, read-only)

| Item | Value |
|---|---|
| Path | `/app/data/spectra.db` (volume `spectra-sqlite-data`, created 2026-10-14) |
| Size | 56,430,592 bytes |
| Schema version | **3** (schema_version table: id=1, version=3, applied 2026-11-16T07:31:47Z) |
| Journal mode | `delete` (no WAL; no -wal/-shm files present) |
| integrity_check | ok |
| foreign_key_check | 0 violations |
| hardware_total | **5380** (CPU 3501, GPU 1879) |
| benchmark_results | **1040** |
| users | 0 |
| build_conversations | 7 (+ build_messages) |
| v4 identity columns | **ABSENT** on hardware (no canonical_key/product_family/identity_status/record_status/superseded_by_id) |
| v4 spec tables | present (ram/storage/psu/motherboard_specifications — M2.5-era schema) |

## 3. API health (live)

| Probe | Result |
|---|---|
| `GET /health` (backend direct) | `{"status":"healthy"}` |
| `GET /api/health` (through frontend nginx) | `{"status":"healthy"}` |
| `GET /api/hardware?limit=1` | `[{"id":1,"name":"AMD Athlon Gold 7220C","manufacturer":"AMD","type":"CPU",…}]` |
| Frontend `GET /` | HTTP 200, SPA index served |
| CSP/security headers | present on nginx responses (CSP, nosniff, DENY, no-referrer) |

## 4. Routing & deployment architecture

- Frontend nginx (in `spectra-frontend` image) listens 8080, binds `100.113.157.0:8080` (tailscale IP).
- `/api/` → `proxy_pass http://backend:8000/` (compose network `spectra_default`), response headers hardened per-location.
- `/assets/` immutable 1y; `/index.html` no-cache; SPA fallback `try_files $uri $uri/ /index.html`.
- No separate reverse-proxy container; nginx IS the frontend container.
- Restart policy: `unless-stopped` both services. Healthcheck: backend only (curl /health, 10s interval).

## 5. Host resources

- 4 vCPU, 7.7 GB RAM (3.1 GB available at capture), disk `/` 905G with 735G free.
- Host user `david` cannot read `/var/lib/docker/volumes/...` directly (NO_VOLUME_ACCESS) — all DB operations must go through `docker exec`/`docker run --volumes-from`.

## 6. Production drift vs GitHub main

| Item | Production | origin/main |
|---|---|---|
| Commit | dcfd7df (M2.5 merge) | 5c2c7d9 (M3.2 merge, PR #8) |
| Schema | v3 (no v4 identity columns) | v4 (migration 4 adds the 5 identity/lifecycle columns + unique partial index) |
| Catalog | 5380 legacy CPU/GPU rows, no verified-published concept | verified-published contract (PUBLISHED+confirmed), 64 cumulative verified SKUs available from manifests |
| Features | M2.5 unified build experience | + M3/M3.1/M3.2: evidence-gated publishing, verified catalog API + toggle/chips, compatibility M32-RULES-v2 (R1–R9 + reason codes) |

Drift is the expected release gap; M3.3 closes it. **No production-only data conflicts**: users table empty; 7 build_conversations are the only user data (preserved through migration; build_conversations gains nullable owner_id in v4 — legacy rows keep NULL owner).

## 7. Existing backup/rollback mechanisms (discovered)

- `/home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-*.db` — two DB snapshots from M2.5 cutover prep.
- `/home/david/projects/spectra/backups/spectra_backup_20261109.db` — older snapshot.
- `/home/david/releases/spectra-75eba50-ops/` — M2.5 cutover ops scripts (`backup.py`, `migrate.py`, `rollback.json`, `compose.json.pre-m25-backup`, restore-proof DBs + evidence JSONs). Pattern: file-copy backup + restore proof; journal_mode=delete made file copies consistent at rest.
- `docker volume` is the single source of truth for prod data; no WAL => a quiesced copy via container stop (or sqlite backup API) is consistent.

## 8. Release candidate

- **RC SHA**: `5c2c7d9a37109da99f20a34973503d1bd6deb236` (PR #8 merge, tip of origin/main; verified ancestor).
- Expected post-release catalog additions: 64 verified SKUs (RAM 33, STORAGE 10, PSU 8, MOTHERBOARD 13) from the M3/M3.1/M3.2 manifests, plus the M3 Core pilot already counted within that total (2 pilot rows: RAM 1, PSU 1).

## 9. Legitimate production-only data to preserve

- All 5380 hardware rows (legacy CPU/GPU catalog), 1040 benchmarks, 7 build_conversations + messages, sources table rows, external_identifiers.
- Migration v4 is additive (5 nullable columns + partial unique index on canonical_key) — legacy rows keep NULL identity columns by contract.
