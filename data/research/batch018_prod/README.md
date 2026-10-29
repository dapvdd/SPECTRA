# Batch 018 — Production Migration (rehearsal-only tooling)

**Status:** READY FOR EXPLICIT PRODUCTION APPROVAL (no production writes performed)

This directory contains the deterministic migration tooling and rehearsal
evidence for applying the GPU Ark (CC BY 4.0) Batch 018 enrichment to the
DavidLab production database. It never writes to production: every step runs
against an isolated, consistency-safe copy.

## Files

| File | Purpose |
|---|---|
| `extract_rehearsal_copy.py` | Consistency-safe extraction of the production DB via the SQLite online backup API (read-only source → container `/tmp` scratch). Never a raw `cp`. |
| `migrate_batch018.py` | Migration tool (template with `RECORDS = []`). Guards: schema precondition, hardware existence, NULL-only, provenance de-dup, exact-count enforcement, transactional + idempotent. |
| `generate_selfcontained.py` | Embeds the 965 verified records into `migrate_batch018_selfcontained.py` (the deployable artifact). |
| `migrate_batch018_selfcontained.py` | Generated artifact (git-ignored; reproduced by `generate_selfcontained.py` + `batch018_valid_records.json`). |
| `verify_rehearsal_apply.py` | Independent read-only post-apply verification (coverage, provenance, integrity, no-overwrite). |
| `diag_mismatches.py` | Confirms the 27 reported "mismatches" are float-coercion artifacts (numerically equal) and there are 0 real problems. |
| `prove_rollback.py` | Proves the file-restore rollback is exact (hash match) on the rehearsal copy. |
| `../batch017/batch018_valid_records.json` | Authoritative 965-record payload (interface=938, memory_bus_width_bits=27). |
| `../batch017/{inspect_prod,inspect_prod_schema,inspect_prod_batch}.py` | Read-only production inspection used to establish the discrepancy and NULL-guard preconditions. |

## Exact rehearsal commands (DavidLab, inside `spectra-backend`)

From `C:\Users\user\spectra-local`:

```powershell
# 1. Consistency-safe rehearsal copy (SQLite backup API) -> container /tmp
Get-Content data\research\batch018_prod\extract_rehearsal_copy.py -Raw -Encoding UTF8 |
  ssh david-lab "docker exec -i spectra-backend python -"

# 2. Generate the self-contained migration artifact
python data\research\batch018_prod\generate_selfcontained.py

# 3. Preflight (read-only validation) on the rehearsal copy
Get-Content data\research\batch018_prod\migrate_batch018_selfcontained.py -Raw -Encoding UTF8 |
  ssh david-lab "docker exec -i spectra-backend python - /tmp/<rehearsal.db> --verify"

# 4. Apply + verify on the rehearsal copy ONLY
Get-Content data\research\batch018_prod\migrate_batch018_selfcontained.py -Raw -Encoding UTF8 |
  ssh david-lab "docker exec -i spectra-backend python - /tmp/<rehearsal.db> --apply --verify"

# 5. Idempotency: re-run step 4 -> must report changes:0
# 6. Rollback proof (see prove_rollback.py)
```

## Approval gate — DO NOT run against `/app/data/spectra.db`

The same self-contained script, when approved, is run against the **production**
path. Until explicit authorization is granted, the script must only ever be
pointed at an isolated rehearsal copy. See
`docs/MIGRATION_READINESS_BATCH018.md` for the full backup, rollback, and
maintenance-window procedure, and the evidence.

## Rehearsal results (2026-10-29)

- Apply: **965** (938 interface + 27 memory_bus_width_bits); quick_check=ok; FK=0.
- Provenance added: **965** (source_id=4, batch_no=18).
- Coverage after: interface 1787/1879 (95.1%), bus_width 1470/1879 (78.2%) —
  identical to staging.
- Real value/provenance mismatches: 0 (27 float-coercion artifacts verified equal).
- Idempotency: re-run => **0 changes**.
- Rollback: exact hash match to the baseline snapshot.
- Production DB hash unchanged throughout: `327c40ca…ae822`.
