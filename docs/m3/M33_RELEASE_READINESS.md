# M3.3 Release Readiness (Phase 11 — FINAL GATE)

**Date**: 2026-11-25
**Branch**: `release/m33-production` = `5c2c7d9` + `fda2975` (pushed to
origin). RC SHA: `5c2c7d9a37109da99f20a34973503d1bd6deb236`.
**Verdict**: **READY_FOR_PRODUCTION_APPROVAL** — all 13 gate items
verified with measured evidence; execution of the production cutover is
owner-gated and NOT performed.

## The 13 gate items (measured)

| # | Item | Evidence | Status |
|---|---|---|---|
| 1 | Baseline production identity | M2.5-production, SHA `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec`, built 2026-11-16T06:52:00Z, containers `spectra-backend/frontend` (images `m25-prod-dcfd7df-s1`), compose `/home/david/releases/spectra-75eba50-ops/compose-m25.json`, port 8080 | ✅ verified (Phase 0/1, `M33_PRODUCTION_BASELINE.md`) |
| 2 | Current production health | `/api/health` `{"status":"healthy"}` (both containers healthy 9+ days); DB volume `spectra-sqlite-data` 56,430,592 B, schema **v3**, integrity ok, FK 0 | ✅ verified (Phase 0) |
| 3 | Backup + restore proof | Online-API snapshot 2026-11-25T06:25:46Z → `/home/david/backups/spectra/m33-release/m33_backup_20261125T062546Z.db` (56,430,592 B, SHA256 `d4d19d55f8dcb58b1629b662139c93400505e91849cd1871a54c55ac8d006d2c`); restore rehearsal PASSED: integrity ok, FK 0, all counts match, real app served restored copy (hardware 200, X-Total-Count 5380) | ✅ (Phase 3, `M33_BACKUP_RESTORE_REPORT.md`) |
| 4 | Migration rehearsal v3→v4 | On restored prod clone: dry-run non-mutating; applied=[4]; **row loss 0** (5380/3501/1879/1040/7/10/39440 preserved); v4 columns + ops tables + partial unique index present & enforced; legacy rows keep NULL lifecycle; idempotent rerun `up-to-date`; ORM compatible incl. rollback probe; stable after reopen. Upgrade takes **1.89 s** on prod-size DB | ✅ (Phase 4, `M33_MIGRATION_REPORT.md`) |
| 5 | Cumulative publication | 62 verified SKUs published (RAM 32 / STORAGE 10 / PSU 7 / MOTHERBOARD 13), 0 rejected, 0 conflicts, 381 UNRESOLVED never published (fail-closed held); provenance 39440→39827 (+387 all verified); **idempotency proven** (rerun: published 0 / skipped 62). **Deviation honestly reported: 62, not 64** — production v3 DB has no pilot rows (pilot never reached production; see report §6) | ✅ (Phase 5, `M33_CATALOG_PUBLICATION_REPORT.md`) |
| 6 | Isolated deployment | Images `m33-rc-5c2c7d9` built from exact SHA; compose project `spectra-m33-rehearsal` (own volume + network, port 8097); healthy; `/api/release` = M3.3-rehearsal @ 5c2c7d9; persistence proven across restart + compose recreate | ✅ (Phase 6) |
| 7 | Functional acceptance | **18/18 PASS**: verified=62 with lifecycle fields; default=5442; real specs (B650 → AM5); Builder M32-RULES-v2 with reason codes + provenance; R1/R2 COMPATIBLE; honest UNKNOWNs never auto-promoted; partial builds never COMPATIBLE; no fabricated wattage rule | ✅ (Phase 7, `M33_ACCEPTANCE_REPORT.md`) |
| 8 | Visual acceptance | **10/10 PASS** (Playwright): SPA, zero console errors, catalog composition on-screen exactly 3501/1879/32/10/13/7, verified names visible, Build page slots, 5 screenshots captured | ✅ (Phase 7) |
| 9 | Security review | No new regressions. CORS allowlist enforced (no arbitrary-origin reflection); CSP + nosniff present; SQLi probe parameterized (no 5xx); traversal blocked (400); publisher prod-path refusal verified live. 2 pre-existing findings for owner decision: F-1 ops endpoints readable while auth off (= current prod posture, gate unit-tested when on); F-2 register returns 500 while auth off. No secrets; 0 users; AI unconfigured | ✅ (Phase 8, `M33_SECURITY_REVIEW.md`) |
| 10 | Rollback rehearsal | All 5 paths PASS with timings: file rollback v4→v3 → healthy in **15 s**; forward recovery + republish (62/62 restored); restart 1 s; compose recreate ~60 s with volume persistence. Key runbook rule: rollback = **v3 file + M2.5 image**, never v3 file + RC image | ✅ (Phase 9, `M33_ROLLBACK_RUNBOOK.md`) |
| 11 | Measured downtime estimate | stop+start 5.2 s; start→healthy 2.4 s; full cycle **7.5 s**; migration 1.89 s. Cutover window budget **< 60 s** including backup + swap + health gates | ✅ measured (Phase 10) |
| 12 | Exact deployment sequence | Documented step-by-step with fresh pre-cutover backup, copy-swap migration (mandatory — runner refuses prod path), compose update to `m33-prod-5c2c7d9` images, 10-point post-cutover gate, abort criteria | ✅ (`M33_DEPLOYMENT_RUNBOOK.md`) |
| 13 | Residual risks | See §2 below — none release-blocking; 2 owner decisions + 3 documented limitations | ✅ this document |

## Residual risks & owner decisions

1. **Pilot rows (2)**: production will show 62 verified SKUs, not 64. The
   2 M3-core pilot rows never reached production (v3 schema has no
   lifecycle columns). If the owner wants them, publish post-cutover via
   the same gated pipeline (one command, idempotent). *Decision: owner.*
2. **Auth posture (F-1)**: release ships with auth disabled (unchanged from
   current prod). Ops endpoints remain readable on the LAN/tailscale
   surface. Enabling requires `SPECTRA_AUTH_ENABLED=1` +
   `SPECTRA_AUTH_SECRET=<random>` in compose. *Decision: owner.*
3. **Register 500 while auth off (F-2)**: pre-existing; recommend 403
   post-release. *Not a blocker.*
4. **CPU/GPU rule pairs**: generation/speed rules honestly UNKNOWN (no
   CPU/GPU acquisition manifests exist yet — M3.2 documented residual).
   No fabrication; socket/DDR/capacity/slots rules verified live.
5. **Single-host SQLite**: unchanged architecture; journal `delete` mode
   means the cutover window must have the backend stopped (the sequence
   does). No concurrent-writer risk beyond current prod.

## What was NOT done (explicitly)

- No production writes: live DB, prod compose, prod volumes, and prod
  containers were never modified. All rehearsal ran on copies/isolated
  deployments. The publisher's `data/spectra.db` refusal was verified live
  and respected.
- No force-push, no merges to main, no secret disclosure, no evidence-gate
  bypass anywhere in Phases 0–11.
- Production cutover (Phase 12) awaits explicit owner authorization.

## Approval gate

Required owner authorizations to proceed to Phase 12:
1. Approve release identity `M3.3-production` @ `5c2c7d9a37109da99f20a34973503d1bd6deb236`.
2. Approve the cutover window + `<60 s` downtime.
3. Decide F-1 auth posture (keep off vs enable).
4. Decide pilot-rows publication (62 vs 64).

On approval, execute `M33_DEPLOYMENT_RUNBOOK.md` §3 exactly.
