# SPECTRA M2.5 — Production Readiness Report (Phases A–L)

**Prepared:** 2026-11-15/16 · **Target:** `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` → production 8080
**Production was NOT modified.** All work was read-only inspection, backups, disposable rehearsals, and document preparation. Cutover requires separate explicit authorization.

## Gate results

| Gate | Verdict | Evidence (summary) | Remaining risk | Required action |
|---|---|---|---|---|
| **G1** Release provenance | **PASS** | GitHub commit on main + CI run #65 `success`; staging clone clean at the SHA; 7/7 blob match at deploy; image IDs recorded (`cd512196…`/`0ae625ae…`); runtime `/api/release` confirms SHA on 8096 | Base images tag-pinned (not digest-pinned) → rebuilds not byte-identical (documented) | None blocking; optional: populate `SPECTRA_IMAGE_DIGEST` at deploy |
| **G2** Production inventory | **PASS** | Phase A baseline: healthy containers (Up 6 days), schema v2, integrity ok, counts captured; disk 86% free, RAM 2.8 GiB avail | Load avg ~3.8 on 4 CPUs (pre-existing host load) | None |
| **G3** Backup integrity | **PASS** | Online SQLite backup-API backup; SHA-256 `801dd666…` recorded; integrity ok, FK clean, counts identical; 0600 perms; outside container fs | Single copy on same host (acceptable for homelab; offsite not in scope) | Optional offsite copy |
| **G4** Restore rehearsal | **PASS** | Backup restored to disposable location, hash-identical, integrity ok, counts verified | None | None |
| **G5** Schema migration | **PASS** | Runner rehearsal v2→v3: 4.1–6.6 s, integrity ok, 39,440 provenance rows preserved, idempotent, downgrade+re-upgrade clean, injected-failure rolls back cleanly | Migration runs in-place on prod volume at cutover (transactional, rehearsal-proven) | Execute per runbook step 5 |
| **G6** Data preservation | **PASS** | All tables reconciled byte-level counts pre/post migration; conversations 1–7 read back; provenance orphans 0 | Post-cutover writes lost only under Strategy-B rollback (quantified ~1 conv/hour) | Operator acknowledgment in runbook |
| **G7** Security readiness | **CONDITIONAL** | No BLOCKERs; API headers strong at dcfd7df; container surface minimal; Tailscale-only; AI fail-closed; 0 users | **S-1: frontend missing CSP/XFO/nosniff** (both prod & staging) | Build + staging-verify the one-line nginx header fix BEFORE cutover, or record written waiver |
| **G8** Backend/frontend compatibility | **PASS** | Route diff: 3 additive routes, 0 removed; shared schemas unchanged; new-FE+old-BE 422 risk → atomic swap mandated; old code proven on v3 DB by runtime rehearsal | Mixed-version window exists only if swap is non-atomic | Use runbook step 6 (atomic `up -d --force-recreate`) |
| **G9** Rollback feasibility | **PASS** | Strategy A proven (old code on v3 DB: ready/catalog/conversations 200); Strategy B proven (old code on restored v2 backup); prod image tags present on host; triggers + commands documented | Stale `rollback-75eba50` tags point to pre-V3 images (documented; correct targets identified) | None (do not use stale tags) |
| **G10** Cutover runbook | **PASS** | 16-step operator runbook with verified paths, project-scoped commands, gates, measured downtime ≈30–60 s | None | Execute only after authorization |
| **G11** Resource capacity | **PASS** | Disk 740G free (DB grows +5.2 MB); RAM 2.8 GiB available; prod containers ~113 MiB; images add ~421 MB (fits) | Host memory tight at peak (swap in use, pre-existing) | Monitor during cutover window |
| **G12** Staging acceptance | **PASS** | M2.5 staging: 56/56 functional, 24/24 DOM, 14 screenshots, human visual acceptance completed (UI-2511 resolved — verdict was reviewer port confusion; fresh-context DOM proves six tabs on 8096) | Staging `image_digest` null (cosmetic) | None |

**Gate rule check:** no FAIL on data integrity, backup recovery, security isolation, or rollback feasibility → **NO-GO does not trigger.** G7 is CONDITIONAL (one pre-cutover item).

## Cross-cutting evidence

- Non-interference: prod + M2 staging containers untouched throughout (`Up 6 days` / `Up 3 days` verified at every phase); M2.5 staging DB hash stable (`1e6a14de…` md5) except documented fixture/probe data from earlier authorized staging work.
- Prod DB read-path verified read-only via `file:…?mode=ro` URI connections inside `spectra-backend`; temporary files removed; `/app/data` contains only `spectra.db` (verified).
- No secrets printed in any log/evidence; env values redacted; backup filename carries timestamp only.
- Rehearsal cleanup: worktree removed (`git worktree list` = staging src only); temp scripts deleted from host `/tmp` and container `/tmp`.

## Open items before an authorized cutover

1. **S-1 (REQUIRED_BEFORE_CUTOVER):** add `add_header X-Content-Type-Options nosniff; add_header X-Frame-Options DENY; add_header Referrer-Policy no-referrer;` to `Dockerfile.frontend`, rebuild, verify on 8096, then cutover with the fixed images — or obtain an explicit waiver.
2. Optional (recommended, config-only): fix prod `SPECTRA_CORS_ORIGINS` to include the real origin (folded into runbook §0 env block).
3. Optional: populate `SPECTRA_IMAGE_DIGEST` at deploy so `/api/release` reports the digest.

## Final verdict

**CONDITIONAL_GO** — All data-integrity, backup, migration, compatibility, and rollback gates PASS with runtime evidence; the single conditional item is the frontend security-header fix (S-1), which is a one-line, staging-testable change. Once S-1 is built+verified (or explicitly waived), the verdict becomes **GO_FOR_AUTHORIZED_CUTOVER**.

**Production has NOT been modified.** A separate, explicit authorization is still required to execute the Cutover Runbook.
