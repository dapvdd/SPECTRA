# Batch 009 — Base Import History Reconstruction

Date: 2026-10-10

This document reconstructs the original SPECTRA data-import history for the
three base-import sources (CPU specifications, GPU specifications, CPU
benchmarks) from repository evidence and the local artifacts actually present
on this machine. Nothing here is inferred from plausibility: every claim links
to a file, a code path, or an observed cell value.

---

## 1. What the repository itself recorded before this batch

- `docs/DATA_SOURCES.md` (pre-existing) named the CPU bootstrap source as
  `https://github.com/felixsteinke/cpu-spec-dataset`, dataset
  `dataset/cpuworld-cpus.csv` ("CPUWorld CPU Dataset"). That documentation is
  **inaccurate for what was actually imported** (see §3).
- `docs/DATA_QUALITY_AUDIT.md` (Sprint 13 audit) recorded the registered
  sources as:
  1. PassMark CPU benchmark catalog
  2. Geekbench Browser, Geekbench 7 CPU
  3. TechPowerUp GPU Database
  and confirmed all 3,575 `external_identifiers` carry `source_id` = 1.
- The live `sources` table before this batch had 7 rows (source ids 1–7):
  PassMark (`benchmark-cpus.csv`), Geekbench 7, TechPowerUp GPU Database,
  GPU Ark, Wikipedia (English), Intel ARK (archived via Wayback), and the
  batch-008 placeholder "Unknown (source not documented in artifact)".
- Import code paths that reference the catalog files:
  - `backend/app/importers/benchmark_cpu_importer.py` imports/enriches CPUs
    from a CSV with columns `CpuName,Socket,ClockSpeed,TurboSpeed,Cores,
    Threads,TDP,ReleaseDate,SourceUrl` (i.e. `benchmark-cpus.csv`); it fills
    only NULL specification fields and never writes external identifiers.
  - `backend/app/importers/cpu_batch_importer.py` + `cpu_importer.py` import
    AMD/Intel CSVs (`amd-cpus.csv`, `intel-cpus.csv`) and write
    `external_identifiers` (intel_cpu_id, product_id_tray/boxed/mpk).
  - `backend/app/importers/gpu_importer.py` / `gpu_batch_importer.py` import
    `gpu_1986-2026.csv` (TechPowerUp-derived dataset) using the column set
    in `gpu_csv.py`.
  - `backend/app/importers/geekbench_score_importer.py` imports Geekbench 7
    scores from `~/Downloads/benchmark/processor-benchmarks.csv` by matching
    `devices/name` against stored CPU names.

## 2. Local artifacts actually present (besides the repo)

| Artifact | Location found | SHA-256 | mtime |
|---|---|---|---|
| `intel-cpus.csv` | `~/Downloads/intel-cpus.csv` | `eb164c40…d15d4` | 2026-08-22 |
| `amd-cpus.csv` | `~/Downloads/amd-cpus.csv` | `abe6c8eb…fcac6` | 2026-08-22 |
| `benchmark-cpus.csv` | `~/Downloads/benchmark-cpus.csv` and inside `cpu-spec-dataset-main.zip` | `90b19cd4…c9db` | 2023-07-10 |
| `gpu_1986-2026.csv` | `data/raw/gpu_1986-2026.csv` (git-ignored) | `495fb95e…da1f` | n/a |
| `processor-benchmarks.csv` | `~/Downloads/benchmark/processor-benchmarks.csv` | `22477b97…3d41e` | 2026-09-16 |
| `cpu-spec-dataset-main.zip` | `~/Downloads/` | n/a | 2026-09-16 |

`cpu-spec-dataset-main.zip` is the GitHub repository
`felixsteinke/cpu-spec-dataset` (AGPL-3.0). Its `dataset/` folder contains
`amd-cpus.csv`, `intel-cpus.csv`, `benchmark-cpus.csv`, `cpuworld-cpus.csv`
and `ampere-cpus.csv`; its README documents each file's origin:
- `amd-cpus.csv` — manually exported from
  `https://www.amd.com/en/products/specifications/processors`
- `intel-cpus.csv` — scraped from Intel ARK (`ark.intel.com`)
- `benchmark-cpus.csv` — scraped from `https://www.cpubenchmark.net/cpu_list.php`
- `cpuworld-cpus.csv` — scraped from `https://www.cpu-world.com/CPUs/CPU.html`

No import log files exist anywhere in the repository or on disk. No PassMark
or Geekbench download log was preserved. Access dates of the original imports
are not recorded anywhere and are **not fabricated** in this batch.

## 3. Reconstruction of what was actually imported

Reconciliation (see `evidence_reconciliation.csv` and
`provenance_reconciliation.md`) recovered the following facts.

### CPU hardware + specifications
- 3,360 CPU hardware rows in the DB. Of these, **3,313 rows match, by exact
  (manufacturer, name), the normalized rows of `intel-cpus.csv` +
  `amd-cpus.csv`** (the felixsteinke dataset export), and **47 rows match
  `benchmark-cpus.csv` only** (e.g. `Intel Xeon E5-1650 v3 @ 3.50GHz` —
  PassMark-style names). The DB therefore holds a mix of the Intel ARK / AMD
  exports and a small PassMark supplement.
- All 3,575 `external_identifiers` have `source_id` 1 (`intel_cpu_id` 2,675 +
  `product_id_tray` 620 + `product_id_boxed` 215 + `product_id_mpk` 65). These
  identifiers are only written by the `intel-cpus.csv` / `amd-cpus.csv` import
  path, so that path demonstrably ran. **The stored ``source_id`` 1 is
  mislabelled for those identifiers: they were actually produced by the Intel
  ARK and AMD exports, not by PassMark.** This is a recorded inconsistency,
  not silently corrected here.
- Fields the base import wrote: `name`, `manufacturer`, `type`, and the
  `cpu_specifications` columns `cores, threads, base_clock_ghz,
  boost_clock_ghz, tdp_w, socket` (Intel also `process_node_nm` from
  `Lithography`). CPU `release_date` came later (batch 003, from Wikipedia).
- The PassMark `benchmark-cpus.csv` path fills only NULL specification cells,
  so a CPU cell whose value is present in both the Intel/AMD export and the
  PassMark catalog is ambiguous at value level and is reported `uncertain`
  (never stored as verified).

### GPU hardware + specifications
- 1,879 GPU rows; **all 1,879 match `gpu_1986-2026.csv` by (manufacturer,
  name)**. Base-import fields: `name`, `manufacturer`, `type`,
  `release_date`, `architecture`, and the `gpu_specifications` columns
  `memory_gb, memory_type, core_clock_mhz, boost_clock_mhz,
  vram_bandwidth_gbps, tdp_w, interface, length_mm`.
- The 44 legacy core-clock values discussed in batch 008 come from an earlier
  TechPowerUp snapshot (batch 001); their current DB values do **not** match
  the current `gpu_1986-2026.csv` cell for the same entity, so they are not
  re-attributed here. They retain their existing batch-001 provenance that
  already flags the reuse restriction.
- `memory_bus_width_bits` is **not** a base-import field (no importer maps a
  bus-width column); all 1,443 values are GPU Ark enrichment (batch 006) and
  remain covered by batch-006 provenance.

### CPU benchmarks (Geekbench 7)
- 1,040 `benchmark_results` rows, all `source_id` 2, all
  `Geekbench 7`/`points`, 520 single-core + 520 multi-core, all
  `recorded_at` NULL.
- **1,040 of 1,040 reconcile exactly** to `~/Downloads/benchmark/
  processor-benchmarks.csv` (`devices/name` normalized match plus an exact
  `devices/score` or `devices/multicore_score` value match). No Geekbench
  6, PassMark score, or other benchmark family is present in the DB.

### What this means for the stored source-1 label
The DB labels everything CPU with "PassMark CPU benchmark catalog
(benchmark-cpus.csv)". The evidence shows the CPU specification values and
external identifiers actually trace to the Intel ARK and AMD exports, with a
minority of CPU rows and NULL-field fills from the PassMark catalog. This is
recorded as a **source-identity inconsistency in the existing data** and is
recommended for a data-cleaning decision in Batch 010 (it is not auto-fixed
in this batch because `sources.id` is referenced by many rows and the correct
disposition needs a decision, not a silent reassignment).

---

## 4. Methods and limitations

- Value-level reconciliation re-implements the same normalizers used by the
  importers (`benchmark_normalizer`, `cpu_normalizer`, `gpu_normalizer`) with
  drift-tolerant column resolution, so the comparison is to the values that
  the importer actually would have read.
- The five artifact files are outside Git (`data/raw/` is git-ignored;
  `~/Downloads` is not versioned). Their SHA-256 hashes are recorded in
  `provenance_reconciliation.json` so the exact artifact version can be
  re-identified. A future auditor without these files cannot reproduce the
  reconciliation from the repository alone.
- No import date, source URL per value, or access date can be recovered for
  the base imports; those fields are left NULL/absent and never invented.