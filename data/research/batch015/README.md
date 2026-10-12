# Batch 015 — Source Transparency & Data Provenance

Read-only transparency work over what the project already knows about where its
hardware and benchmark data came from. The batch does **not** change any
hardware specification value, benchmark score or configuration, external
identifier, or provenance row. It adds the smallest safe additive schema change
to the `sources` registry, exposes the existing provenance through a read-only
API, and surfaces compact source disclosures in the UI.

Base commit: `819018b` (`feat(data): expand modern CPU catalog coverage`).

## What changed

- **Schema (additive).** `sources` gained eight nullable metadata columns:
  `publisher`, `description`, `license_name`, `license_url`, `license_status`,
  `terms_notes`, `attribution`, `retrieved_on`. No existing row was rewritten;
  no source was created, deleted, renamed or remapped. Applied with an
  idempotent `ALTER TABLE ADD COLUMN` migration
  (`backend/app/migrations/add_source_license_metadata.py`) after backing up
  the live database and rehearsing on a disposable copy.
- **Registry data.** The eight columns were filled for the nine registered
  sources from `backend/app/source_registry.py`, whose values are grounded in
  the Batch 009/010 licence research — not assumed.
- **Read-only API.** `/sources`, `/sources/{id}`, `/hardware/{id}/provenance`
  and `/benchmarks/{id}/provenance`. Batched queries (no N+1); 404 on unknown
  ids; existing `/hardware/...` and benchmark responses unchanged.
- **Frontend.** A compact, keyboard-accessible source disclosure under detail
  spec rows, and secondary source attribution for benchmark evidence and
  comparison evidence.

## Licensing distinctions made visible

Provenance is now labelled with an honest status derived from repository
evidence:

| Status | Meaning | Sources |
| --- | --- | --- |
| `clear` | documented reuse licence | 4 (CC BY 4.0), 5 (CC BY-SA 4.0) |
| `restricted` | reuse requires permission | 1 PassMark, 3 TechPowerUp |
| `unknown` | terms inaccessible / no grant | 2 Geekbench, 6 & 8 Intel ARK, 9 AMD |
| `unresolved` | legacy origin undocumented | 7 (Batch 008 placeholder) |

No permission request was sent and no restricted dataset was re-imported.

## Artifacts

| File | Purpose |
| --- | --- |
| `_snapshot.py` / `_db_snapshot.json` | reproducible pre-change baseline |
| `build_source_audit.py` / `_source_audit.json` | machine-readable source + licence + coverage audit |
| `audit_batch015.py` / `_audit_result.json` | independent before/after integrity audit |
| `01_current_state_audit.md` | baseline counts and coverage gaps |
| `02_source_and_license_audit.md` | per-source licence findings and evidence |
| `03_design_and_migration.md` | additive change and its implications |
| `06_independent_audit.md` | audit method, results, limitations |

## Reproduce

```powershell
python data/research/batch015/_snapshot.py
python data/research/batch015/build_source_audit.py
python data/research/batch015/audit_batch015.py
```

## Honest gaps (not fixed by this batch)

- 24 CPUs with specifications have no specification provenance.
- 20 hardware rows have no provenance at all.
- Source 7 is a legacy placeholder whose originating source is undocumented.
- 32,519 provenance rows carry no `license_name` because their source's terms
  are unknown/restricted; the UI now reports this as such rather than implying
  a licence.
