# SPECTRA M2.5 — Migration Rehearsal v2 → v3 (Phase D)

**Executed:** 2026-11-16 · **Environment:** disposable copies on DavidLab host, never production
**Source backup:** `spectra-prod-v2-20261115T143818Z.db` (SHA-256 `801dd666…`, verified)

## 1. Tooling

| Item | Value |
|---|---|
| Runner | `backend/app/migrations/runner.py` at `dcfd7df` (versioned, additive-only, copy-first) |
| Runtime | Host Python 3.13.5, SQLite 3.46.1 (container runs 3.13.x image — same SQLite family) |
| Env vars required | **None** (runner is standalone; `--database` flag selects the copy) |
| Design | Each migration runs inside `BEGIN…commit` with `PRAGMA foreign_keys=ON`; verify-function failure or any exception → `conn.rollback()`; `schema_version` table records the applied version; steps ≤ current version are no-ops (idempotent) |

## 2. Exact commands (as executed, from `/home/david/releases/spectra-m25-staging/src`)

```bash
# status report
python3 backend/app/migrations/runner.py --report  --database ../rehearsal/rehearsal-restore.db
# dry run (no changes)
python3 backend/app/migrations/runner.py --dry-run --database ../rehearsal/rehearsal-restore.db
# apply (v2 -> v3)
python3 backend/app/migrations/runner.py          --database ../rehearsal/rehearsal-restore.db
# verify
python3 backend/app/migrations/runner.py --verify  --database ../rehearsal/rehearsal-restore.db
# downgrade rehearsal
python3 backend/app/migrations/runner.py --target 2 --database ../rehearsal/rehearsal-restore.db
```

## 3. What migration v3 does

`planner-component-categories` (version 3):
- Creates `ram_specifications`, `storage_specifications`, `motherboard_specifications`, `psu_specifications` (each FK→`hardware.id`, unique; typed CHECKs, e.g. DDR-generation enum).
- **Rebuilds `field_provenance`** (SQLite cannot ALTER a CHECK) with a widened `table_name` CHECK so the new categories carry provenance: create `_new` → copy all rows → drop old → rename → recreate indexes; row preservation verified inside the migration.
- All statements additive/idempotent (`IF NOT EXISTS`), so an interrupted run can be re-run.

## 4. Measured results

| Metric | Measured |
|---|---|
| `--report` | current v2 (`auth-tables`), 1 pending (v3) |
| `--dry-run` | no changes (`to_version: 2, applied: []`), 0.11 s |
| **Apply v2→v3** | **4.14 s** wall (user 1.48 s) — later fresh-copy runs 5.1–6.6 s incl. copy |
| Size change | 51,191,808 → 56,430,592 bytes (**+5.2 MB, ≈ +10%**) |
| Post integrity | `integrity_check: ok` · `foreign_key_check: []` |
| Schema version | 3, `--verify` → `verified` |
| Row reconciliation | hardware **5,380** =, CPU 3,501 =, GPU 1,879 =, provenance **39,440 preserved**, ext-ids 3,575 =, benchmarks 1,040 =, sources 10 =, users 0 =, conversations 7 = (owner_id NULL), messages 10 =; new spec tables present with 0 rows |
| Relationship checks | 0 orphan provenance / ext-id / cpu-spec rows; provenance `table_name` distribution unchanged |

## 5. Application startup against the migrated copy

M2.5 backend (rehearsal venv, uvicorn on 127.0.0.1:8765, `SPECTRA_DATABASE_URL=sqlite:////…/app-rehearsal.db`, no secrets):

| Check | Result |
|---|---|
| Startup to ready | `/ready` 200 `{"status":"ready","database":"reachable","migrations":"tracked-version-3"}` (ready poll < 3 s) |
| Catalog API | `/hardware?limit=1` 200; `/hardware/facets` 200 with CPU 3,501 / GPU 1,879 |
| Compatibility API | `/build/compatibility/check` verified live against fixtures: socket rule COMPATIBLE/INCOMPATIBLE, PSU two-tier semantics (450 W vs 293 W floor → UNKNOWN at/above floor, INCOMPATIBLE below), `rules_version: M2.5-RULES-v1`, type-mismatch 422, bogus id 404 |
| Conversation persistence | `POST /build/conversations` 200 (created id 8: cpu 1 + gpu 3361), `GET /build/conversations/8` 200 — write+read on the migrated copy works |

## 6. Idempotency / repeated-migration behavior

- Re-run after v3: `status: up-to-date, applied: []` (0.11 s) — safe.
- `--verify`: `verified` v3.
- Expected rejection: none needed; runner no-ops rather than rejects.

## 7. Downgrade rehearsal (reversibility)

- `--target 2` → `downgraded` in **3.46 s**; drops the four spec tables, version back to 2; data tables untouched.
- Re-upgrade after downgrade → v3 again with identical counts (hw 5,380, provenance 39,440).

## 8. Failure/recovery simulation

A deliberately corrupted migration v3 (statement referencing a nonexistent parent table) was injected on a disposable copy at v2:

- Python sqlite3 enforces FK **immediately** inside the explicit transaction (verified with a micro-test) → the bad statement raises `IntegrityError` during `conn.execute`.
- Runner catches `BaseException` → `conn.rollback()` → **DB left at v2**, `integrity_check: ok`, hardware 5,380, no spec tables, version unrecorded.
- Recovery = remove the fault (or change nothing) and re-run; idempotent statements make re-application safe.

**Residual risk (disclosed):** a hard crash between individual DDL statements inside the transaction would be rolled back by SQLite itself (transactional DDL); a crash *after* commit but before the wrapper finishes is harmless (version already recorded). No partial-state path was found.

## 9. Downtime estimate (measured, not extrapolated)

| Phase | Measured |
|---|---|
| Migration on prod-sized DB | ~4–7 s |
| Backend container start to healthy | ~2.4 s (uvicorn ready poll) + compose `start_period 5 s` |
| Compose replace (two services, shared volume untouched) | ~5–10 s (from V3 precedent + staging recreate) |
| **Total planned cutover window** | **≈ 30–60 s** including health checks and smoke — far below the prior V3 migration window (which also stopped containers) |

Rehearsal artifacts: `rehearsal/*.db`, `rehearsal/uvicorn*.log`, and phase outputs under `docs/release/evidence/m2-5-production-readiness/`.
