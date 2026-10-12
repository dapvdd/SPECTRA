# Batch 014 — Current-State Audit

**Repository:** `C:\SPECTRA`
**Date:** 2026-10-12 (UTC)
**Method:** read-only SQL against a byte-identical copy of the production database;
all figures recomputed from scratch (no trust in earlier prints).

Baseline verified at the start of this batch:

| Item | value |
|---|---|
| Git branch | `main` |
| Git HEAD | `fc424b5` (`feat(frontend): polish visual cohesion and motion`) |
| `data/spectra.db` SHA-256 | `a0539d3042e37f1a6cca431bc5f002823a80e0f9bb221df7aa3604ea4d450214` |
| Size | 51,191,808 bytes |
| `PRAGMA integrity_check` / `quick_check` | `ok` / `ok` |
| `PRAGMA foreign_key_check` | 0 violations |
| hardware | 5,239 (CPU 3,360 / GPU 1,879) |
| cpu_specifications | 3,360 |
| field_provenance | 35,849 |
| external_identifiers | 3,575 |
| benchmark_results | 1,040 |
| build_conversations / messages | 5 / 5 |
| sources | 9 (id 5 = `Wikipedia (English)`) |

The baseline hash is the SHA-256 of the pre-write backup
`data/backups/spectra.db.batch014-20261012T053835Z.bak`, which is a byte-identical
copy of the live database taken inside the guarded apply step. The production DB
now hashes to `401a3974586265804ED55F07A998ADFAFBC3DD7EB46F2F226E3A32E3EABD9035`.

---

## 1. Schema and field types (unchanged)

`hardware`:

```
id INTEGER PK, name VARCHAR(200) NOT NULL, manufacturer VARCHAR(100) NOT NULL,
type VARCHAR(50) NOT NULL, release_date DATE, architecture VARCHAR(100)
```

`cpu_specifications`:

```
id INTEGER PK, hardware_id INTEGER UNIQUE FK->hardware.id,
cores INTEGER, threads INTEGER, base_clock_ghz FLOAT, boost_clock_ghz FLOAT,
tdp_w FLOAT, process_node_nm FLOAT, socket VARCHAR(50)
```

`field_provenance` records per-field evidence and requires `hardware_id`,
`source_id`, `table_name`, `field_name`, `evidenced_value`, `source_url`,
`evidence_status`, `batch_no`, `recorded_at`; a partial unique index
`uq_field_provenance_identity` on
`(hardware_id, table_name, field_name, source_id, evidenced_value, evidence_status)`
guards non-benchmark provenance against re-insertion. **No schema change is needed
for this batch.**

---

## 2. CPU population

| Metric | Value |
|---|---:|
| Total CPUs | 3,360 |
| Intel | 2,694 |
| AMD | 666 |
| GPUs | 1,879 |

---

## 3. Coverage by field (measured from scratch)

| Field | Table | Non-NULL | NULL | Coverage |
|---|---|---:|---:|---:|
| `architecture` | hardware | 571 | 2,789 | 17.0 % |
| `release_date` | hardware | 112 | 3,248 | 3.3 % |
| `cores` | cpu_specifications | 3,355 | 5 | 99.9 % |
| `threads` | cpu_specifications | 2,899 | 461 | 86.3 % |
| `base_clock_ghz` | cpu_specifications | 3,131 | 229 | 93.2 % |
| `boost_clock_ghz` | cpu_specifications | 2,284 | 1,076 | 68.0 % |
| `tdp_w` | cpu_specifications | 3,083 | 277 | 91.8 % |
| `process_node_nm` | cpu_specifications | 2,397 | 963 | 71.3 % |
| `socket` | cpu_specifications | 3,238 | 122 | 96.4 % |

These match the state left by Batch 013 (no data change since Batch 003).

---

## 4. Gap analysis driving Batch 014

The brief named several modern families as *suspects*. They were treated as
hypotheses and audited first; every one was confirmed **completely absent** from
the catalog (0 exact-name matches before the batch):

| Family / pattern | Rows present (before) |
|---|---:|
| Intel Core i9-149xx (14th-gen Raptor Lake Refresh) | 0 |
| Intel Core Ultra (Meteor Lake / Arrow Lake / Lunar Lake) | 0 |
| AMD Ryzen 9000 (Zen 5 desktop) | 0 |
| AMD Ryzen 8000G / 8000F (Zen 4 desktop APU) | 0 |
| AMD Ryzen 8040 / 8045 (Zen 4 mobile) | 0 |
| AMD Ryzen AI 300 (Zen 5 mobile) | 0 |

The catalog therefore contains no modern (2023-2026) consumer desktop or mobile
CPU coverage beyond 13th-gen Intel / Ryzen 7000. This is a **missing-record** gap,
not a missing-field gap: the fix is additive inserts, not updates. Batch 014 is
therefore an INSERT-only batch.

---

## 5. What Batch 014 adds

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| hardware | 5,239 | 5,380 | **+141** |
| CPU | 3,360 | 3,501 | **+141** |
| cpu_specifications | 3,360 | 3,501 | **+141** |
| field_provenance | 35,849 | 36,946 | **+1,097** |
| GPU | 1,879 | 1,879 | 0 |
| external_identifiers | 3,575 | 3,575 | 0 |
| benchmark_results | 1,040 | 1,040 | 0 |
| build_conversations | 5 | 5 | 0 |

New records by architecture:

| Architecture | Rows |
|---|---:|
| Arrow Lake | 35 |
| Zen 5 | 26 |
| Zen 4 | 25 |
| Raptor Lake Refresh | 25 |
| Meteor Lake | 21 |
| Lunar Lake | 9 |

All 141 new records carry `architecture`; 102 carry a full `release_date`; every
record carries all five core numeric fields; 76 carry `process_node_nm` and 73
carry `socket` (see `04_mapping_and_exclusions.md` for why the remainder are NULL).
Every inserted field has a `field_provenance` row attributing it to
`Wikipedia (English)` (source id 5, CC BY-SA 4.0) with `evidence_status='verified'`
and `batch_no=14`.
