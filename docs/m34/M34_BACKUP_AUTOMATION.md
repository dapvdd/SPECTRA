# M3.4 Backup & Recovery Automation (Task 4)

**Date**: 2026-11-26
**New artifact**: `backend/app/scripts/backup_job.py` + tests (`test_backup_job.py`, 7 cases)
**Reuses**: `backup_database.py` (Online Backup API + verification), `restore_rehearsal.py` (restore + prune primitives), `alerts.py` (backup_stale/backup_missing thresholds)
**Production scheduling**: PREPARED, NOT ACTIVATED (`ops/backup/cron_backup.sh.example`) — owner approval required.

## 1. What the job does per run

1. Acquires the directory lock (`O_CREAT|O_EXCL`, timestamp payload). A fresh lock → run **skips** with `{"skipped": true, "reason": "locked"}` (never fails a run because of an overlap). A lock older than 1 h (staleness threshold) is broken.
2. Creates `spectra_backup_<UTC-timestamp>.db` via the SQLite **Online Backup API** — consistent under concurrent writes, WAL-aware (source is only ever read; the live DB is never a write target).
3. Verifies the copy: `integrity_check == ok`, `foreign_key_check` violations == 0, core-table row counts vs source (skippable under write load with `--no-compare-source`).
4. Writes `<backup>.manifest.json`: created_at (UTC), db_file, sha256, size_bytes, schema_version, integrity_check, foreign_key_violations, row_counts, source path.
5. Writes `<backup>.manifest.json.sha256` — SHA-256 **of the bytes on disk** (newline=""/no CRLF translation; verified cross-platform).
6. Updates `.last_good` (last-known-good pointer) — only after full verification passes.
7. Applies retention (keep-newest-N) that **never deletes the `.last_good` target**.
8. Releases the lock in a `finally` block — a failed run never leaves a stale-fresh lock.

## 2. Accident-protection guarantees (tested)

| Guarantee | Test |
|---|---|
| Last-good is never pruned, even when keep would demand it | `test_retention_never_deletes_last_good` (3 runs, keep=1 → both newest AND last-good survive; never 0) |
| Retention deletes only beyond keep | `test_retention_deletes_oldest_beyond_keep` |
| Concurrent run skips instead of racing | `test_lock_blocks_concurrent_run` |
| Stale lock (≥1 h) is broken automatically | `test_stale_lock_is_broken` |
| Failure releases the lock and reports the reason | `test_lock_released_after_failure` |
| Manifest is checksum-verifiable | `test_backup_creates_files_and_manifest` + `manifest_checksum_matches` |
| Refuses to produce an empty surviving set | inherited from prune guard + re-asserted in `backup_retention` |

## 3. Restore rehearsal (unchanged primitive, now wired)

`restore_rehearsal.py` remains the restore authority: copies the backup to a
**disposable** target, verifies integrity/FK/row counts there, refuses
live-looking paths. The M3.4 job chain is:

```
backup_job (create+verify+manifest)
  → restore_rehearsal --backup <newest> --target <scratch>   (rehearsal)
  → verify_backup_set --verify-dir <backup_dir>              (audit mode)
```

`verify_backup_set` (also in backup_job) re-verifies every manifest
checksum + DB integrity in a directory and confirms `.last_good` still
verifies — the acceptance gate for Task 8.

## 4. Scheduling config (prepared only)

`ops/backup/cron_backup.sh.example`: nightly 03:17 host cron →
`docker exec spectra-backend python -m backend.app.scripts.backup_job
--source /app/data/spectra.db --backup-dir /backups --keep 14`, output to
`/home/david/backups/spectra/scheduled`, log to
`/home/david/ops/spectra_backup.log`, failures via cron mail (operator's
existing channel). Release/rollback backups live in a separate directory
(`m33-release/`) that retention never touches.

## 5. Secrets and data hygiene

- No DB files, manifests with source paths beyond the operator-known path,
  or secrets are committed. The example script contains no credentials.
- Backup directories are host-local; nothing in the repo reads them.
