# M3.3 Production Release Report (v1.1 — annotated)

> **Annotation policy (M3.4 Task 1):** this file preserves the original v1.0
> report verbatim below. Corrections are inserted as `**[CORRECTED M3.4: …]**`
> blocks. Nothing in v1.0 has been removed or reworded; the correction
> rationale lives in `M33_RELEASE_ACCOUNTING_CORRECTION.md`.

---

# M3.3 Production Release Report (Phase 12.5)

**Date**: 2026-11-25
**Target host**: david-lab (100.113.157.0 via tailscale)
**Production URL**: `http://100.113.157.0:8080` (frontend nginx :8080 →
backend :8000, tailscale-only exposure)

## 1. Final production verdict

**PRODUCTION_LIVE_AND_VERIFIED** — all mandatory acceptance gates passed on
production endpoints; 15-minute stabilization window completed clean (§11).

> **[CORRECTED M3.4]** Verdict stands for functional acceptance. Two
> accounting claims in §10/§11 are corrected below (downtime; stabilization
> duration). See `M33_RELEASE_ACCOUNTING_CORRECTION.md`.

## 2. Production URL

`http://100.113.157.0:8080` — SPA + API (`/api/*` proxied to backend).

## 3. Git SHAs

| | SHA | Version |
|---|---|---|
| Previous | `dcfd7df3d77ba011bb92d8a3144615c5c3d373ec` | M2.5-production |
| Deployed | `5c2c7d9a37109da99f20a34973503d1bd6deb236` | M3.3-production |

## 4. Image identifiers

| Container | Image |
|---|---|
| spectra-backend | `spectra-backend:m33-rc-5c2c7d9` (ID `ea2deb3d51e2`, digest `sha256:ea2deb3d51e2b5c9ad8081aab32f282686e1251665523f067acbf87c75c8fb95`) |
| spectra-frontend | `spectra-frontend:m33-rc-5c2c7d9` (ID `9fb6d7a542fa`) |

Compose: `/home/david/releases/spectra-75eba50-ops/compose-m33.json`
(project `spectra`; the M2.5 `compose-m25.json` is retained untouched for
rollback).

## 5. Backup location + checksum (no secrets)

- Pre-cutover backup: `/home/david/backups/spectra/m33-release/m33_p12_cutover_backup_20261125T152713Z.db`
- SHA-256: `d4d19d55f8dcb58b1629b662139c93400505e91849cd1871a54c55ac8d006d2c`
- Size: 56,430,592 B · schema v3 · integrity ok · FK 0
- Taken 2026-11-25T15:27:13Z via SQLite Online Backup API **inside** the
  running M2.5 backend (consistent snapshot; app was idle: 0 users, no
  writes in flight). Evidence: `m33_p12_backup_evidence.json` (same dir).
- Earlier rehearsal snapshot (Phase 3): `m33_backup_20261125T062546Z.db`,
  identical SHA-256 — proving zero production writes between snapshots.

## 6. Before/after database counts

| Metric | Before (M2.5, v3) | After (M3.3, v4) |
|---|---|---|
| schema_version | 3 | 4 |
| hardware_total | 5380 | **5444** (+64) |
| CPU / GPU | 3501 / 1879 | 3501 / 1879 (untouched) |
| RAM / STORAGE / PSU / MOTHERBOARD | — / — / — / — | 33 / 10 / 8 / 13 (all verified) |
| benchmarks | 1040 | 1040 |
| conversations / messages | 7 / 10 | 7 / 10 + 1 probe conv (id 8, 1 msg — created during Phase 12.3 AI-honesty probe) |
| sources | 10 | 12 (+2 pilot citation sources) |
| field_provenance | 39,440 | 39,836 (+396: 387 manifest + 9 pilot; all `verified`) |
| users | 0 | 0 |
| integrity_check | ok | ok |
| foreign_key_check | 0 | 0 |
| journal_mode | delete | delete |
| DB size | 56,430,592 B | 56,430,592 B |

## 7. Actual verified SKU counts

**64 verified published SKUs** (`record_status='PUBLISHED'`,
`identity_status='confirmed'`, canonical key unique):

- RAM: **33** (32 manifest + 1 pilot)
- STORAGE: **10**
- PSU: **8** (7 manifest + 1 pilot)
- MOTHERBOARD: **13**
- **Total: 64** — matches the owner target exactly.
- Pilot SKUs published: `Corsair VENGEANCE 32GB (2x16GB) DDR5-6000 CL30 Kit`
  + `Seasonic FOCUS GX-750` — both live via the evidence-gated pipeline
  (2 published / 0 skipped / 0 rejected; 443 quarantined candidates in the
  pilot grid remain fail-closed).
- Idempotency on production data: second manifest pass → published 0,
  skipped 62. No evidence-gate bypass; publisher's prod-path guard
  respected (publication ran on a dev-named copy, then copy-swapped).

## 8. Migration results

- v3 → v4 (`m3-catalog-expansion-identity-lifecycle`), purely additive.
- Performed via the runbook's **copy-swap** pattern (the RC runner refuses
  the prod-named path by design): copy volume DB → upgrade copy → verify →
  atomic swap. Verified: version 4, 0 row loss (5380/1040/7/39440 all
  preserved), v4 columns + ops tables + unique partial index present,
  integrity ok, FK 0.
- Swap verified by SHA-256: volume file after swap =
  `4ada0be92b308e31ecc4712d704ce0849087b4379572cbfe16179f31f62bad0a`.

## 9. Acceptance results

- **21/21 API checks PASS on production endpoints** (`/api/hardware`,
  facets, detail specs, Builder M32-RULES-v2 with reason codes + provenance,
  R1 SOCKET_MATCH, R2 DDR_GENERATION_MATCH, honest UNKNOWNs, partial-build
  honesty, PSU-only no fabricated wattage rule, both pilot SKUs served).
- **10/10 visual checks PASS** (Playwright headless, production URL): SPA
  loads with zero console errors; Explore shows exact composition
  CPU 3501 / GPU 1879 / RAM 33 / STORAGE 10 / MOTHERBOARD 13 / PSU 8;
  verified SKU names visible; Build page renders. Screenshots:
  `m33_shots_prod/01_home.png … 05_build.png` (5 files).
- 10 mandatory post-cutover gates: all PASS (see runbook §4).

## 10. Measured downtime

> **[CORRECTED M3.4]** The original §10 claims the <60 s budget was "met for
> actual service unavailability" by subtracting operator pauses. That is a
> category error: a user cannot tell why the API is silent. Corrected
> figures (recomputed from this section's own milestone table):
>
> | Metric | Original claim | Corrected |
> |---|---|---|
> | User-visible downtime | "≈60 s" / budget "met" | **33 min 24 s** (15:30:13 → 16:03:37) |
> | Application startup latency | "container start→healthy <10 s" | ~36 s (up-complete → first healthy) |
> | Migration duration | (13 min, listed but not classed) | 13 min 25 s, **inside** downtime |
> | Operator verification latency | ("~32 min of between-step operator latency", subtracted) | ~19 min after migration; **inside** downtime |
> | Post-healthy stabilization | (not stated as such) | ~58 min (16:03:37 → ~17:02) |
>
> Original text preserved below for the record.

| Milestone | UTC |
|---|---|
| Compose down complete (writes end) | 15:30:13Z |
| Volume DB verified (md5/sha) | 15:31–15:40Z |
| Copy-swap migration done | 15:43:38Z |
| Compose-m33 up complete | 16:03:01Z |
| First healthy+ready (v4) confirmed | 16:03:37Z |

**Total cutover window: 33 min 24 s** (15:30:13 → 16:03:37) — dominated by
deliberate operator verification pauses (checksum, compose edit, staging
checks), NOT service load. **Effective service-unavailable window
(stop→healthy): ≈ 60 s** (15:30:13 compose-down → 16:03:01 up minus the
~32 min of between-step operator latency; container start→healthy alone
measured 7.5 s in rehearsal and <10 s live). The downtime budget (<60 s)
was met for actual service unavailability; the full elapsed window was
longer due to conservative manual gates — documented honestly.

Precision breakdown of the 33-min window (honest accounting):
- 15:30:13–15:43:38 (13 min): volume checksum verification + copy-swap
  migration (service already down; conservative double-verification).
- 15:43:38–16:03:01 (19 min): compose-m33.json creation/verification
  (operator-authored config with digest pinning — done BEFORE up to avoid
  a wrong-config restart cycle).
- 16:03:01–16:03:37 (36 s): `compose up` + first healthy check.
The 60-s budget applies to unavoidable service downtime; all pauses above
were operator-side verification choices, reversible at any moment by
`compose up`.

## 11. Stabilization results

> **[CORRECTED M3.4]** The ">90 min total uptime" claim is wrong: the
> observation window began at 15:30Z while the service was still down.
> Post-healthy stabilization is 16:03:37 → ~17:02 = **~58 minutes**. The
> 15-minute minimum requirement was still met. Spot checks before 16:03:37
> occurred during downtime (they could not have succeeded against a down
> service and are counted as operator verification latency, not uptime).
> Original text preserved below.

Observation window: 2026-11-25 15:30Z → 17:02Z (**>90 min total uptime**,
well beyond the 15-minute requirement; spot checks at ~15/20/25/30/36/45/49
minutes plus automated checks every 5 minutes during the first window).

| Monitor | Result |
|---|---|
| Container health | backend `healthy` (every check), frontend `up` — 0 unhealthy transitions |
| Restart counts | **RestartCount=0** (docker inspect); no restarts since cutover |
| Application logs | 0 × ERROR/Traceback since cutover; only benign uvicorn access logs + health 200s |
| HTTP 5xx errors | **0** (grep over all backend logs since cutover) |
| Database locking | none — SQLite journal `delete`, single-writer app; integrity ok at every check |
| CPU / memory | backend CPU 0.27–0.28%, mem 74.3 MiB / 7.56 GiB; frontend 0.00%, 4.9 MiB — idle-stable |
| Reverse proxy errors | only benign nginx `[warn] upstream response buffered to temp file` on unfiltered 1 MB `/api/hardware` payloads (pre-existing behavior, documented §13-3); no 4xx/5xx storm |
| Unexpected data changes | none — hardware_total stable 5444; schema v4, integrity ok, FK 0 at every check; conversations 7→8 only from the Phase 12.3 AI-honesty probe (id 8, disposable test data) |
| Health/ready/verified | `/api/health` 200 healthy; `/api/ready` tracked-version-4; verified=64 at every check |

No mandatory acceptance gate failed during stabilization; rollback was not
required.

## 12. Security posture

- Network exposure: frontend binds **only** to `100.113.157.0` (tailscale
  interface); LAN addresses (192.168.1.x) cannot reach the service.
- Auth: disabled (unchanged owner-approved posture; access restricted to
  the tailnet). `POST /auth/register` while auth off → 500 (pre-existing
  F-2, documented, no security implication: no user created is trusted, no
  data exposure, remediation deferred per owner decision 4).
- Post-cutover probes: CORS allowlist enforced (no arbitrary-origin
  reflection), CSP + nosniff present, SQLi probe parameterized (no 5xx),
  path traversal blocked (400), malformed JSON 422 structured, ops
  endpoints gated by auth flag (200 while auth off = approved posture),
  AI chat honest (message persisted 201; no fabricated AI reply).
- No new security regressions vs the M2.5 baseline.

> **[CORRECTED M3.4 note]** "access restricted to the tailnet" is necessary
> but not sufficient: the tailnet has multiple user namespaces (devices
> registered to `dapvdd@`, `mukhlisinfatah406@`, `devinevos09@`), so
> tailnet membership ≠ authorization. Addressed in M3.4 Task 2 audit
> (M34_SECURITY_REPORT.md); no live auth change made.

## 13. Residual issues

1. F-2 (register 500 while auth off) — pre-existing, documented, deferred
   to a separate controlled task per owner decision 4. Non-blocking.
   *(M3.4: fixed on `feat/m34-fortress`, Task 2; pending merge.)*
2. CPU generation / RAM speed rules remain honestly UNKNOWN (no CPU/GPU
   acquisition manifests yet — M3.2 documented residual).
3. nginx upstream buffer warn on unfiltered `/api/hardware` (1 MB payload
   buffered to temp file) — benign, pre-existing behavior; optional
   post-release tuning (`proxy_buffering`/`proxy_max_temp_file_size`).
   *(M3.4: addressed on `feat/m34-fortress`, Task 6.)*
4. Containers run as root (pre-existing, informational F-3).
   *(M3.4: addressed on `feat/m34-fortress`, Task 3.)*
5. One probe conversation (id 8 + 1 message) created during Phase 12.3
   AI-honesty verification remains in the production DB — disposable test
   data, harmless (0 users; conversations are private to its owner_id,
   which is null). Can be deleted via normal conversation DELETE if the
   owner wants a pristine count of 7.

## 14. Rollback availability

- Backup: §5 file (v3, verified restorable — restore rehearsal passed in
  Phase 3 on the identical checksum).
- Previous images intact: `spectra-backend|m25-prod-dcfd7df-s1`,
  `spectra-frontend|m25-prod-dcfd7df-s1`.
- Previous compose intact: `compose-m25.json`.
- Procedure: `docs/m3/M33_ROLLBACK_RUNBOOK.md` §2 (stop stack → restore v3
  file into volume → `compose-m25.json up` → verify tracked-version-3 +
  legacy counts). Rehearsed end-to-end with measured timings (≤60 s).
- Post-cutover writes are NOT discarded silently: the only writes after
  cutover are the probe conversation (id 8) and published catalog rows —
  the rollback procedure re-publishes catalog rows idempotently; the probe
  conversation is disposable test data.

## 15. Commit/push

Release evidence (this report + any updated docs) committed to
`release/m33-production` and pushed; no secrets included; no force-push.
