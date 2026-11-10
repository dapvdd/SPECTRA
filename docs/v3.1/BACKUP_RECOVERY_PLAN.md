# SPECTRA V3.1 — Backup & Recovery Plan

Date: 2026-11-10
Scope: SQLite database backup, verification, retention, restore rehearsal, and
the human procedure for recovering production. Built in M3; live-verified
against the real david-lab backup on 2026-11-10.

---

## 1. Current state (observed baseline)

| Item | State |
|---|---|
| Live DB | `/app/data/spectra.db` inside `spectra-backend` (volume `spectra-sqlite-data`), 51,191,808 bytes, integrity ok, migration v2 |
| Backups on host | Release-day artefacts in `/home/david/releases/spectra-75eba50-ops/` and one in `/home/david/projects/spectra/backups/` |
| Scheduled backups | **None** (F-04, P1) — the data-loss window is "since the last manual backup" |
| Host cron | Only the DavidLab cloud-storage job, which does not cover SPECTRA backups |

## 2. Tooling delivered (on the V3.1 branch)

| Tool | Command | What it does |
|---|---|---|
| Backup | `python -m backend.app.scripts.backup_database --source <db> --output <file>` | **WAL-aware** consistent copy (stops the torn-backup class of failure), then verifies SHA256, `integrity_check`, `foreign_key_check`, and row counts; refuses to leave an unverified backup behind |
| Retention | `python -m backend.app.scripts.restore_rehearsal --prune <dir> --keep 7` | Keeps the newest 7 `backup*.db` files; only ever deletes matching names; refuses when the surviving set would be empty |
| Rehearsal | `python -m backend.app.scripts.restore_rehearsal --backup <file> --target <scratch>` | Copies the backup to a **disposable** target and verifies it there (SHA match, integrity, FK, plausible row counts); refuses live-looking targets (`/app/data/spectra.db`) |

All three are pure-python (stdlib only) and host-runnable — verified on
david-lab where only `python3` exists (no sqlalchemy needed).

## 3. Live verification evidence (2026-11-10)

```text
backup:    /tmp/v31-rehearsal-source.db  (copy of backup-20261109T162847Z.db)
restored:  /tmp/v31-restore-target.db    (disposable)
sha256:    a82529ec0f74cd7b98eb484ffc6ce34151661eee99c1f03de42134552550fba7  (match)
integrity: ok      foreign_key_check: ok
rows:      hardware 5380, cpu_specifications 3501, gpu_specifications 1879,
           benchmark_results 1040, sources 9, build_conversations 6,
           build_messages 10
verdict:   restore_rehearsal_passed
```

No production state was modified; the live DB was never written.

## 4. The schedule to install (USER-GATED — not installed by this operation)

The tooling is ready; the missing piece is a host cron entry. Recommended
(approves required from the user before installation):

```cron
# Nightly verified backup at 03:10 (before the 03:30 cloud-storage job),
# keeping 7, plus a weekly restore rehearsal.
10 3 * * *  cd /home/david/releases/spectra-75eba50-ops && /usr/bin/python3 /home/david/releases/spectra-75eba50/backend/app/scripts/backup_database.py --source /tmp/spectra-live-copy.db --output /home/david/backups/spectra/backup-$(date +\%Y\%m\%dT\%H\%M\%SZ).db >> /home/david/backups/spectra/backup.log 2>&1
```

Two host-side realities this must respect (documented, not executed):
1. The live DB lives **inside the container** — the backup step first needs a
   consistent read-only copy out of the container (the release-day
   `docker exec … sqlite3 backup` pattern in `prepare.py` is the proven
   approach), or the container-internal module once the V3.1 image ships the
   scripts.
2. Retention + rehearsal should run after each backup; `--keep 7` bounds disk
   usage at ~350 MB.

Until the cron is installed, the **manual fallback** below is the recovery
posture — treat "time since last backup" as the data-loss window.

## 5. Recovery procedure (human-run, in order)

1. **Freeze writes** — stop traffic to the backend (e.g. `docker stop
   spectra-frontend` or a compose-level pause) so the failing DB is not
   written further.
2. **Capture the failing state** — `docker cp spectra-backend:/app/data/spectra.db
   /tmp/evidence-<ts>.db` (for post-mortem; never restore over it in place).
3. **Pick the backup** — newest verified `backup*.db`; confirm its
   `backup-evidence.json` SHA256.
4. **Rehearse first (mandatory)** —
   `python3 -m backend.app.scripts.restore_rehearsal --backup <file> --target /tmp/rehearsal.db`
   must print `restore_rehearsal_passed`. Never restore a backup that has not
   passed a rehearsal.
5. **Restore into the container** — `docker cp /tmp/rehearsal.db
   spectra-backend:/app/data/spectra.db` then `docker restart spectra-backend`.
   (This is the single mutation step; it replaces the live DB — user-gated,
   never automated.)
6. **Verify** — `/api/ready` → `database: reachable`, `migrations:
   tracked-version-2`; spot-check row counts against the rehearsal output;
   run one catalog query and one conversation read.
7. **Post-mortem** — only after service is verified, analyze the evidence copy
   for the corruption cause; file findings back into the runbook.

## 6. What recovery does NOT cover

- **Host loss** — backups live on the same host as the DB. The DavidLab
  cloud-storage job covers `/home/david`, but verify it actually includes the
  backup directory before relying on it for host-loss recovery.
- **Point-in-time recovery** — WAL-aware copies are crash-consistent
  snapshots, not continuous PITR. Worst case loses everything since the last
  backup.
- **Secrets** — `.env` is not in backups by design; keep the runtime secret
  store separate (and out of git, verified).
