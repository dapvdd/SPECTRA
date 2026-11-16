# SPECTRA M2.5 — Rollback Runbook (Phase G)

**Status:** Prepared and rehearsal-tested. **Never executed against production.**
**Rehearsal evidence:** old-backend-on-v3 (`rehearsal/uvicorn-prod.log`), old-backend-on-v2 (`rehearsal/uvicorn-prod-v2.log`), runner downgrade timing, image inventory.

## 0. Preconditions (verified)

| Asset | Value |
|---|---|
| Running prod images (rollback targets) | backend `sha256:8cb02c8b7e18d95df5af80ae3601d76dfcf403bb9df5764dc158a3a21c77bcd5` = `spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0` · frontend `sha256:6dec82c38484fc93e3d55f2a0e1fb3c4b2694b0558ae46c928124e0e5ff5e233` = `spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0` — **present on host, tag-verified** |
| ⚠️ Not the rollback images | Host tags `rollback-75eba50` point to **older pre-V3 images** (`bcd58f603cdd` / `52369140ad11`) — do **not** use them for M2.5 rollback |
| Pre-cutover DB backup | `/home/david/backups/spectra/m2-5-cutover-prep/spectra-prod-v2-20261115T143818Z.db` (SHA-256 `801dd666…`, integrity ok) |
| Cutover-time backup | taken fresh after write freeze (Cutover Runbook step 3) — this is the Strategy-B restore point |
| Prod compose | `/home/david/releases/spectra-75eba50-ops/compose.json`, project `spectra`, volume `spectra-sqlite-data`, network `spectra_default` |

## 1. Rollback triggers (operator decision points)

Any of:
- `/ready` non-200 for 3 consecutive health cycles after cutover.
- 5xx rate > 5% over 5 minutes on `/api/*`.
- Catalog mismatch: `GET /api/hardware/facets` types ≠ CPU 3501 / GPU 1879 (+ fixture counts if fixtures loaded).
- Compatibility check 5xx or wrong `rules_version` (≠ `M2.5-RULES-v1`).
- DOM check failure on the six-tab strip or build slots after cutover.
- Conversation persistence failure (create/read).

**Decision owner:** release operator. Rollback is a compose-level operation; it does **not** require re-approval, but the operator must announce the freeze window to users (single-user homelab).

## 2. Strategy A — Application rollback (primary)

**Valid because:** migration v2→v3 is additive-only and the old backend provably runs on a v3 database (rehearsal: ready 200, catalog OK, conversation create OK). Post-cutover data (conversations/messages) **survives**.

```bash
ssh david-lab

# 1. Freeze writes (stop prod; DB untouched)
cd /home/david/releases/spectra-75eba50-ops
docker compose -p spectra -f compose.json stop backend frontend

# 2. Point compose back to the 75eba50 image tags
#    (compose.json already pins them; only needed if cutover edited it:
#     restore the file from git or re-edit image: lines to
#     spectra-backend:75eba50b1f09052f40409f6066a2ac030344d1a0 /
#     spectra-frontend:75eba50b1f09052f40409f6066a2ac030344d1a0)

# 3. Replace containers (atomic, same volume)
docker compose -p spectra -f compose.json up -d --force-recreate

# 4. Health
docker ps --filter name=spectra --format '{{.Names}} {{.Status}}'
curl -s http://100.113.157.0:8080/api/ready          # expect tracked-version-2 (old code reports v2)
curl -s 'http://100.113.157.0:8080/api/hardware?limit=1'
```

**Downtime:** ~10–20 s (stop + recreate + health). **Data loss:** none (DB stays v3; old code ignores the four new tables; `schema_version` stays 3 — old `/ready` will still say `tracked-version-3`? No: old code reads the same `schema_version` table → reports **3**; harmless).

Note: leave the DB at v3. **Do not** downgrade the production DB as part of Strategy A (unnecessary; additive tables are inert).

## 3. Strategy B — Full database rollback (secondary)

**Use when:** the v3 database itself is suspected (corruption, bad migration state), or Strategy A failed.

**Data-loss disclosure (explicit):** every conversation/message/user row created **after the cutover-time backup** is lost. Current prod rate is ~1 conversation write per hour at peak (observed); the operator must weigh this against the trigger. To preserve post-cutover conversations, export them via `GET /api/build/conversations` (+ messages) **before** the restore and re-create after recovery, if the operator chooses.

```bash
ssh david-lab

# 1. Stop both prod containers (write freeze)
cd /home/david/releases/spectra-75eba50-ops
docker compose -p spectra -f compose.json stop backend frontend

# 2. Replace the DB in the volume with the cutover-time backup
#    (volume is root-owned; run the copy inside a short-lived container)
docker run --rm -v spectra-sqlite-data:/data -v /home/david/backups/spectra:/bk alpine \
  sh -c 'cp /bk/spectra-prod-v2-<CUTOVER_TS>.db /data/spectra.db && chown 0:0 /data/spectra.db'

# 3. Restore old image tags in compose.json (as Strategy A step 2)

# 4. Start old stack
docker compose -p spectra -f compose.json up -d --force-recreate

# 5. Verify
docker exec spectra-backend python3 -c "import sqlite3;c=sqlite3.connect('/app/data/spectra.db');print(c.execute('PRAGMA integrity_check').fetchone(), c.execute('SELECT version FROM schema_version').fetchone())"
curl -s http://100.113.157.0:8080/api/ready        # tracked-version-2
```

**Downtime:** ~1–2 min (stop + 48.8 MB restore + start + verify). **Data loss:** post-backup writes (quantified above).

## 4. Consistency guardrails

- Both strategies preserve `spectra-sqlite-data` and `spectra_default`; nothing touches staging projects (`spectra-m25-staging`, `spectra-m2-staging`) or other containers.
- Never run `--target 1` downgrade on production (would drop `users`/`owner_id` — data-bearing); Strategy B's restore supersedes it.
- If the cutover-time backup file is missing/corrupt: Strategy B is unavailable; fall back to Strategy A + fresh full backup investigation (integrity check on the live DB) before any further action.

## 5. Rehearsal results

| Rehearsal | Result |
|---|---|
| Old backend (75eba50^) on **v3** DB | ready 200 in 0.04–2.4 s; `/hardware`, `/facets`, conversation create + reset all 200 → Strategy A valid |
| Old backend on **v2** backup copy | ready 200; catalog OK; conversation create 200 → Strategy B valid |
| Runner downgrade v3→v2 | 3.46 s, clean (host-level; **not** used in prod runbook) |
| Prod image `docker save` | 74.9 MB tar written and deleted (offline-insurance copy is feasible pre-cutover) |

**Production has not been modified.** Execution of either strategy is authorized implicitly as part of an approved cutover, or explicitly at incident time by the operator.
