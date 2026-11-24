# M3.2 Compatibility Intelligence — Delivery Report

**Date**: 2026-11-24
**Branch**: `feat/m32-compatibility-intelligence`
**Rules contract**: `M32-RULES-v2` (extends `M2.5-RULES-v1`; all seven M2.5
rules keep their semantics and gain machine-readable reason codes; two new
rules R8/R9 registered).

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

## 6. Test results (CI-parity)

| Suite | Result |
|---|---|
| Backend (`python -m pytest backend/app -q`) | 1530 passed / 2 skipped / 2 failed — the 2 are the pre-existing `test_deployment_config.py` failures, identical on unmodified `main` |
| Frontend (`node --test src/*.test.js`) | 693 passed (baseline 681 + net new) |
| Frontend build (`vite build`) | OK |
| oxlint | 4 warnings — the identical pre-existing set on `main` |

## 7. Residual limits (stated honestly)

- R8 cannot verify CPU/board generation support: no chipset/BIOS-support
  dataset exists; documented mismatch stays UNKNOWN by design.
- R9 is advisory only: above-max rated RAM speed is UNKNOWN with an
  explanation, never INCOMPATIBLE (no QVL data).
- Verified catalog coverage = 13 motherboards (ASUS only). The "Verified
  only" toggle is honest about this: with it on, the catalog shows exactly
  the rehearsal-verified set, nothing invented to fill gaps.
- `reason_code` is additive: legacy clients ignoring it see no change;
  clients consuming it get stable machine-readable codes.
