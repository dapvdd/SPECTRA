# Batch 014 — Expand modern CPU catalog coverage

Adds **141 missing modern consumer CPU records** (2023–2026) to the SPECTRA catalog,
each with complete field-level provenance, in a guarded, insert-only, idempotent
operation.

**Commit subject:** `feat(data): expand modern CPU catalog coverage`
**Source:** English Wikipedia — CC BY-SA 4.0 (`sources` id 5), access date 2026-10-12.
**Verdict:** independent audit PASS (16/16 checks, `06_independent_audit.md`).

## What was added

| Family | Rows |
|---|---:|
| Intel Core 14th-gen (Raptor Lake Refresh) | 25 |
| Intel Core Ultra — Meteor Lake (H/U/HL/UL) | 21 |
| Intel Core Ultra 200 — Arrow Lake (S/U/H/HX) | 35 |
| Intel Core Ultra 200V — Lunar Lake | 9 |
| AMD Ryzen 9000 (Zen 5 desktop) | 19 |
| AMD Ryzen 8000G / 8000F (Zen 4 desktop APU) | 10 |
| AMD Ryzen 8040 / 8045 (Zen 4 mobile) | 15 |
| AMD Ryzen AI 300 (Zen 5 mobile) | 7 |
| **Total** | **141** |

Inserted: 141 `hardware` + 141 `cpu_specifications` + 1,097 `field_provenance`.
Updated: 0. Deleted: 0. Benchmarks/external ids/build conversations: unchanged.

## Contents

| File | Purpose |
|---|---|
| `01_current_state_audit.md` | baseline state, coverage, target-family gap analysis |
| `02_source_and_licence_audit.md` | sources considered, licence terms, reliability gate |
| `03_candidate_inventory.csv` | all 141 candidates + the 3 excluded rows, with source refs |
| `04_mapping_and_exclusions.md` | naming/value/architecture mapping rules and exclusions |
| `05_database_patch.json` | the apply-ready patch (proposed inserts) |
| `06_independent_audit.md` | independent audit verdict and checks |
| `apply_results.json` | applied counts, hashes, backup path, verification summary |
| `batch014_stats.json` | before/after metrics |
| `build_candidates.py` | deterministic extractor (16 table specs) |
| `wikitext_tables.py` | dependency-free wikitext table parser |
| `apply_batch014.py` | guarded INSERT-only loader (dry-run by default) |
| `audit_batch014.py` | independent auditor (16 checks) |
| `sources/` | raw Wikipedia/Template wikitext + `manifest.json` (URLs, hashes, licence) |
| `_candidates.json` | full machine-readable inventory (candidates + excluded) |

## Guarantees

- **Additive only** — INSERTs; no existing row is updated, renamed or deleted.
- **Idempotent** — canonical-name matching skips rows already present; provenance uses
  `INSERT OR IGNORE` behind the partial unique index.
- **Recoverable** — a verified pre-write backup is created inside the apply step
  (`data/backups/spectra.db.batch014-20261012T053835Z.bak`) and the write runs in a
  single `BEGIN IMMEDIATE` transaction.
- **Provenanced** — every inserted field carries a `field_provenance` row
  (Wikipedia, CC BY-SA 4.0, `verified`, `batch_no=14`).
- **Reproducible** — see `04_mapping_and_exclusions.md` §7.

## Database

| | before | after |
|---|---:|---:|
| hardware | 5,239 | 5,380 |
| CPU | 3,360 | 3,501 |
| field_provenance | 35,849 | 36,946 |

Pre-apply SHA-256: `a0539d3042e37f1a6cca431bc5f002823a80e0f9bb221df7aa3604ea4d450214`
Post-apply SHA-256: `401a3974586265804ed55f07a998addfac3dd7eb46f2f226e3a32e3eabd9035`

## Tests

- `backend/app/test_batch014_catalog_ingestion.py` — extraction helpers, candidate
  inventory invariants, and the guarded loader (insert-only, no-overwrite,
  idempotent, provenance complete) against a disposable SQLite DB.
- Full backend suite and frontend suite/lint/build are run as part of the batch
  (see the batch completion report).
