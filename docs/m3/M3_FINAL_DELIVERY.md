# M3 Final Delivery Report — Catalog Expansion & Data Dominance

**Date**: 2026-11-17
**Branch**: `feat/m3-catalog-expansion` (HEAD `006e8fa`, pushed; draft PR
target). Main untouched at `5074211`. Production untouched at
`M2.5-production` (`dcfd7df`).

## 1. Final verdict

**READY_FOR_MERGE_REVIEW** — with the residual-risk register in §7 carried
into the PR description.

Basis:
- All 14 mission deliverables complete (`M3_RELEASE_READINESS.md` §1).
- Pilot dataset verified by independent audit: 400/400 records
  (100/category), 2,500/2,500 provenance rows, 0 duplicate canonical keys,
  0 FK violations, idempotent re-import.
- All independent-review Critical/High findings fixed with TDD evidence;
  full regression green at every step.
- Safety contract held end-to-end: zero production DB writes, zero staging
  mutations, zero merges to main, zero force-push, no restricted-source
  scraping at any point.

## 2. What was delivered

| Layer | Delivered |
|---|---|
| Sources | Gate 0 feasibility + registry; two curated adapters (Wikipedia CC BY-SA 4.0 `clear`; manual official citations honestly `unknown`), zero network I/O (AST + behavioral pins) |
| Identity | `manufacturer\|type\|family_or_model\|variant` canonical keys; kit≠module; capacity variants; SHA-256 uniqueness suffix on 300-char truncation; duplicates → conflict candidates, never auto-merged |
| Schema | Migration v4 (dev-only): 5 nullable hardware columns, unique-partial index, `ingestion_runs` + `publication_batches`; legacy rows structurally untouched (5,389-row rehearsal: 0 backfill, 0.04 s) |
| Validation | Unit semantics (MT/s vs MHz, MB/s vs Gb/s, rated watts vs TDP), ranges, cross-field rules, fail-closed type gate (malformed values = blockers, never crashes), deterministic completeness-only quality score |
| Publication | Transactional fail-closed publisher: lifecycle gate, validation gate, provenance rowcount gate (unregistered source aborts batch), wired conflict gate (intra-batch + against-published), idempotent re-import, per-batch audit rows, case-insensitive prod-path refusal |
| API/UX | Provenance endpoint 6 categories, constant query bounds (eager loads ≤12), `/hardware` 2-query pagination, SourceTransparencyFooter with verified-only lastVerifiedOn, Neural Luxury tokens preserved, no new runtime deps |
| Ops | `/ops/ingestion-runs` + `/ops/publication-batches`: allow-listed SQL, bound params, bounded limit (422 outside 1–100), 503 fail-closed pre-v4, feature-flagged auth (401 matrix) |
| Tests | Backend 1,396 passed + 2 skipped + 2 deselected (CI-parity); frontend 681 passed; every functional change TDD RED→GREEN→REGRESSION |
| Pilot | 400 real, human-verified records (RAM/Storage/Motherboard/PSU ×100) in isolated dev DB, published through bounded batches 10→25→50→100 |

## 3. Independent review outcomes (7 scopes)

| Scope | Verdict | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| 1. Identity + migration v4 | CONCERNS | 0 | 2 | 2 | 2 |
| 2. Ingestion pipeline | CONCERNS | 0 | 0* | 2* | 4 |
| 3. Publication lifecycle | CONCERNS | 1 | 1 | 2 | 4 |
| 4. Compatibility impact | PASS | 0 | 0 | 1 | 3 |
| 5. Provenance API + UX | CONCERNS | 0 | 0 | 1 | 2 |
| 6. Ops visibility + security | PASS | 0 | 0 | 0 | 3 |
| 7. Pilot data audit | PASS | 0 | 0 | 0 | 0 |

\* counted Medium in scope 2's report; the unwired conflict gate was
escalated to High in disposition (mission §6 makes the gate mandatory).

## 4. Finding dispositions

### Fixed (TDD RED→GREEN, regression green)

| # | Finding (scope, severity) | Fix | Commit |
|---|---|---|---|
| 1 | Provenance `INSERT..SELECT` silently matched 0 rows for unregistered source → spec values published with NO provenance (3, **Critical**) | rowcount gate: `rowcount != 1` aborts batch naming the source; transaction rolls back clean | `d02ba42` |
| 2 | Prod-path refusal case-sensitive — `DATA/SPECTRA.DB` opens production on case-insensitive filesystems (3, High) | `_is_prod_path`: casefold + separator normalization | `d02ba42` |
| 3 | Migration CLI defaulted `--database` to `data/spectra.db` with no refusal (1, High) | `_ensure_not_prod_path` on `upgrade()`/`downgrade()` | `d02ba42` |
| 4 | v4 `reversible=False` not honored — partial downgrade dropped ops tables, left 5 columns, bricked re-upgrade (1, High) | `downgrade()` honors `reversible`; refuses with file-restore pointer; new refusal test | `d02ba42` |
| 5 | `detect_conflicts` keyed values by source_name — same-source conflicts silently missed (2, Medium) | values keyed positionally (`source#idx`) | `d02ba42` |
| 6 | canonical_key 300-char truncation could cut the variant → silent SKU merge (1, Medium) | truncation appends 16-hex SHA-256 suffix (collision ≈2⁻⁶⁴) | `d02ba42` |
| 7 | Conflict gate never wired into `publish_batch` (`conflict_free=True` hardcoded) (2, **High** on disposition) | `_apply_conflict_gate` wired: intra-batch conflicts reject ALL involved; against-published differing re-import rejects incoming instead of skipping; idempotent identical re-import preserved (pilot probe: 400 skipped, 0 rejected) | `006e8fa` |
| 8 | Dry-run overstated success: counted provenance without consulting the sources registry (3, Low #7) | `_unregistered_sources` check mirrors apply-time rejection | `006e8fa` |
| 9 | `lastVerifiedOn` took max access_date over ALL records — uncertain record's date displayed as "Last verified" (5, Medium) | filter `evidenceStatus === "verified"`; +1 test | `055d127` |
| 10 | Malformed spec values crashed `unit_checks`/`cross_field_checks` with TypeError — batch died with opaque traceback (Phase 9 self-review) | `_type_check_failure` gate: real int/float only (bool excluded), malformed → named blockers | `e3533a0` |
| 11 | `quality_score` dead first computation, ambiguous precedence (2/4, Low) | removed; behavior identical | `d02ba42` |

### Documented, not fixed (residual — §7)

| # | Finding (scope, severity) | Disposition |
|---|---|---|
| R1 | Stuck-'running' `ingestion_runs` rows after SIGKILL; no sweeper (3, Medium) | Dev-only visibility; runs are auditable and manually correctable; a sweeper is a follow-up, not a blocker — no data integrity impact |
| R2 | Concurrent `batch_no` collision → whole batch rolls back (3, Low) | Safe direction (fail-closed); publication is single-operator in current workflow |
| R3 | Spec-column f-string interpolation in `_insert_record` (3, Medium) | Fail-closed anyway (unknown column aborts batch); caller is the internal pipeline, not user input |
| R4 | `q` LIKE wildcards (`%`/`_`) (pre-existing 1.3) | Search-only impact, no data exposure; byte-identical default behavior preserved by mission contract |
| R5 | `sourceUrl` href rendered directly (pre-existing; React 19 blocks `javascript:`) | Out of M3 scope; noted for merge reviewer |
| R6 | `_verify_v4` checks index name only, not UNIQUE/partial-ness (1, Medium) | Correct index is created by v4's own DDL; verification hardening is follow-up |
| R7 | `|` not escaped in canonical components (1, Low) | Boundary ambiguity only creates *extra* conflict candidates (fail-safe direction); escaping would change existing keys |
| R8 | `run_m3_pilot.py` `if False] or _fk_check_pilot` (2, Low) | Documented dev-harness trade-off; rehearsal probes use `PRAGMA foreign_key_check` |
| R9 | No wall-clock latency assertions (by design) | Deterministic query-count bounds are the enforceable contract |

## 5. Test & evidence trail

- Backend (CI-parity): 1342 → 1356 (P7) → 1362 (P8) → 1380 (P9) → 1392
  (P10 fixes) → **1396** (P10b conflict gate) passed; 2 skipped, 2
  deselected throughout.
- Frontend: 680 (P7) → **681** (lastVerifiedOn pin) passed.
- Rehearsal: 5,389-row prod-scale upgrade 0.04 s, legacy rows untouched;
  rollback contract = refuse non-reversible + file-restore verified.
- Pilot audit (scope 7): 400/400 PUBLISHED + identity confirmed; 2,500
  provenance exact (RAM 600, STORAGE 500, MOTHERBOARD 900, PSU 500); 0
  duplicate keys; report↔DB numbers match; idempotency re-verified under
  the wired gate (read-only probe).
- Evidence files: `docs/m3/evidence/PHASE{0_1,2_3_4,5,6,7,8,9}_EVIDENCE.md`.

## 6. Safety contract compliance (final statement)

- No production deployment; `/api/release` still `M2.5-production dcfd7df`.
- No production or staging DB writes; every write went to isolated dev
  clones / `data/dev/m3_pilot.db` / in-memory test DBs.
- No merge to main; no force-push; feature branch only (12 commits).
- No worktree deletions; `C:\Users\user\spectra-m3` intact.
- No scraping of restricted sources; adapters are pure transforms with
  structural no-network pins.
- M2.5-RULES-v1 byte-unchanged (blob-compared); no false-positive
  compatibility conclusions introduced.

## 7. Residual risks for the merge reviewer

See §4 "Documented, not fixed" (R1–R9). None is Critical/High; all are
fail-safe-direction or pre-existing behavior preserved deliberately.

## 8. Merge-review pointers

- Start: `M3_RELEASE_READINESS.md` (inventory + rehearsal) → this file
  (verdict + dispositions) → `M3_TEST_MATRIX.md` (test contract).
- Largest diffs: `publisher.py` (gates), `migrations/runner.py` (v4 +
  guards), `m3_validation.py` (rules + type gate).
- The pilot DB (`data/dev/m3_pilot.db`) is a generated dev artifact, not
  tracked data; regenerate with `run_m3_pilot.py`.
