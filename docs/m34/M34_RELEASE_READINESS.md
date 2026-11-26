# M3.4 Release Readiness (Task 8)

**Date**: 2026-11-26
**Branch**: `feat/m34-fortress` (from `main`@`5c2c7d9a37109da99f20a34973503d1bd6deb236`)
**Production**: M3.3 @ `5c2c7d9` — untouched throughout this milestone.

## 1. Verdict

**CONDITIONAL_REVIEW**

All code-level acceptance gates pass (§2). The conditions are the mission's
explicit owner-approval gates (§4): production deployment rehearsal, live
auth changes, scheduled job activation, and the annotated release tag cannot
be executed autonomously by design. No blocking defects are known.

## 2. Acceptance results

| Gate | Result | Evidence |
|---|---|---|
| Backend CI-parity suite | **1591 passed / 2 skipped / 0 failed** (CI-parity command incl. both CI deselects) | local run post-Task-6, 54.8 s |
| Frontend suite | **693 pass / 0 fail** | `npm test` post-Task-7 |
| Auth regression tests | 64/64 (`test_auth_security.py`, `test_m3_security.py`, `test_m34_auth_fix.py`, `test_v31_matrix.py`) | Task 2 |
| F-2 fix regression | 10/10 (`test_m34_auth_fix.py`) incl. auth-off 201 + unusable placeholder token + 403 registration-disabled matrix | Task 2 |
| Container hardening acceptance | 16/16 static compose/Dockerfile/guard tests (`test_m34_container.py`); runtime rehearsal user-gated | Task 3 |
| Backup automation acceptance | 7/7 job tests + 23/23 preexisting backup/restore tests; **live scratch exercise**: backup created, manifest sha256 verified, verify-set audit `last_good_ok: true` | Task 4 |
| Restore rehearsal | fail-closed refusal of a hardware-less dev DB (by design); production-data rehearsal already proven in M3.3 | Task 4 |
| Persistence/restart | volume path unchanged + entrypoint template-init preserved under non-root (static); runtime restart test in §4 gate | Task 3 |
| Deployment orchestrator | 8/8 stage tests incl. write-loss abort + honest downtime accounting; preflight suite 100% green | Task 5 |
| API performance comparison | measured baseline (1,022,879 B; 0.24–0.35 s; 8 temp-file spills/24 h) → gzip + in-memory buffering implemented; compatibility pinned (6 tests) | Task 6, M34_PERFORMANCE_REPORT.md |
| Browser smoke tests | not run against production (no deployment); covered by 693 frontend unit tests; visual/Playwright smoke re-run is a post-deploy acceptance step | §4 |
| Security review | M34_SECURITY_REPORT.md: F-1..F-5 documented; F-2 fixed; F-3/F-4 fixed; F-1 prepared (owner-gated); no live changes | Task 2 |

## 3. Deliverables

| Document | Content |
|---|---|
| `docs/m34/M34_SECURITY_REPORT.md` | F-2 fix, exposure audit, findings F-1..F-5, dispositions |
| `docs/m34/M34_OPERATIONS_RUNBOOK.md` | daily health snapshot, alert handling, manual backup, restore, staged deploy |
| `docs/m34/M34_BACKUP_AUTOMATION.md` | job contract, guarantees, scratch acceptance evidence |
| `docs/m34/M34_DEPLOYMENT_AUTOMATION.md` | stage model, write-loss guard, honest downtime, guarded bring-up |
| `docs/m34/M34_PERFORMANCE_REPORT.md` | measured baseline, root causes, fixes, expected effect |
| `docs/m34/M34_CONTAINER_HARDENING.md` | controls, compatibility guarantees, rehearsal plan |
| `docs/m34/SECURE_AUTH_CONFIG.example.env` | prepared fail-closed auth config (not activated) |
| `docs/m3/M33_RELEASE_ACCOUNTING_CORRECTION.md` + `M33_PRODUCTION_RELEASE_REPORT_v1.1_ANNOTATED.md` + `m33_release_tag_message.txt` | Task 1 corrections + prepared tag |
| `ops/backup/cron_backup.sh.example` | prepared schedule (not installed) |
| `compose.m34.yaml` | hardened runtime overlay |

## 4. Owner-gated conditions (before these are done, verdict stays CONDITIONAL)

1. **Production deployment rehearsal** on david-lab with the staged
   orchestrator (`run_rehearsal`, isolated project/volume) → honest downtime
   measurement < 60 s; then browser smoke (Playwright 5-page) against the
   rehearsal stack.
2. **Merge approval** + production release following
   `M34_OPERATIONS_RUNBOOK.md` §5 (never bypassing `deploy_release.sh`).
3. **Auth posture decision**: apply `SECURE_AUTH_CONFIG.example.env` (or
   explicitly re-approve the auth-off posture given F-1's multi-user tailnet
   finding).
4. **Schedule activation**: install the nightly backup cron (and optionally
   the 5-min monitor).
5. **Annotated tag**: `git tag -a m33-production-5c2c7d9 … -F
   docs/m3/m33_release_tag_message.txt && git push origin <tag>` after
   approval.

## 5. Known residuals (non-blocking)

- F-1 remains until the owner decides the auth posture (prepared config ready).
- `pip-audit`/dependency scanning not in CI (F-5) — recommended follow-up.
- Distroless runtime images — optional further minimization.
- Unfiltered `/hardware` remains ~1 MB uncompressed for non-gzip clients
  (compatibility contract); gzip clients see ~10× reduction. Pagination
  by default would be an API break and was deliberately not taken.
- Probe conversation id 8 in production DB (documented M3.3 residual,
  disposable).
