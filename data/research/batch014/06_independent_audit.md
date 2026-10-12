# Batch 014 — Independent Verification Audit

**Verdict: PASS**

## 1. Inputs

| Item | Value / Path |
|---|---|
| Pre-apply backup | `C:\SPECTRA\data\backups\spectra.db.batch014-20261012T053835Z.bak` |
| Backup SHA-256 | `a0539d3042e37f1a6cca431bc5f002823a80e0f9bb221df7aa3604ea4d450214` |
| Post-apply DB SHA-256 | `401a3974586265804ed55f07a998addfac3dd7eb46f2f226e3a32e3eabd9035` |
| Source | `Wikipedia (English)` (source id 5), CC BY-SA 4.0, access date 2026-10-12 |
| Candidate inventory | `data/research/batch014/_candidates.json` (141 candidates, 3 excluded) |
| Patch | `data/research/batch014/05_database_patch.json` |
| Audit script | `data/research/batch014/audit_batch014.py` |
| Full result | `data/research/batch014/_audit_result.json` |

All checks were recomputed from the backup + live DB (`mode=ro`), independently of
the apply script's own prints.

## 2. Scope of change

This is an **INSERT-only** batch. No existing hardware, specification, benchmark,
external-identifier, source or build-conversation row is modified or removed.

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| hardware | 5,239 | 5,380 | +141 |
| CPU | 3,360 | 3,501 | +141 |
| cpu_specifications | 3,360 | 3,501 | +141 |
| field_provenance | 35,849 | 36,946 | +1,097 |
| GPU | 1,879 | 1,879 | 0 |
| external_identifiers | 3,575 | 3,575 | 0 |
| benchmark_results | 1,040 | 1,040 | 0 |
| build_conversations | 5 | 5 | 0 |

New records by architecture: Arrow Lake 35, Zen 5 26, Zen 4 25, Raptor Lake
Refresh 25, Meteor Lake 21, Lunar Lake 9. All 141 carry `architecture`, `cores`,
`threads`, `base_clock_ghz`, `boost_clock_ghz` and `tdp_w`; 102 carry
`release_date`; 76 carry `process_node_nm`; 73 carry `socket`.

## 2.1 Independent audit checks (all recomputed from backup + live DB)

| # | Check | Result |
|---:|---|---|
| 1 | `PRAGMA integrity_check` | `ok` |
| 2 | `PRAGMA foreign_key_check` | 0 violations |
| 3 | candidates present | 141/141 |
| 4 | spec values match the patch | all match |
| 5 | provenance complete per inserted field | all present |
| 6 | no duplicate CPU names | 0 duplicate groups |
| 7 | no hardware rows deleted | 0 |
| 8 | added count | 141 (expected 141) |
| 9 | no hardware rows modified | 0 |
| 10 | no spec rows modified | 0 |
| 11 | no spec rows removed | 0 |
| 12 | no provenance lost | 35,849 → 36,946 |
| 13 | benchmark rows preserved | 1,040 → 1,040 |
| 14 | external identifiers preserved | 3,575 → 3,575 |
| 15 | build conversations preserved | 5 → 5 |
| 16 | idempotent re-run | 0 would be re-inserted |

Full machine-readable result: `_audit_result.json` (`passed: true`, `failures: []`).

## 3. Integrity checks

- `PRAGMA integrity_check` = `ok`; `PRAGMA quick_check` = `ok`; `PRAGMA foreign_key_check` = 0.
- Row counts changed only by the 141 intended inserts (plus their 141 spec rows and
  1,097 provenance rows).
- Only `hardware`, `cpu_specifications` and `field_provenance` gained rows; no other
  table changed.
- 0 hardware/spec rows modified or removed; 0 duplicate CPU names.
- Every inserted field has a provenance row with `source_id=5`,
  `evidence_status='verified'`, `license_name='CC BY-SA 4.0'` and `batch_no=14`.
- Backup hash equals the pre-apply database hash; the production DB hash is recorded.
- Re-running the loader reports 0 inserts (idempotent).
- No benchmark or gaming benchmark rows were imported or altered.

## 4. Verdict

**PASS** — 141 modern CPU records (14th-gen Intel, Core Ultra 1/2, AMD Ryzen
9000/8000/8000F/8040/8045 and Ryzen AI 300) were added with complete field-level
provenance, no overwrites, no deletions and no collateral changes; integrity and all
16 independent checks pass.
