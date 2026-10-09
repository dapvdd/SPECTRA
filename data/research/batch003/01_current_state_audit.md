# Batch 003 — Current-State Audit

**Repository:** `C:\SPECTRA`
**Date:** 2026-10-09 (UTC)
**Method:** read-only SQL against `data/spectra.db` (`mode=ro`), recomputed from scratch.

Baseline verified at start of this batch:

| Item | Value |
|---|---|
| Git HEAD | `598fa12` (`feat(data): recover GPU core clocks from verified source`) |
| `data/spectra.db` SHA-256 | `5e4d71093f60843c166940704657adf1fe552d0c505953d9afc5ee277ecd389e` |
| Size | 929,792 bytes |
| `PRAGMA quick_check` | `ok` |
| hardware | 5,239 (CPU 3,360 / GPU 1,879) |

The historical figures were treated as estimates and re-measured. All numbers below
are from the live database.

---

## 1. Schema and field types

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

`architecture` and `release_date` live on `hardware`; the numeric fields live on
`cpu_specifications`. Release dates are stored as ISO `YYYY-MM-DD` when a full date is
known, otherwise NULL. No schema change is required for this batch.

Other tables: `benchmark_results` (1,040), `external_identifiers` (3,575),
`sources` (3), `build_conversations` (4), `build_messages` (4).

---

## 2. CPU population

| Metric | Value |
|---|---:|
| Total CPUs | 3,360 |
| Intel | 2,694 |
| AMD | 666 |

---

## 3. Coverage by field (measured from scratch)

| Field | Table | Non-NULL | NULL | Coverage |
|---|---|---:|---:|---:|
| `architecture` | hardware | 54 | **3,306** | 1.6 % |
| `release_date` | hardware | 48 | **3,312** | 1.4 % |
| `process_node_nm` | cpu_specifications | 2,381 | **979** | 70.9 % |
| `boost_clock_ghz` | cpu_specifications | 2,284 | **1,076** | 68.0 % |
| `tdp_w` | cpu_specifications | 3,083 | **277** | 91.8 % |
| `base_clock_ghz` | cpu_specifications | 3,131 | 229 | 93.2 % |
| `cores` | cpu_specifications | 3,355 | 5 | 99.9 % |
| `threads` | cpu_specifications | 2,899 | 461 | 86.3 % |
| `socket` | cpu_specifications | 3,238 | 122 | 96.4 % |

These match the state left by Batch 001 (Batch 001 added 54 architecture, 48 release
dates, 36 process-node, 11 base-clock and 11 TDP values).

### Process node — manufacturer split

- Intel: 2,356 of 2,694 populated; **338 Intel CPUs still NULL**.
- AMD: **25 of 666 populated; 641 AMD CPUs NULL** (process node was effectively
  Intel-only before Batch 001's 36 additions).

### Architecture gap — generation proxy

Using the populated `process_node_nm` as a generation proxy, the 2,665 Intel
missing-architecture CPUs cluster at 14 nm (880), 22 nm (537), 32 nm (329), 45 nm (219),
10 nm (132), plus 65/90/130/180/250 nm legacy and 337 with unknown node. The 641 AMD
missing-architecture CPUs are mostly pre-Zen/Ryzen generations.

---

## 4. Provenance tables

`sources`:

| id | name | url |
|---|---|---|
| 1 | PassMark CPU benchmark catalog (benchmark-cpus.csv) | https://www.cpubenchmark.net/ |
| 2 | Geekbench Browser - Geekbench 7 CPU | https://browser.geekbench.com/ |
| 3 | TechPowerUp GPU Database (gpu_1986-2026.csv) | https://www.techpowerup.com/gpu-specs/ |

`external_identifiers` covers CPUs only, all from source 1:
`intel_cpu_id` 2,675, `product_id_tray` 620, `product_id_boxed` 215,
`product_id_mpk` 65. There is no per-value provenance column for CPU
specifications, so value-level provenance is carried in this batch's evidence
artifacts (`03_evidence_table.csv`, `05_database_patch.json`), consistent with
Batch 001/002.

Benchmarks: 1,040 rows, all CPU Geekbench 7; **0 GPU benchmark rows, 0 gaming rows**.

---

## 5. Identity conventions observed

- Intel names look like `Intel Core i5-12400F Processor`, `Intel Pentium G4560 @ 3.50GHz`,
  `Intel Xeon Processor E5-2699 v4`.
- AMD names look like `AMD Ryzen 5 5600`, `AMD Athlon Gold 7220C`.
- Existing `architecture` values use the **platform/marketing codename** convention
  (e.g. `Rocket Lake`, not `Cypress Cove`; `Alder Lake`, not `Golden Cove`), and
  `Zen`, `Zen+`, `Zen 2`, `Zen 3`, `Zen 4` for AMD. Batch 003 follows this convention.

---

## 6. Gap summary driving Batch 003

| Priority | Field | Gap | Notes |
|---:|---|---:|---|
| 1 | `architecture` | 3,306 | largest gap; source-limited |
| 2 | `release_date` | 3,312 | full-date evidence only |
| 3 | `process_node_nm` | 979 | AMD-dominated; Intel mostly done |
| 4 | `boost_clock_ghz` | 1,076 | many are genuinely no-turbo parts |
| 4 | `tdp_w` | 277 | |

Batch 003 targets these from a legally reusable, deterministic source (see
`02_source_and_licence_audit.md`), respecting "correctness over row count".
