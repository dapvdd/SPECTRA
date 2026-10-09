# Batch 002 — Source & Schema Audit

**Repository:** `C:\SPECTRA`
**Date:** 2026-10-09 (UTC)
**Objective:** recover missing GPU `gpu_specifications.core_clock_mhz` values from an
already-present, documented, legitimately reusable local source.

Baseline (read-only, verified at start of this batch):

| Item | Value |
|---|---|
| Git HEAD | `798d33e` (`feat(data): apply hardware enrichment batch 001`) |
| `data/spectra.db` SHA-256 | `503790258e1884b6478e64c52a2affd9f04eac8ae0e53f3d632be223312205a3` |
| `data/spectra.db` size | 921,600 bytes |
| `PRAGMA quick_check` | `ok` |
| hardware | 5,239 (CPU 3,360 / GPU 1,879) |
| gpu_specifications | 1,879 (one row per GPU, no orphans) |

The stated estimate of ~1,110 missing GPU core clocks was **verified as an estimate**.
The current database has **1,066** missing values, because Batch 001 already filled 44
of the original 1,110 (`gpu_specifications.core_clock_mhz` NULL count went 1,110 → 1,066
in `batch001/apply_results.json`).

---

## 1. Schema and GPU specification model

`gpu_specifications` (SQLite):

```
id INTEGER PK, hardware_id INTEGER UNIQUE FK->hardware.id,
memory_gb FLOAT, memory_type VARCHAR(50), core_clock_mhz FLOAT,
boost_clock_mhz FLOAT, vram_bandwidth_gbps FLOAT, tdp_w FLOAT,
interface VARCHAR(50), length_mm FLOAT
```

The SQLAlchemy model is `backend/app/models/gpu.py::GPUSpecification`
(`core_clock_mhz: Mapped[float | None]`, nullable). The existing GPU importer
(`backend/app/importers/gpu_importer.py`) maps the TechPowerUp-derived snapshot column
`Clock Speeds__GPU Clock` → `core_clock_mhz` and `Clock Speeds__Boost Clock` →
`boost_clock_mhz` via `gpu_normalizer.py::parse_mhz` (strict `"<number> MHz"` parsing).
`core_clock_mhz` is the GPU reference/base clock, in **MHz**, and every GPU row already
holds a `boost_clock_mhz` where one exists.

Importer source constants:

```
GPU_SOURCE_NAME = "TechPowerUp GPU Database (gpu_1986-2026.csv)"
GPU_SOURCE_URL  = "https://www.techpowerup.com/gpu-specs/"
```

`gpu_validator.validate_gpu` bounds `core_clock_mhz` and `boost_clock_mhz` to
`[100, 4000]` (existing, unchanged project rule).

---

## 2. Local source snapshot inventory

Two GPU specification snapshots are present under `data/raw/` (that directory is
git-ignored — "acquired, not versioned").

### 2.1 `data/raw/gpu_1986-2026.csv` — TechPowerUp snapshot — **NOT USABLE**

- Provenance: TechPowerUp GPU Database scrape (columns such as
  `Clock Speeds__GPU Clock`, `Clock Speeds__Base Clock`, `Clock Speeds__Boost Clock`;
  a `source_file` column holds per-card JSON filenames). This is the file behind the
  project's registered `source_id 3`.
- Reuse permission was **re-verified live** during this batch against
  `https://www.techpowerup.com/robots.txt` (verbatim):

  > "TechPowerUp content is made available for your personal, non-commercial use …
  > Use of any device, tool, or process designed to data mine or scrape the content
  > using automated means is prohibited without prior written permission …
  > Prohibited uses include … (1) text and data mining activities …; (2) the development
  > of any software, machine learning … and/or large language models (LLMs); (3) creating
  > or providing archived or cached data sets containing our content to others; and/or
  > (4) any commercial purposes. Contact w1zzard@techpowerup.com for assistance."

- Verdict: **BLOCKED for this enrichment.** Bulk extraction into a SPECTRA data set is
  exactly the "creating … data sets containing our content" use the terms prohibit, and
  permission has not been granted in writing. Per the batch rules, permission is
  *unclear*, so its data is **not** imported here. This decision is independent of the
  fact that Batch 001 used the same snapshot — that prior use does not constitute a
  licence grant, and the brief explicitly warned not to assume it did.

### 2.2 `data/raw/gpuark-gpu-specs.csv` — GPU Ark dataset — **USABLE**

- Provenance: documented by the dataset card `data/raw/README.md`
  (`license: cc-by-4.0`, `data_files: gpuark-gpu-specs.csv`, curated by GPU Ark).
- Reuse permission **re-verified live** at `https://gpuark.com/datasets/`:
  "**CC BY 4.0** — … use freely with attribution to gpuark.com."
- Citation required by the licence:
  `GPU Ark (2026). GPU specifications & benchmarks dataset. https://gpuark.com/datasets/`
- Columns include `vendor (nvd/amd/int)`, `manufacturer`, `base_clock`, `boost_clock`,
  `is_retail_board`. The dataset card documents that `vendor` is only set for chip-level
  rows and that unset-vendor rows are OEM/board variants.

---

## 3. Source column, units and semantics

For GPU Ark:

- Field used: **`base_clock`** — the GPU reference/base core clock.
- Unit: **MHz** (integer values, e.g. `166`, `1650`, `2670`). Confirmed by value range
  and by direct comparison to the database (section 4).
- Target: `gpu_specifications.core_clock_mhz`, also **MHz**. **No unit conversion** is
  applied (`MHz → MHz`). Blank `base_clock` cells are skipped; no zero or negative base
  clocks exist in the source.

Semantic validation against data already in the database (independent corroboration): of
the 813 GPU rows that already hold a `core_clock_mhz`, 58 have an exact-normalized-name
GPU Ark row; of those, the 44 whose stored `boost_clock_mhz` also equals GPU Ark's
`boost_clock` are certainly the same product, and for **all 44** GPU Ark's `base_clock`
equals the stored `core_clock_mhz` (0 mismatches). This confirms that GPU Ark
`base_clock` and SPECTRA `core_clock_mhz` are the same concept in the same unit.

---

## 4. Current missing-value count (from the database)

```
SELECT COUNT(*) FROM gpu_specifications;                       -- 1879
SELECT COUNT(*) FROM gpu_specifications WHERE core_clock_mhz IS NULL;     -- 1066
SELECT COUNT(*) FROM gpu_specifications WHERE core_clock_mhz IS NOT NULL; -- 813
```

Missing by manufacturer: NVIDIA 539, AMD 382, Intel 144, ATI 1.

Coverage before: **813 / 1879 = 43.27 %**.

---

## 5. Legitimacy confirmation

- GPU Ark is an **openly licensed (CC BY 4.0)** dataset that is already present in the
  repository and documented by its own dataset card. Attribution is preserved in every
  artifact produced by this batch (`02_mapping_results.csv` `source_url`, `04_database_patch.json`
  `source`, and this document).
- The TechPowerUp snapshot is **excluded** on licence grounds.
- No value is invented, inferred, interpolated, or converted; only exact field values
  from the documented source are copied into NULL target cells.

**Conclusion:** A legally and technically suitable source exists (GPU Ark), so Batch 002
proceeds to Phase 2 (deterministic matching) and Phase 3 (preflight).
