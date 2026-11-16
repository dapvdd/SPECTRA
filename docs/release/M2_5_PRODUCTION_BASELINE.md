# SPECTRA M2.5 — Production Baseline (Phase A)

**Captured:** 2026-11-15T14:25:45Z (host), DB re-verified 2026-11-16
**Method:** read-only SSH inspection (`ssh david-lab`), `docker inspect/ps`, in-container read-only SQLite queries. Nothing was modified.
**Evidence:** `docs/release/evidence/m2-5-production-readiness/phaseA-inventory.txt`

## 1. Host

| Item | Value |
|---|---|
| Hostname | david-lab |
| OS / kernel | Debian, Linux 6.12.113+deb13-amd64 x86_64 |
| CPU / RAM | 4 CPUs · 7.6 GiB RAM (2.8 GiB available) · 3.8 GiB swap (1.3 GiB used) |
| Load average | 3.76 / 2.62 / 2.22 |
| Disk `/` (/dev/sda5) | 905G total · 119G used · 740G available (14%) |
| Docker / Compose | 29.9.2 / v5.6.1 |

## 2. Production Compose topology

| Item | Value |
|---|---|
| Compose project | `spectra` |
| Working dir / config | `/home/david/releases/spectra-75eba50-ops` / `compose.json` |
| Frontend container | `spectra-frontend` (`fb2f3aa8bb46`) — Up 6 days, image `sha256:6dec82c38484fc93e3d55f2a0e1fb3c4b2694b0558ae46c928124e0e5ff5e233` = `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Backend container | `spectra-backend` (`8bb67a872fdd`) — Up 6 days (healthy), image `sha256:8cb02c8b7e18d95df5af80ae3601d76dfcf403bb9df5764dc158a3a21c77bcd5` = `spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Port publish | `100.113.157.0:8080->8080/tcp` (frontend only; backend internal 8000, unpublished) |
| Network | `spectra_default` (frontend 172.19.0.3, backend 172.19.0.2) |
| Volume | `spectra-sqlite-data` (external named volume) → `/app/data` rw (root-owned on host; readable only via container) |
| Restart policy | `unless-stopped` both; privileged=false, caps=[], no docker.sock mounts |
| Backend env (names only) | `SPECTRA_DATABASE_URL`, `SPECTRA_CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL` (+ interpreter vars). `SPECTRA_AUTH_ENABLED` not set (auth disabled). Values not printed. |

## 3. Production database (read-only in-container)

| Item | Value |
|---|---|
| File | `/app/data/spectra.db`, 51,191,808 bytes (48.8 MiB), no WAL/SHM sidecars |
| Journal mode | `delete` |
| Integrity / FK | `integrity_check: ok` · `foreign_key_check: []` |
| Schema version | **2** (`schema_version` row: id=1, version=2, applied 2026-11-09T16:35:05Z) — matches `/api/ready` → `tracked-version-2` |

Row counts:

| Table | Rows |
|---|---|
| hardware | **5,380** (CPU 3,501 · GPU 1,879) |
| cpu_specifications / gpu_specifications | 3,501 / 1,879 |
| field_provenance | 39,440 |
| external_identifiers | 3,575 |
| benchmark_results | 1,040 |
| sources | 10 |
| users | **0** |
| build_conversations / build_messages | **7 / 10** (all owner_id NULL) |

## 4. Application health (measured)

| Probe | Result |
|---|---|
| `GET /` | 200, 0.0008 s |
| `GET /api/hardware?limit=1` | 200, 0.074 s |
| `GET /api/ready` | 200 `{"status":"ready","database":"reachable","migrations":"tracked-version-2"}` |
| `GET /api/release` | **404** (endpoint introduced after prod build 75eba50; pre-existing, not a regression) |

## 5. Release checkouts on host

| Path | State |
|---|---|
| `/home/david/releases/spectra-75eba50` | Release checkout, detached at `75eba50b1f09052f40409f6066a2ac030344d1a0`, clean (0 dirty) |
| `/home/david/releases/spectra-75eba50-ops` | Private ops dir (mode 0700): `compose.json`, Nov-9 backups (`backup-20261109T162847Z.db`, SHA-256 `a82529ec…`), migration evidence, `original-containers.json`, `rollback.json` |
| `/home/david/projects/spectra` | Legacy dirty checkout — untouched, out of scope |
| `/home/david/releases/spectra-m2-staging` / `spectra-m25-staging` | Staging environments — untouched (non-interference re-verified; see Phase G reference) |

## 6. Readiness summary

Production is healthy, at schema v2, with 5,380 hardware records and live conversation data. Capacity headroom is sufficient (disk 86% free; RAM available 2.8 GiB; production containers use ~113 MiB combined). The environment is ready for a controlled cutover preparation workflow: backup → disposable migration rehearsal → separately authorized cutover.

Nothing in this phase modified production.
