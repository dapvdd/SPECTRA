# SPECTRA V3.1 — Release Candidate

Date: 2026-11-10
Operation: SPECTRA V3.1 production hardening
Branch: `feat/spectra-v3.1-production-hardening` (14 commits, baseline `origin/main` = `06e14da4c42c5a5274d9e09b769310b6a4ce3cca`)
Deployed production reference: `75eba50b1f09052f40409f6066a2ac030344d1a0` (untouched throughout)

---

## 1. Verdict

## **READY_FOR_V3.1_RELEASE_REVIEW**

All six milestones are delivered as tested code plus documentation, verified
against the real production environment read-only, with zero production
mutation. The remaining actions (auth activation, backup cron, AI key,
image rebuild) are **by-contract user-gated approvals**, not incomplete work —
each is prepared, documented, and rehearsed so the reviewer can execute them
with a single decision.

## 2. Deliverables by milestone

| Milestone | Deliverable | Key commits | Tests |
|---|---|---|---|
| M1 Auth hardening | Admin bootstrap CLI (fail-closed), security headers middleware, duplicate-decorator fix | `3441b95` | 9 bootstrap + 19 auth-security + matrix |
| M2 Deployment guardrails | `/release` identity endpoint, 8-check preflight (ops-dir + source-checkout shape), fail-closed deploy wrapper, browser release identification | `0c471e6`, `d801279`, `eb79bc8`, `b523ffe` | 25 preflight + 9 frontend + matrix |
| M3 Backup & observability | WAL-aware verified backup, restore rehearsal + retention, bounded `/metrics`, alert engine (9 alerts) | `0eee82d`, `0099dbc`, `1abc8fe`, `1c9dbb9` | 12+11+6+21 tests |
| M4 AI provider readiness | `ai_provider_state` diagnostics, 503/429/502 failure mapping, concurrency bound, `.env.example` | `4ff6b7b`, `da088b9`, `538d145` | 8 concurrency + matrix + release |
| M5 Test matrix | Cross-cutting regression matrix (CORS, headers, leakage, failure modes) | `6d303d2` | 15 matrix tests |
| M6 Documentation | This document + 8 more under `docs/v3.1/` + runbook | (this commit) | — |

## 3. Verification summary

| Check | Result |
|---|---|
| Backend pytest | **1095 passed, 2 skipped** (AI-gated), 2 deselected (Docker-cycle) — +124 vs baseline 971 |
| Frontend `node --test` | **635 passed, 0 failed** — +9 vs baseline 626 |
| Frontend production build | success |
| oxlint | 0 errors (3 pre-existing warnings, out of scope) |
| Live restore rehearsal (real 51 MB prod backup copy) | **PASS** — SHA256 `a82529ec…` match, integrity ok, 5380/3501/1879 rows |
| Live preflight on real ops dir | **8/8 PASS** |
| Live preflight on legacy checkout | **REFUSED** (5 blockers) — takeover guard proven |
| Live wrapper dry-run | **PASS**, zero mutation |
| Production state | **unchanged** (containers, DB, env, volumes, images all as baseline) |
| Secrets in changed files | none (`.env` never committed; real keys never present; `GEMINI_API_KEY` values in tests are placeholders asserted against leakage) |

## 4. Baseline & branch SHAs

| Reference | SHA |
|---|---|
| `origin/main` (baseline) | `06e14da4c42c5a5274d9e09b769310b6a4ce3cca` |
| Branch HEAD (this RC) | see `git rev-parse HEAD` at review time; push verification in §7 |
| Deployed production release | `75eba50b1f09052f40409f6066a2ac030344d1a0` |
| Production DB backup (verified) | `a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7` |

## 5. Approval-required actions (user decisions, prepared and documented)

| # | Action | Why gated | Ready-to-execute doc |
|---|---|---|---|
| 1 | **Enable auth in production** (`SPECTRA_AUTH_ENABLED=1` + `SPECTRA_AUTH_SECRET` + run `bootstrap_admin.py` in the container) | Changes prod env + DB (creates admin) | AUTHORIZATION_MATRIX.md §3; PRODUCTION_RUNBOOK.md §6 |
| 2 | **Install backup cron** on david-lab | Host crontab change | BACKUP_RECOVERY_PLAN.md §4 |
| 3 | **Configure AI provider** (`GEMINI_API_KEY`/`GEMINI_MODEL` + container recreate) | Prod env change + cost | AI_PROVIDER_READINESS.md §6 |
| 4 | **Rebuild image** to move healthcheck to `/ready` (F-09) | Deployment | PRODUCTION_RUNBOOK.md §2 |
| 5 | **Remove `:latest` images** on host (optional cleanup) | Host image store | SECURITY_FINDINGS.md F-02 |
| 6 | **Allow-list production origin** in CORS at activation (F-05) | Prod env change | AUTHORIZATION_MATRIX.md §4 |
| 7 | **Merge this branch + deploy a new release** | The operation contract forbids merging/deploying; the reviewer performs both after review | DEPLOYMENT_GUARDRAILS.md §4 |

## 6. Residual risks (accepted, documented)

- Production runs with auth disabled and no automated backups until actions
  1–2 are approved; exposure remains Tailscale-only.
- Alert transport is unwired by design (operator chooses the channel).
- AI-gated tests (2) stay skipped until action 3 supplies a real key.
- Token revocation is expiry/deletion-based (accepted threat model, F-07).

## 7. Branch state at RC

- 14 commits on `feat/spectra-v3.1-production-hardening`, working tree clean.
- Pushed to `origin` with `git push -u origin feat/spectra-v3.1-production-hardening`;
  local HEAD verified equal to remote HEAD after push (§7 of the final report).
- **Not merged to `main`; nothing deployed** — per operation contract.

## 8. Document index (`docs/v3.1/`)

| Document | Content |
|---|---|
| BASELINE_AUDIT.md | Phase 0 evidence, findings register F-01…F-10 |
| SECURITY_FINDINGS.md | Remediation status per finding + new hardening |
| AUTHORIZATION_MATRIX.md | Roles and access in both auth modes; ops authorization |
| DEPLOYMENT_GUARDRAILS.md | Preflight + wrapper usage and live verification |
| BACKUP_RECOVERY_PLAN.md | Tooling, schedule to install, recovery procedure |
| OBSERVABILITY_PLAN.md | Metrics, alert set, probe to install |
| AI_PROVIDER_READINESS.md | Provider states, failure map, activation runbook |
| TEST_MATRIX.md | Scenario→test mapping, suite totals, gaps |
| PRODUCTION_RUNBOOK.md | Health checks, alert responses, ops procedures |
| RELEASE_CANDIDATE.md | This document |
