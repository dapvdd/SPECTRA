# SPECTRA M2.5 — Backup & Recovery (Phase C)

**Executed:** 2026-11-15T14:38:18Z (backup), restore rehearsal 2026-11-16
**Rule honored:** a backup file alone is not sufficient — restoration was performed and verified.

## 1. Source state

| Item | Value |
|---|---|
| Production DB | `/app/data/spectra.db` in `spectra-backend` (volume `spectra-sqlite-data`) |
| Size | 51,191,808 bytes, no WAL/SHM sidecars (`journal_mode=delete`) |
| Pre-backup integrity | `ok`, FK check empty, schema_version 2 |

## 2. Backup method (consistent online backup)

The SQLite **backup API** (`sqlite3.Connection.backup()`) was executed **inside the production backend container** (the only process able to read the root-owned volume). The backup API copies page-by-page under the database's locking protocol, so the copy is consistent even if writes occur mid-copy — no production stop, no lock beyond the copy window, `journal_mode=delete` handled correctly.

Command pattern (executed via `docker cp` + `docker exec`):

```python
con = sqlite3.connect("/app/data/spectra.db")
dst = sqlite3.connect("/app/data/backup-<ts>.db")
con.backup(dst)   # consistent online copy
```

The temporary in-container copy was removed after transferring out (`/app/data` again contains only `spectra.db` — verified).

## 3. Backup artifact

| Item | Value |
|---|---|
| File | `/home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-20261115T143818Z.db` |
| Size | 51,191,808 bytes (identical to source) |
| SHA-256 | `801dd666acd8dfac0bf01ebec2f7b6537562048e1b22ad3d0b67e9bf921fdf56` |
| Permissions | `-rw------- david david` (0600); directory `/home/david/backups/spectra/m2-5-cutover-prep` |
| Location | Outside the container filesystem and the release dirs; survives container replacement |

## 4. Backup verification (on the copy, read-only)

| Check | Result |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `[]` (no violations) |
| `schema_version` | `(1, 2, 2026-11-09T16:35:05Z)` — v2 |
| Row counts | hardware 5,380 (CPU 3,501 / GPU 1,879) · users 0 · build_conversations 7 · build_messages 10 · sources 10 · field_provenance 39,440 · external_identifiers 3,575 · benchmark_results 1,040 — **identical to live prod** |
| Post-backup prod state | `integrity_check: ok`, `journal_mode: delete` — production untouched |

## 5. Restore rehearsal

| Step | Result |
|---|---|
| Restore target | `/home/david/releases/spectra-m25-staging/rehearsal/rehearsal-restore.db` (disposable) |
| Copy time | 0.06 s |
| SHA-256 after restore | `801dd666…` — byte-identical |
| Integrity on restored copy | `ok`, FK `[]`, counts identical |

The restore path (backup file → disposable location → open and verify) is proven end-to-end.

## 6. Data preserved by this backup

Hardware catalog (5,380 rows + spec tables), field provenance, external identifiers, benchmark results, sources, users (0), build conversations (7) and messages (10) — i.e. the complete application-owned persistent state at backup time.

## 7. Retention & recovery procedure

- **Retention:** keep the pre-cutover backup indefinitely alongside the existing Nov-9 backup (`/home/david/releases/spectra-75eba50-ops/backup-20261109T162847Z.db`, SHA `a82529ec…`, unchanged). At cutover (separately authorized), take a **fresh** backup after the write freeze and retain it as the rollback point (see Cutover Runbook step 3).
- **Recovery procedure (documented, not executed against prod):**
  1. Freeze writes (stop prod containers) — see Rollback Runbook.
  2. Copy the chosen backup into the volume: `docker cp <backup>.db spectra-backend:/app/data/spectra.db` (container stopped → use `docker cp` to a `docker create` container or stop first; exact commands in the Rollback Runbook).
  3. Recreate containers, verify `PRAGMA integrity_check`, `/api/ready`, and row counts before reopening.
- **No secrets or personal data** appear in the backup filename, logs, or evidence: the DB contains 0 users; filenames carry timestamps only.
