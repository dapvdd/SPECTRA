# M3.2 Compatibility Intelligence — Delivery Report

**Date**: 2026-11-24 (final integration gate: 2026-11-25)
**Branch**: `feat/m32-compatibility-intelligence`
**Rules contract**: `M32-RULES-v2` (extends `M2.5-RULES-v1`; all seven M2.5
rules keep their semantics and gain machine-readable reason codes; two new
rules R8/R9 registered).

## 0. Final integration gate (cumulative, 4 categories)

The gate ran the full cumulative pipeline — M3 Core pilot + M3.1
(RAM/STORAGE/PSU) + M3.2 (MOTHERBOARD) — against one database
(`data/dev/m32_cumulative.db`) and verified the verified-catalog contract
and the Builder end-to-end through the real API. Gate commits: `09f30cf`
(checkpoint durability), `0eeb3d2` (content-based checkpoint fingerprint),
`efae97d` (per-manifest fingerprint keys), `fa5a549` (lifecycle fields on
API payloads — integration bug: the verified chip never rendered because
no payload carried `record_status`/`identity_status`), `fbe1022` (gate
artifacts).

### 0.1 Cumulative published counts (actual)

| Source | Published | Idempotency rerun | Quarantined (never publishable) |
|---|---|---|---|
| M3 Core pilot (approved only) | 2 (RAM 1, PSU 1) | skipped 2 | 443 |
| M3.1 manifest_ram.json (128 SKUs, 32 MATCHED) | 32 | skipped 32 | 0 (96 UNRESOLVED never published) |
| M3.1 manifest_storage.json (109 SKUs, 10 MATCHED) | 10 | skipped 10 | 0 (99 UNRESOLVED never published) |
| M3.1 manifest_psu.json (106 SKUs, 7 MATCHED) | 7 | skipped 7 | 0 (99 UNRESOLVED never published) |
| M3.2 manifest_motherboard.json (100 SKUs, 13 MATCHED) | 13 | skipped 13 | 0 (87 UNRESOLVED never published) |
| **Total** | **64** | **published 0 / skipped 64 / rejected 0** | — |

- Unique canonical keys: **64/64** (no cross-source duplicates;
  coincidentally equal to the sum 2+32+10+7+13 — verified from the DB, not
  assumed).
- By type: MOTHERBOARD 13 / PSU 8 / RAM 33 / STORAGE 10.
- Rejected 0, conflicts 0 across all runs; rerun drift: none
  (hardware_total stable at 64).
- Integrity: `integrity_check` ok, foreign_key_violations 0;
  field_provenance 396 rows (395 `verified`, 1 `uncertain` — Wikipedia
  DDR5 background row), 64/64 published rows carry verified provenance
  with per-SKU source URLs.
- Evidence: `docs/m3/evidence/m32_cumulative_rehearsal_log.json`.

### 0.2 Checkpoint durability (Task 4)

Manifest-keyed progress checkpoints were database-blind: a crash on DB A
followed by an apply against DB B silently skipped already-completed
batches. Checkpoints now carry a content fingerprint (`db_fingerprint`:
the manifest's own published canonical keys + row count; path recorded for
diagnostics only) and are validated against the live database before any
resume: fresh/different/restored DB ⇒ checkpoint discarded
(`checkpoint_discarded: true` in the summary) and all batches re-run; the
publisher's canonical-key idempotency stays the second line of defense.
Legacy checkpoint shapes are reconciled against the target DB (trusted
only when every named record still exists). Covered by 7 dedicated tests
(`test_checkpoint_durability.py`) + the 61 acquisition/checkpoint tests.

### 0.3 Verified contract through the API (18 checks)

`GET /hardware?verified=1` returns exactly the 64 eligible
(PUBLISHED+confirmed) rows — four categories present (13/8/33/10),
`X-Total-Count` accurate, facets/pagination/search/type-filters consistent,
default behavior unchanged, and every detail payload's `specifications`
equals the DB truth exactly (no fabricated or overstated fields).
Evidence: `docs/m3/evidence/m32_verified_contract_checks.json`.

The gate also found and fixed a real integration bug: the API never
carried `record_status`/`identity_status`, so the frontend verified chip
(`getVerifiedChip`) could never render on live data — unit tests had fed
the helper a payload shape the API never sends. Both lifecycle fields now
ride on every list + detail payload (additive; pinned by regression tests
on both stacks).

### 0.4 Builder end-to-end (12 checks)

Real published records through `POST /build/compatibility/check`:
R2 DDR-generation match, R3 capacity within max, R4 slots fit, R5 storage
M.2 interface, R6 PSU-only (no fabricated adequacy), R9 advisory UNKNOWN
on missing board-max data; aggregate verdict vocabulary validated; a
partial build (3 of 6 slots) never declares unconditional COMPATIBLE;
every rule result carries `reason_code` + a provenance list;
`rules_version` = `M32-RULES-v2`. Evidence:
`docs/m3/evidence/m32_builder_e2e_acceptance.json`.

### 0.5 Evidence spot-check (24 checks)

Across all 4 manifests: every MATCHED row is PUBLISHED+confirmed in the DB
with matching manufacturer; sampled SKUs carry MPN + per-SKU URL + doc
revision + APPROVED field decisions with URLs; DB normalized values equal
the manifests' `normalized_value`s (numeric-aware); **no UNRESOLVED row
appears in the published catalog** (96+99+99+87 sampled exhaustively per
category); provenance vocabulary clean. Evidence:
`docs/m3/evidence/m32_evidence_spotcheck.json`.

## 1. Scope delivered

| Task | Outcome | Commit |
|---|---|---|
| 1. Motherboard verified acquisition | 13 ASUS boards MATCHED (target 25 unreachable — all non-ASUS vendors blocked); 87 UNRESOLVED | (pre-branch, carried) |
| 2. Reason codes + R8/R9 | `RuleResult.reason_code`; R8 `cpu-motherboard-generation`, R9 `ram-motherboard-speed`; 25 new tests | `fd8779b` |
| 3. Catalog expansion revisit | 0 new SKUs; every manufacturer endpoint blocked (captcha/Akamai/403/429/JS-shell); fallback clause invoked | `e792ad2` |
| 4. Backend integration | `verified=1` on `/hardware` + `/hardware/facets`; ORM v4 columns; reason_code through API schema | `3124eae` |
| 5. Frontend integration | "Verified only" toggle; verified chip; reason-code chip in compatibility section | `e9696b2` |
| 6. Rehearsal + contract fix | Verified contract corrected to PUBLISHED; rehearsal 13 published, idempotent, integrity ok | `a4bc24c` |
| 7. Docs + draft PR | This document + PR | (this commit) |

## 2. Compatibility engine changes (M32-RULES-v2)

### 2.1 Reason codes

Every `RuleResult` now carries an optional `reason_code` (machine-readable,
stable vocabulary, `null` when a rule has no specific code). R1–R7 emit:

| Rule | reason_code examples |
|---|---|
| R1 cpu-gpu-bottleneck | `BOTTLENECK_SEVERE`, `BOTTLENECK_MODERATE`, `BOTTLENECK_NONE` |
| R2 cpu-motherboard-socket | `SOCKET_MISMATCH`, `SOCKET_UNKNOWN` |
| R3 ram-motherboard-type | `RAM_TYPE_MISMATCH`, `RAM_TYPE_UNKNOWN` |
| R4 ram-motherboard-capacity | `CAPACITY_EXCEEDED`, `CAPACITY_UNKNOWN` |
| R5 ram-motherboard-slots | `SLOTS_EXCEEDED`, `SLOT_COUNT_UNKNOWN` |
| R6 gpu-motherboard-slot | `PCIE_SLOT_MISMATCH`, `PCIE_SLOT_UNKNOWN` |
| R7 psu-build-wattage | `PSU_WATTAGE_INSUFFICIENT`, `PSU_WATTAGE_UNKNOWN`, `PSU_TDP_REFERENCE_UNAVAILABLE` |

The API schema (`RuleResultOut.reason_code`) and the frontend both pass the
code through verbatim; the client never invents one.

### 2.2 New rules

**R8 `cpu-motherboard-generation`** — socket equality never implies
generation support. With both sides' generation data documented, a
documented mismatch yields **UNKNOWN, never INCOMPATIBLE** (chipset/BIOS
support data does not exist in the schema); with any side undocumented the
rule is UNKNOWN (`GENERATION_DATA_MISSING`) or NOT_APPLICABLE.

**R9 `ram-motherboard-speed`** — a kit's rated (XMP/EXPO) speed above the
board's documented max is **advisory UNKNOWN, never INCOMPATIBLE**
(`RAM_SPEED_ABOVE_DOCUMENTED_MAX` — the kit still runs at JEDEC speeds);
absent RAM components leave the rule out of the payload (NOT_APPLICABLE).

Both rules are deterministic, explainable, carry reason codes, and follow
the M2.5 rule contract (no scoring, no invented data).

## 3. Verified catalog contract (corrected)

The verified filter is **`record_status='PUBLISHED' AND
identity_status='confirmed'`**. The publisher stamps the terminal
`PUBLISHED` lifecycle state on insertion (APPROVED → PUBLISHED);
APPROVED-but-unpublished rows never reach the public catalog. The initial
implementation used `APPROVED` and the rehearsal caught it (13 published
rows, 0 verified under the wrong filter) — fixed in Task 6 with a pinned
regression test on both sides of the stack.

`GET /hardware?verified=1` and `GET /hardware/facets?verified=1` are
additive; without the parameter, behavior is byte-identical to pre-M3.2.
Facet counts honor the active filter set; `verified` is a cross-cutting
lifecycle filter, not a facet dimension.

## 4. Rehearsal evidence (`docs/m3/evidence/m32_run_log.json`)

Flow mirrors M3.1: clone baseline schema → migrate v1..v4 → dry-run →
apply → idempotency rerun → integrity checks.

| Step | Result |
|---|---|
| schema_clone_upgrade | v0 → v4, migrations [1,2,3,4] |
| dry-run | 13 unique records; rejections are the expected unregistered-source notes (source registers on apply only — pre-existing fail-closed behavior) |
| apply | 13 published, 0 rejected, 0 quarantined |
| idempotent rerun | published 0, skipped_existing 13 → idempotent |
| integrity | `integrity_check` ok, foreign_key_violations 0 |
| rows | hardware 13 (all verified), field_provenance 117 (all `verified`) |

The rehearsal also surfaced and fixed a rehearsal-only hazard: a stale
manifest checkpoint made a resumed apply on a fresh DB report
skipped-without-rows; the rehearsal now resets the checkpoint before
cloning.

## 5. Acquisition honesty (Tasks 1 + 3)

- 13 ASUS motherboards verified end-to-end (MPN + per-SKU URL + APPROVED
  FieldEvidence per populated field); 87 candidates UNRESOLVED.
- Every other manufacturer endpoint was blocked at Task 1 and re-blocked at
  Task 3 (Crucial captcha + 404, Samsung Akamai + 404, Seagate 429,
  Kingston/Seasonic/be-quiet 403, ADATA/TeamGroup/Thermaltake/CoolerMaster
  404, Corsair/WD/G.Skill/EVGA JS-shell or Cloudflare challenge). Zero SKUs
  fabricated; the mission fallback clause (report the actual verified count)
  applies.

## 6. Test results (CI-parity, final gate)

| Suite | Result |
|---|---|
| Backend (`python -m pytest backend -q`) | 1544 passed / 2 skipped / 2 failed — the 2 are the pre-existing `test_deployment_config.py` failures, identical on unmodified `main` |
| Frontend (`node --test`) | 693 passed / 0 failed |
| Frontend build (`vite build`) | OK |
| oxlint | 4 warnings — the identical pre-existing set on `main` |
| Checkpoint + acquisition tests | 61 passed (incl. 7 durability tests) |
| Catalog + verified API tests | 40 passed (incl. lifecycle-payload regressions) |

## 7. Residual limits (stated honestly)

- R8 cannot verify CPU/board generation support: no chipset/BIOS-support
  dataset exists; documented mismatch stays UNKNOWN by design.
- R9 is advisory only: above-max rated RAM speed is UNKNOWN with an
  explanation, never INCOMPATIBLE (no QVL data).
- The cumulative verified catalog (64 rows: RAM 33 / MOTHERBOARD 13 /
  STORAGE 10 / PSU 8) contains no published CPU or GPU records from the
  acquisition manifests — the M3 Core pilot rows cover those types'
  provenance shape, but CPU/GPU rule pairs (R1 socket/bottleneck paths
  involving CPU specs) run at unit-test level only in this rehearsal.
- Verified catalog coverage reflects exactly what passed the evidence
  gate; nothing invented to fill manufacturer gaps (non-ASUS motherboard
  vendors and most storage/PSU vendors remain blocked for
  human-citation-grade extraction).
- `reason_code` is additive: legacy clients ignoring it see no change;
  clients consuming it get stable machine-readable codes.
