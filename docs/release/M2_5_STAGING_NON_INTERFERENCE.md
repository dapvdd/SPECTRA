# SPECTRA M2.5 Staging Deployment — Non-Interference Report

Date: 2026-11-15 (UTC) · Release: dcfd7df3d77ba011bb92d8a3144615c5c3d373ec (M2.5, PR #3 merge)
Environment: DavidLab (david-lab) · Compose project: `spectra-m25-staging` · Port: 100.113.157.0:8096
Author: deployment agent (Crown AI / GLM 5.3 Flash), evidence-driven per davidlab-remote-ops discipline

## 1. Scope and contract

Mission: deploy the merged M2.5 release as an isolated staging environment and
prove that production (8080) and the existing M2 staging (8095) remain
byte-for-byte and behaviorally unchanged.

Safety contract held throughout (no violations observed or executed):
- read-only on all pre-existing resources (containers, images, volumes, networks, files)
- no production deploy/migration/restart; no volume mutation; no shared-secret changes
- no global docker prune; no force-push; no public exposure (Tailscale-IP bind only)

## 2. Baseline (Phase A, 2026-11-15 ~07:00Z) vs post-deploy (Phase J, ~10:2xZ)

| Resource | Baseline | Post-deploy | Verdict |
|---|---|---|---|
| prod container spectra-backend | 8bb67a872fdd, Up 5 days, started 2026-11-09T16:35:18Z | identical (start time unchanged) | UNCHANGED |
| prod container spectra-frontend | fb2f3aa8bb46, Up 5 days, started 2026-11-09T16:36:02Z | identical | UNCHANGED |
| prod DB SHA-256 | 7d1dca46cd19503944e82ec874902c830e94587f72b19b36c33a0f67e5c0310a | identical (Phase J re-hash) | UNCHANGED (byte-identical) |
| prod images | spectra-*:75eba50b1f... | same tags/digests; no new prod tags | UNCHANGED |
| prod health 8080 | 200 | 200 | OK |
| M2 containers | cd985517b513 / 5d9a67a93ffe, Up 2 days, started 2026-11-12T08:04:01/03Z | identical ("Up 3 days", same starts) | UNCHANGED |
| M2 DB SHA-256 | 1fa73adda45291dca97c5ea3c83fe34db0b30547cd6acfa03bbe1bc69efc2eaa | identical | UNCHANGED (byte-identical) |
| M2 health 8095 | 200 | 200 | OK |
| volumes (spectra*) | spectra-sqlite-data | same single volume; M2.5 added NONE (bind mount used) | NO DELTA |
| networks (spectra*) | spectra_default, spectra-m2-staging_default | + spectra-m25-staging_default (new, project-scoped) | NEW-ONLY |

## 3. Isolation boundaries of the new environment

- Compose project `spectra-m25-staging`; working dir `/home/david/releases/spectra-m25-staging`
- Containers `spectra-m25-backend` / `spectra-m25-frontend` (unique names)
- Network `spectra-m25-staging_default` (unique; not shared with prod/M2)
- Data: bind mount `/home/david/releases/spectra-m25-staging/data -> /app/data`
  (new directory; never overlaps prod volume `spectra-sqlite-data` or M2 bind mount)
- Images: `spectra-backend:m25-staging-dcfd7df` / `spectra-frontend:m25-staging-dcfd7df`
  (new tags; pre-existing tags untouched)
- Port: `100.113.157.0:8096->8080` (Tailscale-only; 8096 was verified free pre-deploy)
- Release env: SPECTRA_RELEASE_SHA=dcfd7df..., SPECTRA_RELEASE_VERSION=M2.5-staging
- Auth disabled (SPECTRA_AUTH_ENABLED=0), GEMINI_* unset (no outbound integrations)

## 4. Database isolation chain

1. Snapshot taken from prod via sqlite3 online backup API (read-only URI) inside
   the prod container; prod file hash verified unchanged pre/post (7d1dca46...).
2. Snapshot staged at `db/spectra-m25-preM25-dcfd7df.db` (SHA b33b08ea...),
   copied to `data/spectra.db`, migrated v2 -> v3 with the release runner
   (staging copy only; verified: version 3, integrity ok, fk clean, 5380 rows,
   39440 provenance rows preserved).
3. All subsequent writes (fixtures 5381-5389, staging conversations 7-8) hit the
   staging bind mount only.

## 5. Behavioral non-interference

- Prod catalog (CPU 3501 / GPU 1879) and M2 fixture counts unchanged through
  Phase H/J probes; M2.5 fixtures appear only on 8096.
- Prod `/api/release` returns 404 (endpoint post-dates prod build 75eba50) —
  pre-existing condition, not a regression.
- M2 `/api/release` all-unknown identity — unchanged standing configuration.
- No restart/recreate of any pre-existing container at any phase (docker ps
  start-time evidence in `evidence/j25-out.txt`).

## 6. Residual risk

- The only shared host-level resource is CPU/RAM/disk capacity; staging build
  and browser capture caused transient load only (host had 2.7GB RAM available,
  742GB disk; no memory/disk pressure events observed).
- M2.5 staging remains deployed (per contract, not torn down) consuming ~200MB
  image storage + 49MB DB; teardown procedure documented in the main report.

## Verdict

NON-INTERFERENCE CONFIRMED. Production and M2 staging are byte-identical on
their databases, identical on container identity/uptime, and healthy; all new
state is confined to `spectra-m25-staging`.
