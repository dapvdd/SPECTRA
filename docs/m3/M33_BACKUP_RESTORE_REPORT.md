# M3.3 Backup & Restore Report (Phase 3)

**Date**: 2026-11-25
**Host**: david-lab (Debian 13) — production compose project `spectra`
**Release branch**: `release/m33-production`

## 1. Backup design

Production runs a single SQLite file (`/app/data/spectra.db`, docker volume
`spectra-sqlite-data`, journal_mode=delete, no WAL) with live API traffic.
**A blind file copy of a live SQLite DB is not safe** (torn reads across the
main file + journal). The procedure therefore uses the **SQLite Online
Backup API** (`sqlite3.Connection.backup()`), which produces a consistent,
transactionally coherent snapshot regardless of concurrent readers/writers
and journal state.

Scope captured:

- Database (full, consistent): `m33_backup_<UTCSTAMP>.db`
- Deployment configuration: `/home/david/releases/spectra-75eba50-ops/compose-m25.json`
  (copy referenced in rollback runbook; contains no secrets — GEMINI keys are
  empty strings in the prod compose)
- Current image identifiers: `spectra-backend:m25-prod-dcfd7df-s1`,
  `spectra-frontend:m25-prod-dcfd7df-s1` (recorded in baseline doc)
- Current Git SHA: production `dcfd7df…`, release candidate `5c2c7d9…`
- Rollback metadata: this report + `M33_ROLLBACK_RUNBOOK.md`

Secrets: none included. The backup contains **catalog data only** — `users`
table is empty (0 rows) in production; no credentials, API keys, or tokens
exist in the DB file (verified: table list + row counts below).

## 2. Backup executed (2026-11-25T06:25:46Z)

| Item | Value |
|---|---|
| Method | `sqlite3.Connection.backup()` inside `spectra-backend` container |
| Source | `/app/data/spectra.db` (opened read-only URI mode) |
| Staging | `/tmp/m33_backup_20261125T062546Z.db` (container) |
| Persisted to host | `/home/david/backups/spectra/m33-release/m33_backup_20261125T062546Z.db` |
| Size | 56,430,592 bytes |
| SHA-256 | `d4d19d55f8dcb58b1629b662139c93400505e91849cd1871a54c55ac8d006d2c` |
| integrity_check | ok |
| foreign_key_check | 0 violations |
| Schema version | 3 (tracked; applied 2026-11-16T07:31:47Z) |

Snapshot consistency: live counts captured during the same window match the
backup exactly (hardware 5380, benchmarks 1040, conversations 7, sources 10).

## 3. Full table counts in backup

benchmark_results 1040 · build_conversations 7 · build_messages 10 ·
cpu_specifications 3501 · external_identifiers 3575 · field_provenance 39440 ·
gpu_specifications 1879 · hardware 5380 · motherboard_specifications 0 ·
psu_specifications 0 · ram_specifications 0 · sources 10 ·
storage_specifications 0 · users 0 · schema_version 1.

CPU/GPU catalog spot-checks (restored copy): id 1 "AMD Athlon Gold 7220C"
(CPU, AMD), id 3362 "i810 Graphics" (GPU, Intel); benchmarks: Geekbench 7
rows with scores 695.0 / 2005.0; conversations reference live hardware ids
(900/5222, 10/5215).

## 4. Restore rehearsal (the backup is valid only if restoration succeeds)

Restored the backup **inside the production container but on a temp path**
(`/tmp/m33_backup_20261125T062546Z.db` — never touching the live DB), then:

1. Opened read-only: `integrity_check` ok, 0 FK violations, all table counts
   match §3, schema_version 3.
2. **Restored application startup**: booted the real FastAPI app
   (`backend.app.main:app`) against the restored copy
   (`SPECTRA_DATABASE_URL=sqlite:////tmp/m33_backup…db`) and exercised the
   actual request path:
   - `GET /health` → 200 `{"status":"healthy"}`
   - `GET /hardware?limit=2` → 200, `X-Total-Count: 5380`, first row
     "AMD Athlon Gold 7220C" (identical to live production response)
3. Evidence: `m33_restore_evidence.json` (inside container `/tmp`, mirrored
   in the release evidence bundle).

**Verdict: backup VALID** — restoration succeeds, the restored DB passes
integrity/FK checks, preserves the full CPU/GPU catalog + benchmarks +
conversations, and serves real application traffic.

## 5. Command record (exact, adapted to this host)

```bash
# 1. Consistent backup (inside container; SQLite Online Backup API)
docker cp /tmp/m33_backup.py spectra-backend:/tmp/backup.py
docker exec spectra-backend python /tmp/backup.py
# 2. Persist out of the container to host backup dir
docker cp spectra-backend:/tmp/m33_backup_20261125T062546Z.db /tmp/
mkdir -p /home/david/backups/spectra/m33-release
cp /tmp/m33_backup_20261125T062546Z.db /home/david/backups/spectra/m33-release/
cp /tmp/m33_backup_evidence.json /home/david/backups/spectra/m33-release/
sha256sum /home/david/backups/spectra/m33-release/m33_backup_20261125T062546Z.db
# 3. Restore rehearsal (temp path inside container; live DB untouched)
docker cp /tmp/m33_restore.py spectra-backend:/tmp/restore.py
docker exec spectra-backend python /tmp/restore.py
```

## 6. Notes & honest limits

- The backup is a **v3 schema** snapshot (production has not yet received
  migration v4). Phase 4 rehearses the v3→v4 upgrade on a restored clone.
- `field_provenance` 39,440 rows are the M2-era benchmark provenance; they are
  preserved through the v3 provenance rebuild in migration v3? — N/A here:
  production is already at v3, so the rehearsal path is v3→v4 only (purely
  additive).
- Restored-app startup was exercised **in-process** (TestClient against the
  app factory in the container) rather than a second container bind-mounting
  the restored file. Phase 6 (isolated release deployment) covers full
  container startup against a restored copy, closing that gap.
- Backup cadence recommendation (documented, not implemented here): take a
  fresh online backup immediately before any schema-mutating release step,
  plus a pre-cutover backup in Phase 12.
