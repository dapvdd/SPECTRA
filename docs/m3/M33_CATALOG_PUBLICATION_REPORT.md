# M3.3 Cumulative Publication Report (Phase 5)

**Date**: 2026-11-25
**Target**: `/tmp/m33_migration_rehearsal.db` — production-derived, restored
from the verified Phase 3 backup, migrated v3→v4 in Phase 4. Inside the
`spectra-backend` container; **live production DB untouched**.
**Release branch**: `release/m33-production`

## 1. Scope

Published the four approved M3 manifests (M3.1 RAM / STORAGE / PSU, M3.2
MOTHERBOARD) into the migrated rehearsal DB through the real acquisition
pipeline (`run_acquisition`, checkpointed + idempotent), then proved
cumulative idempotency with a second full pass.

## 2. Baseline state (before publication)

| Metric | Value |
|---|---|
| hardware_total | 5380 (CPU 3501, GPU 1879) |
| verified_published | **0** (production v3 has no record_status column — see §5) |
| provenance | 39440 total / 39378 verified |
| canonical keys | 0 (column just added, all legacy NULL) |
| integrity / FK | ok / 0 |

## 3. Manifest application (first run)

| Manifest | SKUs in manifest | MATCHED | published | skipped | rejected | conflicts |
|---|---|---|---|---|---|---|
| manifest_ram.json | 128 | 32 | 32 | 0 | 0 | 0 |
| manifest_storage.json | 109 | 10 | 10 | 0 | 0 | 0 |
| manifest_psu.json | 106 | 7 | 7 | 0 | 0 | 0 |
| manifest_motherboard.json | 100 | 13 | 13 | 0 | 0 | 0 |
| **Total** | 443 | 62 | **62** | 0 | 0 | 0 |

- No rejections, no conflicts, no checkpoint discards (fresh DB, fresh
  checkpoints). 96+99+99+87 = 381 UNRESOLVED candidates **did not publish**
  (fail-closed evidence gate held).
- Provenance after publication: 39827 total / **39765 verified** (+387 new
  rows, all `verified`).

## 4. Idempotency (second full pass — published must be 0)

| Manifest | published | skipped_existing | rejected |
|---|---|---|---|
| manifest_ram.json | 0 | 32 | 0 |
| manifest_storage.json | 0 | 10 | 0 |
| manifest_psu.json | 0 | 7 | 0 |
| manifest_motherboard.json | 0 | 13 | 0 |
| **Total** | **0** | **62** | **0** |

Idempotency **PROVEN**: re-running every manifest publishes nothing,
skips exactly the already-published 62, rejects nothing.

## 5. Final verified counts (after publication)

| Metric | Value |
|---|---|
| hardware_total | 5442 (5380 legacy + 62 new) |
| verified_published_total | **62** |
| By type | MOTHERBOARD 13 · PSU 7 · RAM 32 · STORAGE 10 |
| canonical_keys_total / unique | 62 / 62 |
| provenance | 39827 / 39765 verified |
| integrity_check | ok |
| foreign_key_check | 0 violations |

Spot-checks: published rows carry real names (e.g. "Corsair Vengeance 16GB
(1x16GB) DDR5-5600 Module", "ASUS PRIME B650-PLUS") with
`record_status='PUBLISHED'`, `identity_status='confirmed'`.

## 6. Honest deviation: 62 published, not 64

The mission brief expected **64** unique verified SKUs (RAM 33, PSU 8 —
including 2 M3-core pilot rows). The production-derived database contains
**0 pilot rows**: the production schema at v3 has no `record_status` column
at all (verified directly on the backup), so the M3-core pilot publication
(2 rows, applied to dev databases during M3 development) never reached
production. This is not a pipeline failure — the manifests published every
MATCHED record they contained (32+10+7+13 = 62), and the pipeline is
idempotent.

Consequence for release: production post-cutover will show **62 verified
SKUs** (RAM 32, STORAGE 10, PSU 7, MOTHERBOARD 13), not 64. If the owner
wants the 2 pilot rows included, they can be published post-cutover via the
same evidence-gated pipeline (they are already in the RC's pilot seed
module); that is an owner decision, not a blocker — the counts are exact
and honestly reported either way.

## 7. Publisher prod-path guard preserved

The publisher's `data/spectra.db` refusal is intact (unchanged code; all
publication ran against `/tmp/m33_migration_rehearsal.db`). No evidence-gate
bypass: every published row passed the manifest MATCHED contract + publisher
verification (canonical key + APPROVED field evidence).

## 8. Command record

```bash
docker cp /tmp/m33_publish2.py spectra-backend:/tmp/publish2.py
docker exec spectra-backend python /tmp/publish2.py
# evidence: /tmp/m33_publication_evidence.json (container)
```

## 9. Residual

- The rehearsal DB now carries the exact post-cutover catalog shape: 5442
  hardware rows, 62 verified-published, provenance 39827/39765 verified.
- CPU/GPU rule pairs (R1 socket paths) still exercise at unit-test level
  only (no CPU/GPU acquisition manifests exist yet — documented in M3.2).
