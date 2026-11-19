# M3 Final Delivery Report — Catalog Expansion & Data Dominance

**Date**: 2026-11-18 (remediation revision; original 2026-11-17)
**Branch**: `feat/m3-catalog-expansion` (HEAD `2031e6c`, pushed; PR #6
marked ready for review). Main untouched at `5074211`. Production
untouched at `M2.5-production` (`dcfd7df`).

## 1. Final verdict

**READY_FOR_MERGE_REVIEW** (2026-11-18, merge-gate round 2). The product
decision is recorded: **accept the small, genuinely verified pilot for M3
Core**; the 443 quarantined variants move to a future M3.1 Catalog
Acquisition milestone. The evidence contract is strengthened to three
fail-closed layers (source eligibility → identity → field verification
with source_reference + match_method), the two confirmed SKUs carry a
per-field audit manifest, and every adversarial bypass shape is pinned by
regression tests. PR #6 is marked ready for review; merge and deployment
remain separate approvals.

Basis:
- The reviewer's core finding is CONFIRMED and FIXED: the previous pilot
  stamped `identity_status='confirmed'` / `evidence_status='verified'` on
  400 generated family×spec combinations cited only to family-level vendor
  pages and Wikipedia technology articles. A valid family and a plausible
  configuration do not establish an individual SKU's existence or specs.
- Fail-closed SKU evidence gate shipped and **strengthened**: `validate_record`
  blocks any `evidence_status='verified'` claim that lacks (1) an eligible
  source (Wikipedia = technology only; family pages = family facts only),
  (2) an identity anchor (manufacturer MPN/part-number or per-SKU URL), or
  (3) a traceable field assertion (non-empty `source_reference` locator +
  `match_method` from the allowed curation vocabulary). Enforced in
  publish_batch AND mirrored in dry_run_batch; embedded `_provenance` is
  forwarded (bypass closed); the assertion is persisted into
  `field_provenance` (integrity-probe fix `f534be0`).
- Pilot rebuilt honestly in the isolated dev DB: **2 confirmed real SKUs**
  (Corsair `CMK32GX5M2B6000C30`; Seasonic FOCUS GX-750), **443 quarantined
  variants**, 8 verified + 2,744 uncertain provenance fields (all 8
  verified rows carry source_reference + match_method), 0 conflicts,
  0 fabrications (`remediation_audit` in
  `docs/m3/evidence/phase5_run_log.json`; pilot rebuilt under the
  strengthened three-layer evidence gate). The SKU-AUDIT-MANIFEST in
  `pilot_sku_verified.py` records exact MPN, manufacturer source URL,
  document revision, per-field evidence location, source value,
  normalized value, and curator decision for every verified field.
- Regression tests pin the contract: family-level citations alone cannot
  establish SKU-level verification; 'verified' requires source_reference
  (evidence locator) + allowed match_method vocabulary; dry-run mirrors
  the gate (1410 backend, 681 frontend → **1426** with Layer 3 tests).
- Safety contract held end-to-end: zero production DB writes, zero staging
  mutations, zero merges to main, zero force-push, no restricted-source
  scraping (vendor pages fetched manually, read-only, authorized).

CONDITIONS for READY_FOR_MERGE_REVIEW — RESOLVED (2026-11-18):
1. ~~Curator substantiates remaining quarantined variants~~ → resolved by
   product decision: the small verified set is accepted for M3 Core; the
   443 quarantined variants belong to M3.1 Catalog Acquisition (the
   fail-closed gate accepts exactly substantiated records whenever that
   curation happens).
2. ~~Product decision on pilot scale~~ → recorded: ship the small honest
   verified set.

## 2. What was delivered

| Layer | Delivered |
|---|---|
| Sources | Gate 0 feasibility + registry; two curated adapters (Wikipedia CC BY-SA 4.0 `clear`; manual official citations honestly `unknown`), zero network I/O (AST + behavioral pins) |
| Identity | `manufacturer\|type\|family_or_model\|variant` canonical keys; kit≠module; capacity variants; SHA-256 uniqueness suffix on 300-char truncation; duplicates → conflict candidates, never auto-merged |
| Schema | Migration v4 (dev-only): 5 nullable hardware columns, unique-partial index, `ingestion_runs` + `publication_batches`; legacy rows structurally untouched (5,389-row rehearsal: 0 backfill, 0.04 s) |
| Validation | Unit semantics (MT/s vs MHz, MB/s vs Gb/s, rated watts vs TDP), ranges, cross-field rules, fail-closed type gate, deterministic completeness-only quality score — **plus M3-remediation SKU evidence gate (strengthened): three fail-closed layers — source eligibility (Wikipedia = technology only; family pages = family facts only), identity verification (MPN or per-SKU URL), field verification (non-empty source_reference locator + allowed match_method: manual-curation | spec-table-row | manufacturer-declaration). No self-declared 'verified' status without a traceable curator assertion. Enforced in publish_batch AND mirrored in dry_run_batch.** |
| Publication | Transactional fail-closed publisher: lifecycle gate, validation gate **(now with evidence gate; mpn forwarded)**, provenance rowcount gate, wired conflict gate (intra-batch + against-published), idempotent re-import, per-batch audit rows, case-insensitive prod-path refusal; dry-run mirrors evidence gate (never overstates success) |
| API/UX | Provenance endpoint 6 categories, constant query bounds (eager loads ≤12), `/hardware` 2-query pagination, SourceTransparencyFooter with verified-only lastVerifiedOn, Neural Luxury tokens preserved, no new runtime deps |
| Ops | `/ops/ingestion-runs` + `/ops/publication-batches`: allow-listed SQL, bound params, bounded limit (422 outside 1–100), 503 fail-closed pre-v4, feature-flagged auth (401 matrix) |
| Tests | Backend 1,410 passed + 2 skipped + 2 deselected (CI-parity, incl. 14 remediation regression tests); frontend 681 passed; every functional change TDD RED→GREEN→REGRESSION |
| Pilot | **Honest pilot**: 2 SKU-verified records published (MPN + per-SKU citation each) + 443 quarantined variants retained in the seed layer for per-SKU curation; isolated dev DB; bounded batches; `remediation_audit` block in the run log |

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
| 12 | **Merge-review HOLD**: 400 generated family×spec combinations stamped `identity_status='confirmed'` / `evidence_status='verified'` on family-level citations only — no MPN, no per-SKU URL (merge review, **Critical**) | SKU evidence gate in `validate_record` (fail-closed: verified ⇒ MPN or per-SKU URL; Wikipedia = technology vocabulary only; family pages = family facts only); gate wired into `publish_batch` and mirrored in `dry_run_batch`; pilot generator stamps honest statuses (verified subset APPROVED, everything else QUARANTINED) | `0a70cf5`, `63b0c2f` |

### Merge-review remediation evidence (2026-11-18)

| Metric | Value |
|---|---|
| Confirmed real SKUs (published) | 2 — Corsair `CMK32GX5M2B6000C30` (per-SKU Tech Specs page), Seasonic FOCUS GX-750 (per-wattage spec tables + MPN anchor) |
| Unverified variants | 443 (family×tier enumeration, `evidence_status='uncertain'`) |
| Quarantined records | 443 (RAM 128, STORAGE 109, MOTHERBOARD 100, PSU 106) |
| Field-level evidence coverage | 8 verified / 2,744 uncertain / 2,752 total spec fields |
| Missing MPNs | 443 records (all quarantined entries) |
| Conflicting specifications | 0 (conflict gate: intra-batch + against-published) |
| Fabrications to preserve the 400 target | 0 (explicitly accepted smaller verified set) |
| EVGA 220-G5-0850-X1 | per-SKU URL resolves but page text is JS-rendered boilerplate (no spec values readable) → NOT claimed verified; stays quarantined |

Regression tests pinning the remediation contract:
- `backend/app/catalog/test_pilot_seed_evidence_gate.py` — pilot generator
  cannot claim 'verified' without SKU reference; family-level citations and
  Wikipedia never verify SKU fields; confirmed identity requires verified
  SKU-level evidence.
- `backend/app/importers/test_m3_validation_evidence_gate.py` —
  `validate_record` blocks Wikipedia-cited 'verified' specs and family-page
  'verified' claims without MPN; passes MPN-anchored records; 'uncertain'
  evidence adds no blocker.
- `backend/app/publishing/test_publisher.py::test_dry_run_rejects_verified_without_sku_evidence`
  — dry-run mirrors the evidence gate (never overstates success).

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
  (P10 fixes) → 1396 (P10b conflict gate) → 1410 (initial remediation) →
  **1425** (strengthened evidence gate: +15 Layer 3 adversarial tests).
  2 skipped, 2 deselected throughout.
- Frontend: 680 (P7) → **681** (lastVerifiedOn pin) passed (re-run after
  remediation: 681 passed, 0 failed).
- Rehearsal: 5,389-row prod-scale upgrade 0.04 s, legacy rows untouched;
  rollback contract = refuse non-reversible + file-restore verified
  (re-run after remediation: REHEARSAL OK, ROLLBACK CONTRACT OK).
- Pilot audit (scope 7, superseded by the merge-review remediation): the
  400/400-verified claim was WRONG (family-level citations mislabeled as
  verified). Honest rebuild: 2 confirmed SKUs, 443 quarantined, 0
  conflicts, integrity ok; idempotency re-verified under the evidence gate
  (skipped_existing == published rows; DB untouched by dry-run).
- Remediation audit: `remediation_audit` block in
  `docs/m3/evidence/phase5_run_log.json` (confirmed SKUs / unverified /
  quarantined / coverage / missing MPNs / conflicts).
- Evidence files: `docs/m3/evidence/PHASE{0_1,2_3_4,5,6,7,8,9}_EVIDENCE.md`.

## 6. Safety contract compliance (final statement)

- No production deployment; `/api/release` still `M2.5-production dcfd7df`.
- No production or staging DB writes; every write went to isolated dev
  clones / `data/dev/m3_pilot.db` / in-memory test DBs.
- No merge to main; no force-push; feature branch only (14 commits,
  including the two remediation commits `0a70cf5` + `63b0c2f`).
- No worktree deletions; `C:\Users\user\spectra-m3` intact.
- No scraping of restricted sources; adapters are pure transforms with
  structural no-network pins. Remediation vendor-page fetches were manual,
  read-only web fetches of publicly published product pages (Corsair,
  Seasonic, EVGA, G.Skill), no bulk crawling.
- M2.5-RULES-v1 byte-unchanged (blob-compared); no false-positive
  compatibility conclusions introduced.

## 7. Residual risks for the merge reviewer

See §4 "Documented, not fixed" (R1–R9). None is Critical/High; all are
fail-safe-direction or pre-existing behavior preserved deliberately.

Remediation-specific residual risks (merge-review HOLD):

1. **Pilot scale is now small by design** — 2 published SKUs vs the
   originally claimed 400. The pipeline is correct and fail-closed; the
   dataset is not. Merging this PR does not deliver a 400-record verified
   catalog; it delivers the machinery that makes such a claim verifiable.
2. **Quarantined variants need curator throughput** — 443 records remain
   quarantined until each gets an MPN + per-SKU citation + source_reference
   locator + allowed match_method. Nothing publishes without all four
   elements (fail-closed), but the curation backlog is real work.
3. **Seasonic FOCUS GX-750 citation is series-level** — the FOCUS GX page
   carries per-wattage spec tables, so the 750 W variant's values are
   directly readable, but a reviewer may rule series pages categorically
   insufficient for 'verified'. If so, this record reverts to QUARANTINED
   (one-line change in `pilot_sku_verified.py`; gate behavior unchanged).
4. **Evidence vocabulary note** — the DB CHECK constraint admits only
   `verified|uncertain|excluded|unmatched`; family/technology-tier evidence
   is stamped `uncertain` (the review prompt's "unverified" has no DB
   representation). Semantics are documented here and in the audit block.
5. **Evidence gate Layer 3 operational overhead** — every future 'verified'
   provenance entry now requires source_reference (evidence locator) +
   allowed match_method. This is a curation workflow change: curators must
   name the exact table/heading/row/field when claiming 'verified'. The gate
   is fail-closed on this requirement; any record omitting it cannot be
   published. This is intentional — it enforces auditable traceability. |

## 8. Merge-review pointers

- Start: `M3_RELEASE_READINESS.md` (inventory + rehearsal) → this file
  (verdict + dispositions) → `M3_TEST_MATRIX.md` (test contract).
- Largest diffs: `publisher.py` (gates), `migrations/runner.py` (v4 +
  guards), `m3_validation.py` (rules + type gate).
- The pilot DB (`data/dev/m3_pilot.db`) is a generated dev artifact, not
  tracked data; regenerate with `run_m3_pilot.py`.
