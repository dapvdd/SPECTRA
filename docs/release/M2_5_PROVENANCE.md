# SPECTRA M2.5 — Release Provenance (Phase B)

**Verified:** 2026-11-15/16 (GitHub API + remote host inspection)
**Target release:** `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec`

## 1. Source identity

| Item | Value | Evidence |
|---|---|---|
| Commit | `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` | GitHub API `/commits/dcfd7df…` — exists on `main`, merge of PR #3 (`feat/spectra-m2.5-unified-build-experience`), tree `d774605aa99eb8eff84192a23da940431e281a8b` |
| Signed | Yes (`git show %G?` = `E` at staging clone) | remote `git log` |
| CI | Workflow **CI run #65**, id `43686753889`, event `push` to `main`, status `completed` / conclusion **`success`** (2026-11-15T06:43:39Z) | GitHub API `/actions/runs?head_sha=dcfd7df…` |
| Prior test verification | 1,944 tests passed (M2.5 delivery report); staging functional 56/56; DOM 24/24; human visual acceptance on 8096 | `docs/release/M2_5_STAGING_DEPLOYMENT_REPORT.md` |
| Staging clone | `/home/david/releases/spectra-m25-staging/src`, detached HEAD at the SHA, **0 dirty files**, `origin/main` = same SHA | remote `git status`/`rev-parse` |
| Blob provenance | 7/7 critical blob SHAs matched the GitHub API tree at staging deploy time | `evidence/m2-5-production-readiness/b25-out.txt` (staging phase artifact) |

## 2. Docker image provenance

| Image | Tag | ID (sha256) | Built |
|---|---|---|---|
| Backend | `spectra-backend:m25-staging-dcfd7df` | `cd512196417560f6914a8c755c8baa4488ae4c3cc52a99dd9d22203c973d7aca` (327 MB) | 2026-11-15 (staging deploy) |
| Frontend | `spectra-frontend:m25-staging-dcfd7df` | `0ae625ae32fd1d25cbfad947652410e2833a7ad14f098fe383f7f44459c02316` (94.3 MB) | 2026-11-15 |

- Built locally on DavidLab from the verified clone (compose `build.context: /home/david/releases/spectra-m25-staging/src`), not pulled from a registry.
- Running staging containers reference exactly these image IDs (`docker inspect` verified).
- **8096 `/api/release`** confirms runtime identity: `git_sha dcfd7df…`, `version M2.5-staging`.

## 3. Build inputs

| Input | Location | Pinning |
|---|---|---|
| Backend deps | `requirements.txt` (fastapi==0.128.1, uvicorn==0.41.0, pydantic==2.12.5, SQLAlchemy==2.0.52, …) | exact versions |
| Frontend deps | `frontend/package-lock.json` via `npm ci` | lockfile |
| Base images | `python:3.13-slim`, `node:22-alpine`, `nginx:alpine` | **tag-pinned, not digest-pinned** |
| Source | git commit `dcfd7df` | SHA |

## 4. Reproducibility assessment

Rebuilding at the same SHA with the same Dockerfiles produces functionally identical images (same lockfiles, same source), but **not byte-identical** images because base-image tags float. Verified diff scope `75eba50^ → dcfd7df` touches 140 files (+15,562/−385), all application-source changes accounted for in the M2.5 milestone; Dockerfiles and requirements are **byte-identical** between prod commit and M2.5 (diff = 0 lines), so image deltas come only from `backend/`, `frontend/`, and base-image drift.

**Reproducibility limitation (recorded, no action authorized):** base images are not digest-pinned; bit-for-bit rebuild is not guaranteed. For deployment, the already-built staging image IDs above can be reused as-is, or images can be rebuilt at cutover time from the pinned checkout — both paths trace to the same SHA.

## 5. `image_digest: null` finding

- `/api/release` reports `image_digest: null` because `docker-compose.m25.yml` sets `SPECTRA_IMAGE_DIGEST: ""` and `release.py` maps an empty value to `null` ("unknown").
- The image ID **is** fully known and recorded (§2); only the diagnostic metadata is unfilled.

**Proposed provenance mechanism (staging-only, requires authorization — not applied):**
1. After a `docker compose build`, capture `docker images --format '{{.ID}}'` (or `docker image inspect` digest) for both images.
2. Write those values into the compose environment (`SPECTRA_IMAGE_DIGEST: "<sha256:…>"`) before `up -d`, or drop the hard-coded empty env and inject it at deploy time.
3. Recreate the staging stack once (`docker compose -p spectra-m25-staging -f docker-compose.m25.yml up -d`) — this also clears the empty-env finding.
4. For production, the same value should be set in the production compose at cutover time so `/api/release` reports a filled digest from first boot.

## 6. Uncommitted-change check

- Staging clone: 0 dirty files.
- Release artifacts (images) were built from that clean clone.
- Production checkout `/home/david/releases/spectra-75eba50`: clean, detached at `75eba50…` — not used for M2.5 artifacts.
- Legacy dirty checkout `/home/david/projects/spectra`: never used, never modified.

## 7. Verdict

Provenance is fully traceable: GitHub commit + successful CI run → clean local clone → locally built images with recorded IDs → running containers on 8096 verified via `/api/release` and `docker inspect`. Suitable for a separately authorized production cutover.
