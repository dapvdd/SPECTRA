# M3.3 Migration Report (Phase 4)

**Date**: 2026-11-25
**Target**: restored production clone `/tmp/m33_migration_rehearsal.db`
(inside `spectra-backend` container; live DB untouched)
**Release branch**: `release/m33-production`

## 1. Rehearsal design

Never against the live database. The Phase 3 backup (v3, verified restorable)
was cloned to a disposable path inside the container and the migration ran
there. Because the production image (M2.5, `dcfd7df`) carries the v3 runner,
the migration runner was imported from the **RC source tree** (`5c2c7d9`)
copied into the container (`/tmp/rc/backend`) — provenance-guarded in the
script (`runner.LATEST_VERSION == 4` assert + runner file path check) so a
silent M2.5-runner drift cannot fake the result.

## 2. Actual schema state (deterministic, Phase 0/1 evidence)

- Production live DB: schema **v3** (`schema_version` id=1 version=3, applied
  2026-11-16T07:31:47Z); hardware has NO v4 identity columns; v4-era spec
  tables exist (M2.5 schema).
- Backup + rehearsal clone: same v3 state (verified before upgrade).

## 3. Migration path v3 → v4 (single migration, additive)

Migration 4 `m3-catalog-expansion-identity-lifecycle`:
- `ALTER TABLE hardware ADD COLUMN` × 5: `canonical_key VARCHAR(300)`,
  `product_family VARCHAR(200)`, `identity_status VARCHAR(20)`,
  `record_status VARCHAR(20)`, `superseded_by_id INTEGER REFERENCES hardware(id)`
- `CREATE TABLE ingestion_runs`, `CREATE TABLE publication_batches` (ops audit)
- `CREATE UNIQUE INDEX uq_hardware_canonical_key ON hardware(canonical_key)
  WHERE canonical_key IS NOT NULL` (partial — legacy NULL keys untouched)

## 4. Rehearsal evidence (all checks PASS)

| Check | Result |
|---|---|
| Dry-run first | applied=[4], **version stays 3** (no mutation) |
| Real upgrade | status `upgraded`, applied=[4] |
| Repeated execution | second run → `up-to-date` (idempotent, no error) |
| Row preservation | hardware 5380→5380, cpu_spec 3501, gpu_spec 1879, benchmarks 1040, conversations 7, messages 10, sources 10, provenance 39440 — **zero loss** |
| Legacy lifecycle | 5380/5380 legacy rows keep NULL canonical_key/identity_status/record_status |
| v4 columns present | true (all 5) |
| Ops tables present | ingestion_runs + publication_batches |
| Unique partial index | present with `WHERE canonical_key IS NOT NULL`; **enforcement proven**: setting the same canonical key on 2 rows fails with IntegrityError and the statement does not half-apply |
| integrity_check | ok |
| foreign_key_check | 0 violations |
| ORM compatibility | RC v4 ORM on migrated schema: query 5380/3501/1879; conversation 1 relationship loads (2 messages); write+flush+**rollback leaves no row** |
| Restart behavior | fresh reopen after all steps: version 4, hardware 5380, integrity ok |

## 5. Before/after comparison

| Metric | Before (v3) | After (v4) |
|---|---|---|
| hardware | 5380 | 5380 |
| CPU/GPU catalog | 3501/1879 | 3501/1879 |
| benchmarks | 1040 | 1040 |
| conversations | 7 | 7 |
| field_provenance | 39440 | 39440 |
| schema_version | 3 | 4 |
| v4 identity columns | absent | present (all NULL on legacy rows) |
| ingestion_runs / publication_batches | absent | present (empty) |
| integrity / FK | ok / 0 | ok / 0 |

No unexplained legacy data loss — the release-blocker condition is not
triggered.

## 6. Transaction safety

- Dry-run executes nothing (`version_after_dryrun == 3` verified).
- Each migration runs in a single transaction (`BEGIN` … commit) with the
  migration's own `verify` callback before commit (`runner.py` upgrade loop);
  a failure mid-migration leaves the DB at v3.
- The unique-index probe proves constraint enforcement and rollback behavior
  on the migrated schema.

## 7. Command record

```bash
# inside spectra-backend container
docker cp /tmp/m33_migrate2.py spectra-backend:/tmp/migrate2.py
docker exec spectra-backend python /tmp/migrate2.py
# evidence: /tmp/m33_migration_evidence.json (container) — mirrored below
```

## 8. Honest limits

- Rehearsed on the Phase 3 backup clone (v3, prod-identical), not on the live
  DB — by design.
- The container image's own runner is v3 (M2.5); production deployment will
  run a **new image built from the RC** whose runner knows v4. The rehearsal
  imported the RC runner explicitly with provenance asserts, which is exactly
  what the Phase 6 deployment will exercise in-image.
- `sqlite3` in the container is modern (>3.35), so the v4 `DROP COLUMN`
  limitation documented in M3 does not affect this forward-only path.
