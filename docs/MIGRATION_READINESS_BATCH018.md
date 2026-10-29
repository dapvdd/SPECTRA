# SPECTRA Batch 018 — Production Migration Readiness Report

**Date:** 2026-10-29
**Author:** Operation SPECTRA automation
**Status:** ✅ **READY FOR EXPLICIT PRODUCTION APPROVAL** (no production writes performed)
**Scope:** GPU Ark (CC BY 4.0) enrichment — Batch 018 — production application readiness

---

## 1. Executive summary

Production is at the pre-batch018 baseline. Batch 018 (965 verified GPU records from
GPU Ark, CC BY 4.0) is **absent** from production. All **965 target records were
verified NULL in production** with **0 conflicts**, and a full rehearsal on an
**isolated, consistency-safe copy** of the production DB succeeded: exactly 965
records + 965 provenance entries applied, integrity intact, idempotent, and
rollback-proven.

**No write was performed on the production DB. The migration is rehearsed only.**
Execution awaits explicit approval.

---

## 2. Discrepancy (production vs staging)

| Item | Windows staging | DavidLab production | Delta |
|---|---|---|---|
| GPU `interface` non-null | 1,787 (95.1%) | **849 (45.2%)** | **missing 938** |
| `memory_bus_width_bits` non-null | 1,470 (78.2%) | **1,443 (76.8%)** | **missing 27** |
| `field_provenance` batch_no=18 | 965 | **0** | **missing 965** |
| source_id=4 present | yes | yes | — |
| batch_no=18 used | yes | no (used: 0,1,2,3,5,6,14) | no collision |

Production DB observed hash/size at inspection: `327c40ca…` / 51,191,808 bytes.
Re-validated at every extraction and re-confirmed unchanged throughout — the
DB retains baseline state now.

### Verified NULL-guard precondition (production, read-only)
Via embedded checker piped into `spectra-backend`:

- 938 `interface` values currently NULL (safe to fill)
- 27 `memory_bus_width_bits` values currently NULL (safe to fill)
- **0** already-populated conflicts
- `quick_check=ok`

---

## 3. Migration artifact (deterministic)

- **Payload:** `data/research/batch018_prod/` — `migrate_batch018.py` +
  `generate_selfcontained.py` produces `migrate_batch018_selfcontained.py`
  containing the 965 verified records embedded as `RECORDS`.
- **Fields:** `interface` (938) and `memory_bus_width_bits` (27).
- **Source / provenance:** source_id=4, batch_no=18, evidence_status=verified,
  confidence=medium, match_method=normalized_name + vendor_prefix_stripped,
  license=CC BY 4.0, attribution, access_date=2026-10-28, ark_id as source_reference.

### Guards (transactional, `BEGIN IMMEDIATE` … `COMMIT/ROLLBACK`)

1. **Schema precondition** — refuses to run unless `gpu_specifications.interface`
   and `.memory_bus_width_bits` exist with expected declared type, and
   `field_provenance` has all required columns. Rejects on any difference from the
   validated baseline → no schema migration ever needed. ✅
2. **Hardware existence** — each target hardware_id must exist; else abort. ✅
3. **Null-only guard** — checked before AND inside the transaction; any existing
   non-NULL value aborts the whole transaction (no partial write, no overwrite). ✅
4. **Provenance de-dup** — no (hardware_id, field, source_id=4, batch_no=18)
   provenance may already exist; abort otherwise. ✅
5. **Count enforcement** — after apply, if not exactly 965 records / 965
   provenance, marks fail. ✅
6. **Rollback** — full-file restore (see §5). ✅

---

## 4. Rehearsal results (isolated copy only)

Extraction (SQLite online backup API, consistency-safe) from
`/app/data/spectra.db` (read-only source) → `/tmp` scratch in container.

| Check | Result |
|---|---|
| Rehearsal copy source hash (prod) | `327c40ca…` — re-confirmed unchanged |
| Rehearsal copy hash | `a82529ec…`, quick_check=ok, same bytes |
| Preflight (schema/NULL/provenance) | ok — 965 targets |
| **Apply** | **965** (938 + 27) |
| Post-apply quick_check | **ok** |
| FK violations | **0** |
| Provenance added (batch18) | **965** |
| `interface` non-null after | 1787 (95.1%) — matches staging |
| `memory_bus_width_bits` non-null after | 1470 (78.2%) — matches staging |
| Distinct (hardware_id, field) pairs | 965 |
| True value/provenance mismatches | **0** (27 float-coercion artifacts verified numerically equal) |
| **Idempotency** (re-run) | **0 changes** — `already-applied-idempotent` |
| **Rollback** (restore baseline) | **exact — hash match `a82529ec…`**, quick_check=ok, batch18 prov removed |


**Rehearsal DB file paths (since cleaned from container /tmp):**
- `/tmp/spectra_rehearsal_20261029T055201.db` (pre-applied copy, cleaned)
- `/tmp/spectra_rehearsal_20261029T055721.db` (attempt-1 txn rolled back, cleaned)
- `/tmp/spectra_rehearsal_20261029T060013.db` (applied + idempotency + rollback target, cleaned)
- `/tmp/spectra_rehearsal_20261029T062052.db` (fresh baseline for rollback, cleaned)

All scratch removed post-rehearsal; nothing remains on the host. Production DB
unchanged.

---

## 5. Production backup / rollback / maintenance-window procedure

These commands run on DavidLab (via `ssh david-lab` inside the
`spectra-backend` container). Journal mode is `delete` (rollback journal) — a
raw `cp` could still race an in-flight write, so the backup uses the SQLite
online backup API which is consistency-safe and does not require stopping the
container.

### 5.1 Pre-production backup (consistency-safe)

Run the extract script (see `data/research/batch018_prod/extract_rehearsal_copy.py`)
to write the production DB to a host-visible location:
`docker exec -i spectra-backend python - < extract_rehearsal_copy.py`, then
`docker cp spectra-backend:/tmp/…db <host path>` and verify hash. This is the
**backup** that gets retained — not deleted like the rehearsal scratch.

### 5.2 Apply (after explicit approval)

`migrate_batch018_selfcontained.py` must execute against the production DB path
`/app/data/spectra.db` **with the same guards** — inside the transaction, only
NULL fields are written and only absent provenance rows are inserted, so it is
safe to run the approved migration once.

Full procedure:
1. Confirm approval (authorized by name + batch/ticket).
2. Take backup (§5.1), verify sha256 matches `327c40ca…` (unchanged prod).
3. Copy backup to a durable, off-container location (host or object storage).
4. Run the migration script against `/app/data/spectra.db --apply --verify`.
5. Immediately verify: applied=965, quick_check=ok, fk=0, provenance=965,
   interface=1787, bus_width=1470.
6. Verify app health: `curl -f http://localhost:8000/health` (no restart needed —
   backend reads the same SQLite file live; SQLite handles concurrent readers).

### 5.3 Rollback (only if verification fails or a defect surfaces)

1. Stop writes: place backend in maintenance (or, if needed, `docker stop
   spectra-backend` — only if rollback requires exclusive access).
2. Restore the backup file over `/app/data/spectra.db`.
3. `docker start spectra-backend` (if stopped).
4. Verify restored hash == backup hash; `curl -f …/health`.
5. Investigate; do not re-run migration until root cause is resolved.

### 5.4 Container-specific considerations

- **No restart is required** for the application path: SQLite file is memory-
  mapped/opened per-connection; the backend reconnects per request.
- **Journal mode:** `delete` (rollback journal), so reads coexist with the single
  writer; the migration holds `BEGIN IMMEDIATE` ensuring exclusive write lock
  during the transaction, protecting against torn/partial writes.
- **Backup safety:** file-level `cp` of a live SQLite DB is unsafe; the backup
  must use the SQLite online backup API (as rehearsed) or run during a write
  quiesce. Never `cp` the volume file while the container is writing.
- **Volume:** the DB lives in the `spectra-sqlite-data` volume mounted at
  `/app/data`. Restoring writes through that mount path.
- **Locking:** `BEGIN IMMEDIATE` acquires the reserved/exclusive lock up front;
  if the app holds an open write transaction during migration it will block —
  schedule during a low-write maintenance window summary below.

### 5.5 Suggested maintenance window

- Low-write period: e.g., 03:00–05:00 UTC Sunday.
- Pre-checks: backup + hash verification (≈1 min), migration (≈1–2 s), post-
  verify + health (≈30 s), rollback ready (snapshot retained).
- Total expected downtime: **nil** (live SQLite, no restart); worst-case if
  rollback needed and container stop required: 1–3 min.

---

## 6. Evidence summary

| Evidence | Value |
|---|---|
| Production DB hash (baseline, re-confirmed) | `327c40caf7562f398da8585de9c9e6c63a01924daab824178470a402245ae822` |
| Production DB size | 51,191,808 bytes |
| Rehearsal copy hash (pre-apply) | `a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7` |
| Applied rehearsal copy hash (post-apply) | `cc4cda2782f19b4c3b26a38ca0e2961edcd5c9376e26743438e5158353b27a01` |
| Restore (rollback) hash | `a82529ec…` (exact match) |
| Records applied | 938 interface + 27 bus_width = **965** |
| Provenance added | **965** (source_id=4, batch_no=18) |
| NULL-overwrite violations | **0** |
| Duplicate provenance | **0** |
| FK / integrity | **0 / ok** |
| Idempotent 2nd run | **0 changes** |
| Value/provenance mismatches | **0** (real); 27 float-coercion artifacts verified equal |
| Backend tests | 703 passed (2 skipped) |
| Classifier tests | 29 passed |

Rehearsal scripts: `data/research/batch018_prod/` (extraction, migration,
self-contained generator, verification, rollback proof).

---

## 7. Verdict

**READY FOR EXPLICIT PRODUCTION APPROVAL.**

Batch 018 is a pure additive backfill onto existing columns (`interface`,
`memory_bus_width_bits`) — no schema migration, no overwrite, fully rehearsed,
idempotent, and rollback-proven. No production write, container restart, or
deployment has been performed. Await explicit authorization before any
production execution.
