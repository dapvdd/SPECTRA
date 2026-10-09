# Batch 002 — Preflight Report

**Source:** GPU Ark GPU specifications & benchmarks dataset — `data/raw/gpuark-gpu-specs.csv`
**Licence:** CC BY 4.0 (attribution to `https://gpuark.com/datasets/`)
**Target:** `gpu_specifications.core_clock_mhz` (MHz), NULL-only, guarded updates
**Status:** preflight complete — safety gates passed, ready to apply

---

## 1. Required counts

| Metric | Count |
|---|---:|
| GPU rows in database | 1,879 |
| GPU rows audited (target field NULL) | 1,066 |
| Source rows available (GPU Ark rows with a non-blank `base_clock`) | 10,516 |
| Exact normalized-identity matches | 1,062 |
| Deterministic normalized matches passing all guards (**safe updates**) | **1,012** |
| Ambiguous matches (excluded) | 50 |
| Unmatched rows (excluded) | 4 |
| Invalid values (excluded) | 0 |
| Candidates already populated (not touched) | 813 |
| **Safe NULL-only updates** | **1,012** |

`1,012 + 50 + 4 = 1,066` ✔ (every audited row is accounted for exactly once).

---

## 2. Matching method (deterministic, no fuzzy matching)

For each audited GPU row:

1. **Normalize identity.** Apply the project's `normalize_name`
   (`backend/app/importers/benchmark_normalizer.py`: collapse whitespace, strip Unicode
   control/format characters), then strip a leading chip-vendor prefix
   (`NVIDIA `/`AMD `/`ATI `/`Intel `). This mirrors the existing importer's
   `normalize_gpu_name`, which stores chip names without the vendor prefix.
2. **Vendor agreement.** GPU Ark `vendor` must map to the database manufacturer
   (`nvd→NVIDIA`, `amd→AMD`, `int→Intel`); AMD↔ATI is allowed to bridge the legacy ATI
   brand. No other cross-vendor match is accepted.
3. **Unique clock value.** All GPU Ark candidates for that normalized name + vendor must
   carry exactly one distinct `base_clock`. (Observed: every matched name had exactly one
   candidate row, so there were no competing distinct base values.)
4. **Range validity.** `100 ≤ base_clock ≤ 4000` MHz (the project's existing
   `gpu_validator` bounds).
5. **Independent corroboration.** The `boost_clock_mhz` already stored in the database
   must equal GPU Ark's `boost_clock` within 10 MHz (GHz-rounding tolerance). This proves
   the two records are the *same product/variant* and guards against conflating AIB
   board, mobile, or IGP variants that share a marketing name.
6. **Physical sanity.** Reject `base_clock > boost_clock_mhz`. (Equality is allowed —
   several workstation/no-boost parts legitimately have base = boost, and GPU Ark reports
   base = boost for them.)

A row that fails step 3 or 5 is **ambiguous**; a row that fails step 4 or 6 is
**invalid**; a row with no candidate is **unmatched**. None of these are applied.

### Why the corroboration step matters

On the 44 already-populated rows that were boost-confirmed the same product, GPU Ark's
`base_clock` matched the stored `core_clock_mhz` **44/44** (0 mismatches). On rows whose
stored boost clock does *not* match GPU Ark's boost (e.g. `Radeon R7 240`: stored
boost 780 vs GPU Ark boost 700; `GeForce MX350`: stored boost 1468 vs GPU Ark 937), the
record is a different clock variant and is excluded rather than guessed.

---

## 3. Exclusions for review

### 3.1 Ambiguous — boost clock does not corroborate identify (50)

All 50 are identical-normalized-name candidates whose stored `boost_clock_mhz` disagrees
with GPU Ark's `boost_clock` by more than 10 MHz. Full list with reasons is in
`04_database_patch.json` `excluded` and in `02_mapping_results.csv` (`status=ambiguous`).
Distribution: NVIDIA 22, AMD 17, Intel 11. Examples:

| hardware_id | name | mfr | stored boost | GPU Ark base / boost |
|---:|---|---|---:|---|
| 3569 | Radeon R7 240 | AMD | 780 | 650 / 700 |
| 4645 | GeForce GT 740M | NVIDIA | 895 | 980 / 1033 |
| 4991 | GeForce MX350 | NVIDIA | 1468 | 747 / 937 |
| 4339 | UHD Graphics 770 Mobile | Intel | 1500 | 300 / 1600 |

These are preserved, not filled.

### 3.2 Unmatched — no GPU Ark row with the same normalized name + vendor (4)

| hardware_id | name | mfr |
|---:|---|---|
| 4152 | Mobility Radeon HD 4250 IGP | ATI |
| 4771 | GeForce GT 740 OEM | NVIDIA |
| 5188 | B200 SXM 192 GB | NVIDIA |
| 5234 | RTX PRO 6000D Blackwell | NVIDIA |

### 3.3 Invalid values (0)

No source `base_clock` fell outside `[100, 4000]` MHz, and none exceeded the existing
`boost_clock_mhz`.

---

## 4. Safe-update profile

- Safe updates by manufacturer: **NVIDIA 514, AMD 365, Intel 133**.
- Source values used: GPU Ark `base_clock`, range **100 – 2,670 MHz**.
- Every target cell was verified `core_clock_mhz IS NULL` at generation time; updates are
  guarded `WHERE hardware_id = ? AND core_clock_mhz IS NULL`.
- No `hardware` identity, `benchmark_results`, `sources`, `external_identifiers`, or
  other table is written. No inserts/deletes.

---

## 5. Pre-apply database state

| Item | Value |
|---|---|
| SHA-256 | `503790258e1884b6478e64c52a2affd9f04eac8ae0e53f3d632be223312205a3` |
| Size | 921,600 bytes |
| `PRAGMA quick_check` | `ok` |
| hardware / CPU / GPU | 5,239 / 3,360 / 1,879 |
| cpu_specifications / gpu_specifications | 3,360 / 1,879 |
| benchmark_results / external_identifiers / sources | 1,040 / 3,575 / 3 |
| GPU core-clock coverage | 813 / 1,879 = 43.27 % |
| GPU benchmark rows / gaming rows | 0 / 0 |

---

## 6. Safety gate decision

- Legally suitable, locally present, documented source with clear CC BY 4.0 reuse: **yes**
  (GPU Ark). TechPowerUp bulk reuse: **blocked** and not used.
- Deterministic, reproducible matching with no fuzzy resolution: **yes**.
- Every proposed update is a NULL-only fill of a numeric field already bounded by the
  project validator: **yes**.
- Baseline hash matches the Batch 001 checkpoint: **yes**.

**Gate result: PROCEED to Phase 4 (apply).**
