# Stage 6 — Calibration Verification Report

**Tool**: `calibration_verify.py` (read-only, dev DB).
**Dev DB**: `C:\Users\user\spectra-local\data\dev\spectra_dev.db`

**Purpose**: verify that the suitability star anchors hard-coded in `suitability_service.py` match the actual percentile distribution of the benchmarked (Geekbench 7) population. Drift is *reported*, never silently rewritten.

## Families

| Family | Status | Max % err | Documented anchors (p10→p90) | Observed (p10→p90) |
|---|---|---:|---|---|
| single-core | ok | 9.36% | 667, 983, 1325, 1637, 2020 | 667, 1075, 1325, 1562, 2016 |
| multi-core | drift | 24.74% | 1409, 2809, 5001, 8017, 16347 | 1409, 3214, 5001, 7266, 12303 |

## Interpretation

- Anchors are the p10/p30/p50/p70/p90 score boundaries of the Geekbench 7 population, mapped to stars 1–5 in `docs/SCORING_METHODOLOGY.md`.
- `ok` means the documented anchors sit within 10% of the observed percentiles (no methodology change warranted).
- `drift` means the observed population moved away from the documented anchors — an honest signal that star boundaries may need review; it is never auto-corrected.
- This stage changes **no** scoring code: it is a verification/report pass only.