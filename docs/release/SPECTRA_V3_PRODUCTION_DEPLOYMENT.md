# SPECTRA V3 production deployment attempt

Date: 2026-11-09

**Verdict: BLOCKED_FOR_SAFETY**

Production URL: http://100.113.157.0:8080

## Execution ledger

- [x] Inspect local source, origin, remote checkout, containers, disk, persistence and health.
- [ ] Establish clean deployment checkout: **blocked**.
- [ ] Verify existing backup and create fresh pre-migration backup.
- [ ] Disable writes and establish absence of database writers.
- [ ] Execute and verify segment backfill and schema v1/v2 migration.
- [ ] Build and deploy backend and frontend.
- [ ] Execute live browser/API/database smoke checks.
- [x] Record the failed preflight gate.

## Source verification

Local main initially clean at `8e6dea44b0484eb49eaf76ae3c9959f0f909c678`.
Fetched origin/main matched that exact SHA. Approved baseline
`d462040db0e85b2e4becf19b5ad45a132a637e6a` is an ancestor; the only
change from the baseline to the release candidate is the production release
report. Thus local application source matches the tested baseline. Tests
reported in the earlier release report were not rerun in this attempt.

Remote checkout: `/home/david/projects/spectra`, HEAD
`cca96d94a227b9ced40b6a0e98674ae979da4d89`.
Remote fetch advanced origin/main from `f0e377d` to `8e6dea4`.
`git log origin/main..HEAD` returned no commits.

Remote status showed **37 staged files, two modified backend files and four
untracked files**. The staged frontend and Dockerfile.frontend match `f0e377d`
(`git diff --cached f0e377d --name-only -- frontend Dockerfile.frontend`
returned no paths), but do not match the approved V3 source.

Modified backend files:

- `backend/app/schemas/comparison.py`
- `backend/app/services/comparison_service.py`

Their changes add nullable comparison handling, but their complete contents
are not identical to origin/main: the deployed checkout lacks GPU request and
response models, `compare_gpus`, direction-aware comparison and derived CPU
power efficiency. These differences also exist against `f0e377d`.

Untracked files reported:

- `backend/app/test_comparison_service.py`
- `compose.override.yaml`
- `compose.override.yaml.bak-before-tailscale`
- `data/spectra.db.upload`

The release report describes local edits as duplicating upstream content.
Inspection establishes a partial older overlay, not a clean or
content-identical application checkout. Under the requested clean-checkout
gate and stop-on-divergence rule, rollout stopped before reconciliation or
production mutation. No reset, stash, checkout replacement or deletion was
performed. A subsequent attempt needs an explicitly reconciled, preserved
deployment checkout or an approved isolated exact-release deployment context.

## Verified runtime identity and persistence

The exact running source commit cannot be established from the checkout:
containers and checkout are distinct evidence. Verified running image IDs:

| Service | Image ID |
| --- | --- |
| spectra-backend | `sha256:bcd58f603cdd7dbff8359d45c835d8784c49955442576bca78dfe9652f9a4378` |
| spectra-frontend | `sha256:52369140ad112d25a7503b73cfdbcb406bc0e706996a49f9fddc7b66b7af70dd` |

These match the pre-V3 runtime images documented in the release report.
No V3 image was built or deployed, and no new rollback tag was created.

Backend persistence is the named volume `spectra-sqlite-data`, mounted read/write
at `/app/data`, host path `/var/lib/docker/volumes/spectra-sqlite-data/_data`.
The frontend has no mounts. Compose project is `spectra`. Backend container
labels refer to `compose.yaml`; frontend labels refer to `compose.yaml` and
`compose.override.yaml`. The override binds `100.113.157.0:8080:8080`.
Root filesystem had 744 GiB available (14% used).

## Health, backup and migration evidence boundaries

`GET http://100.113.157.0:8080/api/health` returned HTTP 200 and
`{"status":"healthy"}`. Docker reported the backend healthy and the frontend
running. This is a basic availability check, not V3 acceptance verification.

The existing backup path from the earlier report is
`/home/david/projects/spectra/backups/spectra_backup_20261109.db`.
Its historical SHA256 is
`a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7`.
**Accessibility, hash, integrity, row counts and recoverability were not
reverified in this attempt.** No fresh backup was created because preflight
stopped before the backup/migration phase. No current database integrity or
schema-version claim is made.

Writes were never disabled; no migration, database restore, down-migration,
container replacement, volume removal or unrelated service change occurred.
Rollback was unnecessary because no rollout took place. Browser smoke,
authentication, route compatibility, cache-policy and new-asset checks were
not executed. Existing auth/AI configuration limitations remain historical
findings from the release report, not newly verified results.

## Remaining blocker

Reconcile and preserve the dirty remote deployment checkout under a concrete
authorized procedure, then rerun preflight and all subsequent gates. Production
continues on the exact pre-V3 images above; V3 is not live from this attempt.
