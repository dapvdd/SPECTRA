# M2 Staging Baseline — DavidLab Production Audit

Date: 2026-11-12 · Auditor: autonomous release agent · Access: `ssh david-lab` (user `david`, docker group)

## Production topology (read-only evidence)

| Item | Value |
|---|---|
| Compose project | `spectra` (working dir `/home/david/releases/spectra-75eba50-ops`) |
| Containers | `spectra-backend` (healthy, up 2 days), `spectra-frontend` (up 2 days) |
| Images | `spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0`, `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Release | legacy ops-deployment; no git checkout (deployed artifact dir) |
| Network | `spectra_default` (bridge, external from compose's view) |
| Volume | `spectra-sqlite-data` → `/app/data` (backend only) |
| Database | `/app/data/spectra.db` inside volume; 51,191,808 bytes; journal mode `delete` (no WAL); `user_version` 0 |
| Frontend | nginx:alpine, listens 8080, proxies `/api/` → `http://backend:8000/` (Docker DNS on `spectra_default`) |
| Port binding | `100.113.157.0:8080->8080` (Tailscale interface only) |
| Health | `GET /` → 200; `GET /api/health` → `{"status":"healthy"}` |
| Backups on host | `~/releases/spectra-75eba50-ops/backup-20261109T162847Z.db`, `backup-immediate-pre-migration.db`, `restore-proof-*.db` |

## Host resources

- Disk `/`: 905G total, 116G used, **743G free** (14%)
- Memory: 7745M total, **2946M available**
- Docker Engine 29.9.2 · Docker Compose v5.6.1
- Tailscale interface: `tailscale0` = `100.113.157.0/32`
- User `david`: docker group ✓, sudo group ✓ (not needed for staging); volume dir root-owned → **DB snapshot must go through a container mount, not host path**

## Other workloads (avoid colliding)

`nimbusops-nginx-demo` (:18080), `nas-grafana` (:13000), `nas-prometheus` (:19090), `homelab-homepage` (:3002), `mammon-dashboard` (:8765), `davidcloud-*` (**:8081 used**), telegram bots, netdata (:19999), exporters. Existing networks: `spectra_default`, `davidcloud_default`, `homepage_default`, `mammon_default`, `nas-observability_monitoring`, `netdata_default`, `nexus-openclaw_default`.

## Staging isolation design (Gate B)

| Dimension | Production | **Staging (planned)** |
|---|---|---|
| Compose project | `spectra` | `spectra-m2-staging` |
| Containers | `spectra-backend`, `spectra-frontend` | `spectra-m2-staging-backend-1`, `spectra-m2-staging-frontend-1` (compose-generated; no `container_name`) |
| Network | `spectra_default` | `spectra-m2-staging_default` (compose-scoped) |
| Volume | `spectra-sqlite-data` (external) | **bind mount** `/home/david/releases/spectra-m2-staging/data` (staging-owned, explicit, easily removed) |
| Port | `100.113.157.0:8080` | **`100.113.157.0:8095`** (verified free; Tailscale-only, not public) |
| Images | `spectra-*:75eba50b…` | `spectra-backend:m2-staging-4293cdf`, `spectra-frontend:m2-staging-4293cdf` |
| Env | production CORS | staging-only CORS (staging origin), no secrets |
| Entrypoint | migrates at boot | same image, **migration pre-applied to the staging DB copy** (entrypoint becomes a no-op check) |

No shared names, no shared network/volume, no public 0.0.0.0 binding, no privileged containers, no Docker socket, no `latest` tags, no production credentials copied (GEMINI_API_KEY empty in prod compose and intentionally omitted in staging).

**Gate A: PASS** — topology understood, snapshot path proven (volume read via container mount), resources sufficient.
**Gate B: PASS (design)** — zero collision surface; validated again against live state before startup (Phase E).
