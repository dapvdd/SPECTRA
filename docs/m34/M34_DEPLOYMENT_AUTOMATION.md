# M3.4 Deployment Automation (Task 5)

**Date**: 2026-11-26
**New artifact**: `backend/app/scripts/deploy_m34.py` (+ `test_deploy_m34.py`, 8 tests)
**Reuses untouched**: `deploy_preflight.py` (all 8 guards), `deploy_release.sh` (the ONLY sanctioned bring-up path), `backup_job.py`, publisher prod-path guard.
**Production deployment**: NOT executed. Rehearsal on production host: USER-GATED.

## 1. Stage model

| Stage | When | What happens | Downtime? |
|---|---|---|---|
| **preflight** | T-30 min | All existing preflight guards: release SHA match, clean checkout, compose collision, mutable tags, backup availability, migration compatibility, disk space, volume identity. Any blocker → hard stop. | No |
| **prepare** | T-10 min (service UP) | Fresh pre-cutover backup (Online Backup API + manifest) + **database identity capture** (schema_version, core row counts, file sha256, size). | No |
| **cutover** | Window | 1) compose down (writes end) → 2) **write-loss guard**: re-capture DB identity and compare to prepare-stage capture → 3) swap candidate → 4) compose up --wait. | **Yes — this is the whole window** |
| **acceptance** | post-up | /health, /ready, /release probes; release SHA must match expected; downtime recorded. | No |
| **rollback** | on failure | compose down → up rollback compose (previous images + previous DB), per M33_ROLLBACK_RUNBOOK paths. | Yes (incident) |
| **rehearsal** | isolated env | full pipeline + honest downtime measurement, no production contact. | isolated only |

## 2. Write-loss prevention (tested)

The M3.3 cutover had a 6-minute gap between backup (15:27:13Z) and down
(15:30:13Z), and ~33 min between down and first-healthy. Any write in such
gaps is silently lost when the DB file is swapped. M3.4 closes this:

- `capture_db_identity()` fingerprints the DB (sha256 + schema_version +
  core row counts + integrity).
- `identities_match()` — any sha256/count/schema difference between
  prepare-stage and post-down captures ⇒ **cutover ABORTS** before swap.
  Test: `test_guard_aborts_on_lost_writes` proves down ran, up never ran.
- Post-down re-check also catches a crashed writer mid-interruption.

## 3. Honest downtime accounting (tested)

Per `M33_RELEASE_ACCOUNTING_CORRECTION.md` §2, the acceptance stage records:

```
user_visible_downtime = first_accepted_probe_at − down_completed_at
```

Wall clock. **Operator pauses are inside it and are never subtracted.**
There is no "effective downtime" field anywhere in the report.
Test: `test_downtime_measured_without_operator_pause_subtraction` (asserts
the note text and both timestamps; a simulated 0.2 s operator pause inside
`down` flows into the measurement).

## 4. Preparation moved OUT of the interruption window

Compared to M3.3's actual timeline (33 m 24 s downtime, of which ~19 min was
compose-file authoring and ~13 min was checksum+migration):

| Step | M3.3 (inside window) | M3.4 |
|---|---|---|
| Image build | before | before (unchanged) |
| Compose config authoring/verification | **inside (19 min)** | before (validated by `compose config` in preflight) |
| Pre-cutover backup | partially inside | prepare stage (service up) |
| DB identity capture | n/a | prepare stage (service up) |
| Migration rehearsal | before | before (unchanged) |
| Checksum verification | inside (10 min) | inside but seconds (sha256 of 56 MB ≈ 0.2 s) — the M3.3 10 min was manual double-verification, replaced by the automated identity guard |
| compose up + healthy | 36 s | target ≤ 60 s total |

Remaining user-visible downtime with M3.4 orchestration: compose down
(~5 s) + identity re-capture (~1 s) + swap (<1 s) + compose up --wait
(~10–30 s) ≈ **20–40 s**, measured by the rehearsal JSON.

## 5. Guards preserved (regression-tested)

- `deploy_release.sh` legacy-checkout refusal + `spectra-<sha>-ops` naming (test_m34_container.py::TestGuardsIntact).
- Publisher prod-path refusal (`_is_prod_path`) — untouched, asserted.
- Preflight mutable-tag and collision checks — `test_deploy_preflight.py` 100% green (40/40 with Task 5 tests).
- Fixed in passing: preflight `_run()` now fails closed (exit 127 check) when docker/git binaries are missing instead of crashing — robustness improvement, no behavior change on the Linux host.

## 6. Production rehearsal procedure (USER-GATED, prepared only)

```bash
# On david-lab, isolated project + volume (mirrors M3.3 rehearsal pattern):
cd /home/david/releases/spectra-<sha>-ops
python -m backend.app.scripts.deploy_m34 \
    --release-dir . --expected-sha <sha> --stage preflight
# full isolated rehearsal (separate compose project + volume):
python -m backend.app.scripts.run_m34_rehearsal   # wrapper: run_rehearsal()
# → rehearsal JSON includes honest downtime; target < 60 s
```

Nothing in this task activates anything on production. The stage runner
refuses to run compose outside the release directory and never touches the
production volume except through the guarded prepare/cutover flow.
