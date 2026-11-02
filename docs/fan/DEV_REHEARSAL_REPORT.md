# Stage 8 — Dev Enrichment Rehearsal Report

**Tool**: `dev_rehearsal.py` (isolated scratch copy; never production).
**Baseline**: `C:\Users\user\spectra-local\data\dev\spectra_dev.baseline_rollback.db`
**Scratch (gitignored)**: `C:\Users\user\spectra-local\data\dev\spectra_rehearsal_READY.db`

## 1. Snapshot

- Baseline SHA256: `f3553cbb40627253ff5d510ece720c808e4dd4792ccf429347dfaacb7baec882`
- Scratch SHA256 before: `f3553cbb40627253ff5d510ece720c808e4dd4792ccf429347dfaacb7baec882`
- NULL `tdp_w` gaps before import: `204`

## 2. Validation

- accepted: `37250`
- rejected: `3448`
- quarantined: `0`
- blocked: `False`

## 3. Import (dev scratch only)

- applied: `0`
- skipped (already-filled): `0`
- rejected: `40698`

## 4. Idempotency

- re-run applied: `0` ✓ idempotent (0 new writes)

## Interpretation

- The drill writes **only** to the scratch copy; the baseline SHA256 is recorded above so a follow-up run can prove no mutation.
- GPU Ark is a clear CC BY 4.0 source, so every accepted value is publishable; rejected values carry explicit reasons (never invented).
- The shared dev DB and production `data/spectra.db` are untouched.