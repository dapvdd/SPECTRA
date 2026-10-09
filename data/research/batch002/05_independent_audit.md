# Batch 002 — Independent Verification Audit

**Verdict: PASS**

This audit was recomputed from the actual database, the GPU Ark source, and the
pre-apply backup. It does **not** trust the counts printed by the apply step. The
`verified` values below come from `enrich_batch002.py verify`, which recomputes the
matching plan against the **pre-apply backup** and then re-checks the live database and a
cell-level diff of the whole database against that backup.

Inputs:

| Item | Path / value |
|---|---|
| Pre-apply backup | `data/backups/spectra-pre-batch002-coreclock-20261009T025502Z.db` |
| Backup SHA-256 | `503790258e1884b6478e64c52a2affd9f04eac8ae0e53f3d632be223312205a3` |
| Post-apply `data/spectra.db` SHA-256 | `5e4d71093f60843c166940704657adf1fe552d0c505953d9afc5ee277ecd389e` |
| Source | `data/raw/gpuark-gpu-specs.csv` (GPU Ark, CC BY 4.0) |
| Full machine-readable result | `data/research/batch002/audit_results.json` |

---

## 1. Checks performed

| # | Check | Result |
|---:|---|---|
| 1 | `PRAGMA quick_check` on live DB | `ok` |
| 2 | Backup hash equals the recorded pre-apply hash (and the Batch 001 checkpoint) | PASS — `503790…205a3` |
| 3 | Every applied value equals its source record (`base_clock`) | PASS — 1,012 checked, **0 mismatches** |
| 4 | No populated value overwritten — full cell-level diff of every table, backup vs live | PASS — 1,012 changed cells, **all** allowed (`core_clock_mhz`: NULL → GPU Ark value), **0 unexpected** |
| 5 | No duplicate / conflicting target updates | PASS — 1,012 unique `hardware_id` |
| 6 | Row counts unchanged (all tables incl. build_*) | PASS — see §2 |
| 7 | Coverage delta equals applied count (813 + 1,012 = 1,825) | PASS |
| 8 | `benchmark_results` unchanged; GPU benchmark rows = 0; gaming rows = 0 | PASS — 1,040 → 1,040; GPU 0; gaming 0 |

Every check is `true` in `audit_results.json`; `verdict = "PASS"`.

The cell-level diff (check 4) is the strongest guarantee: the backup and the live
database are compared cell by cell across `hardware`, `cpu_specifications`,
`gpu_specifications`, `benchmark_results`, `external_identifiers`, `sources`,
`build_conversations`, and `build_messages`. The only differences are the 1,012 intended
`gpu_specifications.core_clock_mhz` NULL→value updates. No hardware identity, no
benchmark row, no source record, and no unrelated table was altered; no row was inserted
or deleted.

---

## 2. Row counts (before → after, from backup vs live)

| Table | Before | After |
|---|---:|---:|
| hardware (CPU / GPU) | 5,239 (3,360 / 1,879) | 5,239 (3,360 / 1,879) |
| cpu_specifications | 3,360 | 3,360 |
| gpu_specifications | 1,879 | 1,879 |
| benchmark_results | 1,040 | 1,040 |
| external_identifiers | 3,575 | 3,575 |
| sources | 3 | 3 |
| build_conversations | 4 | 4 |
| build_messages | 4 | 4 |

---

## 3. GPU core-clock coverage

| | Non-null `core_clock_mhz` | NULL | Coverage |
|---|---:|---:|---:|
| Before | 813 | 1,066 | 43.27 % |
| After | 1,825 | 54 | **97.13 %** |

The remaining 54 NULLs are exactly the 50 ambiguous + 4 unmatched rows deliberately left
unfilled and preserved for review (see `02_mapping_results.csv` and
`04_database_patch.json`).

---

## 4. Recorded outcomes

| Outcome | Count |
|---|---:|
| GPU rows audited (field NULL) | 1,066 |
| Safe NULL-only updates applied | 1,012 |
| Ambiguous (excluded, boost not corroborated) | 50 |
| Unmatched (no normalized-name + vendor row) | 4 |
| Invalid values | 0 |

Excluded/unmatched rows are documented in `02_mapping_results.csv` (`status`,
`exclusion_reason`), `03_preflight_report.md` §3, and `04_database_patch.json`
(`excluded`, `unmatched`). They are unchanged in the database.

Note on artifacts: `04_database_patch.json` is the Phase-3 **proposal** (`"applied": false`
records its state at proposal time). The authoritative record of what was applied is
`apply_results.json`; the authoritative record of the verification is
`audit_results.json`.

---

## 5. Source/licence compliance

- Values came only from the CC BY 4.0 GPU Ark dataset (`https://gpuark.com/datasets/`),
  cited in every artifact (`source_url`, plus the citation string in the patch JSON).
- The TechPowerUp snapshot was **not** used for this batch (robots.txt forbids bulk data
  extraction / dataset creation without written permission).
- No value was invented, inferred, interpolated, or unit-converted.

---

## 6. Test suites (hermetic)

Run from the repository with the backend database URL redirected to a throwaway copy,
so the production database was never touched by tests.

| Suite | Command | Result |
|---|---|---|
| Backend | `python -m pytest backend/app -q` with `SPECTRA_DATABASE_URL` → temp DB copy | **548 passed**, 0 failed |
| Frontend | `npm test` (`node --test src/*.test.js`) | **520 passed**, 0 failed |

Production `data/spectra.db` SHA-256 re-checked after the test run:
`5e4d7109…cd389e` (unchanged by tests).

---

## 7. Explicit confirmations

- Application code: **untouched** (no `backend/`, `frontend/` source changes).
- Gaming benchmarks: **not added** (GPU benchmark rows = 0, gaming rows = 0).
- `.opencode/`: **untouched**.
- Hardware identities, benchmark rows, source records, and unrelated tables: **unchanged**.
- No inserts or deletes anywhere.

**Independent audit verdict: PASS.**
