# M3.4 Container Hardening (Task 3)

**Date**: 2026-11-26
**Artifacts**: `compose.m34.yaml` (hardened overlay), `Dockerfile.backend` (non-root).
**Status**: merged-ready on `feat/m34-fortress`; production application is user-gated.

## 1. Controls implemented

| Control | Backend | Frontend | Evidence |
|---|---|---|---|
| Non-root runtime user | `spectra` uid/gid 10001 (`USER spectra`) | uid 101 (nginx-unprivileged convention) | Dockerfile.backend; compose `user:` |
| Capabilities | `cap_drop: [ALL]` | `cap_drop: [ALL]` | compose.m34.yaml |
| Privilege escalation | `no-new-privileges:true` | same | compose.m34.yaml |
| Read-only root filesystem | `read_only: true` | same | compose.m34.yaml |
| Explicit writable paths | volume `/app/data` (unchanged name) + tmpfs `/tmp` (64 MB, 1777) | tmpfs `/var/cache/nginx` + `/var/run` | compose.m34.yaml |
| Resource limits | 512 MiB / 1.0 CPU | 128 MiB / 0.5 CPU | measured idle baseline 74.3 / 4.9 MiB — ≥6× headroom |
| Health check | preserved: curl `/health`, 10s/5s/3, start_period 5s | n/a (nginx has no health endpoint; `up` state suffices) | compose.m34.yaml |
| Minimal runtime images | unchanged (python:3.13-slim, nginx:alpine) — already minimal; further distroless work deferred (owner review) | same | Dockerfiles |

## 2. Compatibility guarantees (tested)

- **SQLite volume unchanged**: `spectra-sqlite-data:/app/data` — M3.3 backups, restore paths, and rollback runbooks remain valid byte-for-byte.
- **Bind address unchanged**: `FRONTEND_HOST_BIND:-100.113.157.0:8080` — tailscale-only exposure preserved; never 0.0.0.0.
- **Entrypoint template-init preserved**: `/app/data` + `/tmp/spectra` chowned to `spectra` at build; `entrypoint.sh` copies the template into an empty volume as the runtime user.
- **Publisher prod-path guard untouched** (regression-tested in `test_m34_container.py::TestGuardsIntact`).
- **Healthcheck contract unchanged** for orchestrators depending on it.

## 3. SQLite persistence under the hardened model — verification plan

Executed logic (rehearsal-gated; script + steps in M34_OPERATIONS_RUNBOOK.md §4):

1. Fresh volume + hardened compose up → entrypoint copies template → `/health` 200 as uid 10001.
2. Write probe (create conversation) → `docker restart` → data persists (volume ownership correct).
3. `backup_database.py` from inside the hardened container → backup file owned by spectra, verified (integrity ok).
4. Restore rehearsal (scratch target) → integrity ok → swap → healthy.
5. Migration runner on a copy → copy-swap → tracked-version current.

Each step fails closed: any permission error surfaces as an unhealthy backend, caught by the healthcheck, blocking cutover in `deploy_release.sh` (Task 5).

## 4. Residual notes

- nginx runs as uid 101 and binds 8080 (unprivileged) — no `setcap` needed; `cap_drop ALL` verified compatible.
- tmpfs sizes (64/32 MB) sized from measured working sets with ≥6× headroom; SQLite temp store defaults to `/tmp` — bounded by tmpfs size.
- The backend `pip` layer still runs as root at build time (standard; runtime is non-root).
- Distroless/read-only-image further minimization: recommended follow-up, requires owner review of build toolchain changes.
