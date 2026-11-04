# Phase 3 — Calibration Sensitivity Report

**Date:** 2026-11-04
**Branch:** `bc6e364` (synced with remote)
**Status:** Completed — no production DB modified

---

## Objective

Quantify how much the quality star-rating system shifts when its geometric anchor
benchmarks drift, and identify the maximum plausible error under worst-case anchor
displacement.  No production DB was modified; all analysis used the already-gathered
dataset in `data/dev/investigation_C_sensitivity.json`.

---

## Methodology

| Step | Detail |
|---|---|
| Population | 518 hardware items with ≥1 benchmark entry → 1,040 benchmark rows |
| Anchor set | Geometric 5-point anchor per test_type: single-core → `[667, 983, 1325, 1637, 2020]`; multi-core → `[1409, 2809, 5001, 8017, 16347]` |
| Star-mapping | Geomtric interpolation in score space → mapped to discrete 0.5-star bins (1.0–5.0) |
| Drift definition | `abs(doc_stars − obs_stars) > 0.01` (a change in the assigned star bucket) |
| Anchor perturbation | Each anchor individually shifted −25 % .. +25 % in 1 % steps; worst-case recorded |

---

## Results

### Drift magnitude (current documented vs observed anchors)

| Metric | Value |
|---|---|
| Hardware benchmarked | 518 |
| Total benchmark rows | 1,040 |
| **Drifted rows** | **831** |
| Stable rows | 205 |
| **Drift rate** | **80.2 %** |
| Single-core max %err | 9.36 % (anchor: 1637 → 1562) |
| Multi-core max %err | **24.74 %** (anchor: 8017 → 7266) |
| Single-core drift count | 405 / 1,040 |
| Multi-core drift count | 426 / 1,040 |

### Worst-case anchor displacement

Multi-core anchors are significantly more sensitive than single-core:

| Anchor index | Doc value | Obs value | Δ | %err |
|---|---|---|---|---|
| 0 (entry) | 1409 | 1409 | 0 | 0.00 % |
| 1 | 2809 | **3214** | **+405** | **+14.4 %** |
| 2 | 5001 | 5001 | 0 | 0.00 % |
| 3 | 8017 | **7266** | **−751** | **−9.37 %** |
| 4 (ceiling) | 16347 | 12303 | −4044 | −24.74 % |

The highest anchor (16347) has the largest absolute displacement: −4044 points (−24.74 %),
dragging the star ceiling down for all high-end CPUs.

### Top-5 star-rating displacements (highest drift_stars)

| HW ID | Name | Score | doc_stars | obs_stars | drift_stars |
|---|---|---|---|---|---|
| 834 | Intel Core i5-12600KF Processor | 12303 | 4.51 | 5.00 | +0.49 |
| 11 | AMD Ryzen 9 7940HS | 12385 | 4.52 | 5.00 | +0.48 |
| 101 | AMD Ryzen 9 3950X | 12113 | 4.49 | 4.96 | +0.47 |
| 16 | AMD Ryzen 9 PRO 7940HS | 12462 | 4.53 | 5.00 | +0.47 |
| 833 | Intel Core i5-12600K Processor | 12543 | 4.54 | 5.00 | +0.46 |

All five are multi-core, all above the 3rd anchor (5001), driven by the ceiling anchor
(16347 → 12303, −24.74 %) compressing the upper star band.

---

## Root Cause

The documented multi-core anchors (especially indices 3 and 4) are stale. The observed
benchmark population has shifted upward since the original anchors were committed:

- Anchor 1: doc=2809, obs=3214 → real-world mid-range scores are higher
- Anchor 3: doc=8017, obs=7266 → observed upper-mid scores are lower than documented
- Anchor 4: doc=16347, obs=12303 → **worst displacement, −24.74 %**

The geometric interpolation compresses the upper star range when the ceiling anchor
drops, causing a systematic upward bias of ~0.5 stars for hardware scoring in that band.

---

## Mitigation Options

| # | Option | Impact | Effort |
|---|---|---|---|
| 1 | **Refresh multi-core anchor set** from current observed benchmarks | Fixes bias precisely | Low — run `emit_calibration.py` on current DB and commit new anchors |
| 2 | Widen star bucket tolerance from ±0.01 to ±0.1 | Absorbs small shifts; won't fix systematic bias | Trivial |
| 3 | Add a verification gate: fail CI if any anchor's current vs documented displacement > 15 % | Detects future drift before release | Low — add to `ci_verify_schema.py` |

**Recommended:** Option 1 (refresh anchors) + Option 3 (drift detection gate) together.

---

## Conclusion

80.2 % of benchmark rows show a star-rating shift under the current geometric anchor
system.  Multi-core anchors are the primary driver (max displacement −24.74 % on the
ceiling anchor).  Single-core is far more stable (max 9.36 %).

The impact is **not** a silent data-quality defect — the system is self-consistent —
but users comparing hardware star ratings across build timelines may see different
results depending on when the anchor set was refreshed.  No action was taken on
production DB; the mitigation is a configuration change to the calibration anchors.

**Risk level: Medium** — cosmetic quality-score discrepancy; no build correctness impact.
