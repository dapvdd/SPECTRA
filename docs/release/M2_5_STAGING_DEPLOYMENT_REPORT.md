# SPECTRA M2.5 Staging Deployment & Acceptance Report

Date: 2026-11-15 (UTC) · Release: `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` (short dcfd7df)
Target: DavidLab · `100.113.157.0:8096` · compose project `spectra-m25-staging`
Directory: `/home/david/releases/spectra-m25-staging`
Executed by: deployment agent per gates A–L mission contract (read-only on prod + M2 staging)

## Verdict

**STAGING_ACCEPTED_PENDING_VISUAL**

All functional, data, security, isolation and rollback gates passed with
verifiable evidence. The single open item is the human pixel review of the 14
captured screenshots: the reviewing agent cannot read PNG pixels (documented
limitation), so visual correctness is proven only at the DOM-structure level
(24/24 assertions). Per mission rubric this maps to
STAGING_ACCEPTED_PENDING_VISUAL, not STAGING_ACCEPTED.

## Gate results

| Gate | Scope | Result | Evidence |
|---|---|---|---|
| A Baseline audit | host, docker, DBs, ports | PASS | audit-out2.txt, audit2/3, predeploy-baseline.json |
| B Release provenance | git clone @ dcfd7df | PASS | b25-out.txt (7/7 blob SHA match vs GitHub API tree) |
| C Isolated design | compose validation | PASS | compose-config-resolved.json, c25-out.txt |
| D Consistent snapshot | prod DB -> staging | PASS | d25-out.txt (prod hash unchanged pre/post) |
| E Migration v3 | staging copy only | PASS | e25-out.txt (runner verify, integrity, fk clean) |
| F Fixtures | 9 M25-STAGING-FIXTURE rows | PASS | fixtures output (ids 5381-5389) |
| G Deploy + health | build + up | PASS | g25-out.txt (health 200, ready v3) |
| H Functional API | 56 checks | PASS 56/56 | h25-out2.txt (out.txt = raw 55/56 w/ expectation fix) |
| I Browser/DOM | 24 DOM assertions | PASS 24/24 | i25-part2-out.txt + dom-checks.json |
| J Non-interference | prod + M2 unchanged | PASS | j25-out.txt, NON_INTERFERENCE report |
| K Rollback drill | staging stop/start | PASS | k25-out.txt (health 000 -> 200, DB hash stable) |
| L Report | this document | DONE | — |

## Provenance chain

- Commit `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` = main HEAD at deploy time
  (GitHub API), signed merge of PR #3 (parents abb2548 + 29a3b66), CI run
  43686753889 success 2026-11-15T06:43Z.
- Host clone: detached HEAD at the SHA, 0 dirty files, 7/7 critical blobs
  (Dockerfiles, entrypoint, requirements.txt, package-lock.json, compose.yaml,
  migrations/runner.py) match the GitHub API tree SHAs exactly.
- Images built from that checkout:
  - `spectra-backend:m25-staging-dcfd7df` manifest list sha256:cd512196417560f6914a8c755c8baa4488ae4c3cc52a99dd9d22203c973d7aca
  - `spectra-frontend:m25-staging-dcfd7df` sha256:0ae625ae32fd1d25cbfad947652410e2833a7ad14f098fe383f7f44459c02316
  - running containers reference these image IDs (docker inspect verified)
- `/api/release` reports git_sha dcfd7df..., version M2.5-staging.

## Data & migration

- Snapshot: sqlite3 backup API (read-only source) from prod @ SHA
  7d1dca46...; staged copy b33b08ea...; migrated to v3 -> live staging DB
  eb1fdc23... (stable across Phase K restart).
- Post-migration: schema_version 3 (2026-11-15T09:32:02Z), integrity ok,
  foreign_key_check clean, 5380 hardware rows, 39440 provenance rows preserved,
  4 new spec tables created.
- Credential isolation: prod `users` table empty -> nothing to sanitize;
  staging runs SPECTRA_AUTH_ENABLED=0 (no secrets required or present).
- Fixtures: 9 rows `M25-STAGING-FIXTURE ...` (RAM x3, STORAGE x2, MOTHERBOARD x2,
  PSU x2) with dedicated staging-only source (id 11) and uncertain provenance;
  catalog totals: CPU 3501, GPU 1879, RAM 3, STORAGE 2, MOTHERBOARD 2, PSU 2.

## M2.5 semantics verified on staging (Phase H/I)

- rules_version = `M2.5-RULES-v1` (bumped from M2's M2-RULES-v1; documented).
- PSU two-tier advisory policy: 750W >= TDP-reference -> UNKNOWN (never
  COMPATIBLE from listed TDPs; explanation marked non-authoritative); 750W vs
  900W-TDP GPU (reference floor 1333W) -> INCOMPATIBLE.
- GPU-slot rule UNKNOWN with slots > 0 (no PCIe generation data).
- Aggregate precedence INCOMPATIBLE > UNKNOWN > COMPATIBLE exercised in all
  three directions; empty/mobo-only builds UNKNOWN with zero rules.
- Error contract: 404 unknown id, 422 wrong category, 422 invalid category,
  determinism verified, no catalog growth during checks.

## Security (staging)

- API security headers present (nosniff, DENY, no-referrer, CSP default-src 'none').
- Traversal 400; SQL probe 0 rows; malformed inputs 422; extra fields forbidden.
- AI endpoints 503 with safe message (no GEMINI key configured; no outbound).
- Rate limiting disabled by default (env parity with prod).
- users table: 0 before and after all probes.

## Findings (non-blocking, release-level)

1. **Frontend static shell lacks CSP/XFO** — backend API carries security
   headers; the nginx static layer does not. Identical behavior in prod/M2
   lineage; recommend an upstream nginx config block for a future release.
2. **`SPECTRA_IMAGE_DIGEST` empty in `/api/release`** — compose file hardcodes
   `""` which overrides the deploy shell env. Provenance is still pinned by the
   image tag + recorded build manifest list above. Recommend removing the
   hardcoded empty env from the staging compose (kept as-is to preserve the
   validated Phase C config).
3. **Staging conversations 7-8 created during DOM capture** — expected
   application behavior (build assistant), staging-only, disclosed.

## Artifacts

- Remote (`/home/david/releases/spectra-m25-staging/`):
  - `docs/design/evidence/m2-5-staging/`: 14 PNGs + dom-checks.json +
    phase outputs (22 files, 2.7MB)
  - `evidence/`: h25.py/h25-out(.2).txt, i25-part1/2 (.py/.out), j25-out.txt,
    k25-out.txt, sec25-out.txt, sec25b/c-out.txt, compose-config-resolved.json
  - `db/spectra-m25-preM25-dcfd7df.db` (pre-migration snapshot, b33b08ea...)
  - `data/spectra.db` (live staging DB, eb1fdc23...)
  - `docker-compose.m25.yml` (validated), `src/` (verified checkout)
- Local mirror: `C:\Users\user\AppData\Local\Temp\opencode\m25\` (all phase
  outputs + predeploy-baseline.json + verdict files)

## Rollback / teardown

- Stage-level rollback (executed, Phase K): `docker compose -p
  spectra-m25-staging -f docker-compose.m25.yml stop|start` — proven working.
- Full removal (NOT executed; environment intentionally left running for human
  visual review): `docker compose -p spectra-m25-staging -f docker-compose.m25.yml
  down` then remove `/home/david/releases/spectra-m25-staging/data` contents and
  images `spectra-*-m25-staging-dcfd7df` if desired. These touch ONLY
  project-scoped resources.

## Human visual review checklist (PENDING)

Reviewer should open the PNGs in `docs/design/evidence/m2-5-staging/` and
confirm: landing hero typography; six-slot grid layout; chip colors
(unknown=amber, incompatible=red); rule list hierarchy; detail pages for
RAM/MB/STORAGE/PSU; mobile 390px stacking; dark theme palette. DOM assertions
already confirm structure/order/state; pixel judgment is the open item.
