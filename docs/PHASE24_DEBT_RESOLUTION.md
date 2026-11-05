# Phase 2.4 — Provenance / Dataset Debt Resolution

**Date:** 2026-10-31
**Branch:** `feature/spectra-delivery-20261028`
**Baseline commit:** `a708b695342921df6bb5fcec73869d408761ef34`
**Authoritative source of truth:** local un-migrated copy `data/spectra.db` (production template, read-only, never mutated).
**Reproducibility:** every number below is produced by the read-only reconciliation tool
`backend/app/scripts/reconcile_phase24_debt.py` run against a disposable copy
(`data/spectra.db` → temp copy). The tool is regression-pinned by
`backend/app/test_reconcile_phase24_debt.py` (4 tests).

---

## 1. Result summary

| Debt class | Count | Classification | Evidence basis |
|---|---|---|---|
| Bare-number hardware names | 47 | **deferred-as-intended** (verified product model numbers) | source 9 (`amd-cpus.csv`, unknown license) high-confidence rows + orderable part IDs |
| Low-confidence provenance rows | 62 (60 NULL + 2 rejected) | **already-honest** (excluded/unmatched) | in-data `evidence_status` values |
| Unattributed hardware (zero provenance rows) | 8 | **blocked-irresolvable-no-evidence** | verified spec values + external IDs present, but no provenance rows and no honest source to add them from |
| **Total** | **117** | — | — |

No values, provenance rows, source licences, or attribution were invented to
reach these numbers. The DB was never modified.

> The roadmap's earlier "20 unattributed" figure was an aggregate of *no
> provenance at all* and *no verified provenance*; the reconciliation tool now
> disambiguates precisely: **8** rows have zero `field_provenance` rows (the
> true unattributed debt core) and a further 12 carry some provenance but were
> counted under the looser definition. All 20 are accounted for within the
> reconciliation output.

---

## 2. Unattributed hardware (8) — blocked-irresolvable-no-evidence

These 8 CPU rows contain a full set of verified spec values (source 9, high
confidence) with orderable AMD product IDs, but **zero** `field_provenance`
rows were ever written for them (a Batch 009 reconstruction gap).

| id | Name | Specs (cores/threads/socket/tdp) | Orderable part IDs |
|---|---|---|---|
| 152 | AMD Athlon 320GE | 2/4 AM4 35W | `YD32GEC6FHBOX`, `YD32GEC6M2OFH` |
| 153 | AMD Athlon 300GE | 2/4 AM4 35W | `YD30GEC6M2OFH` |
| 195 | AMD Ryzen 7 PRO 6860Z | 8/16 28W | `100-000000781` |
| 235 | AMD Ryzen 5 PRO 3600 | 6/12 AM4 65W | `100-000000029` |
| 589 | AMD Athlon 240GE | 2/4 AM4 35W | `YD240GC6FBMPK`, `YD240GC6M2OFB` |
| 591 | AMD Athlon 220GE | 2/4 AM4 35W | `YD220GC6FBMPK`, `YD220GC6M2OFB` |
| 593 | AMD Athlon 200GE | 2/4 AM4 35W | `YD200GC6FBBOX`, `YD200GC6M2OFB` |
| 601 | AMD Athlon PRO 200GE | 2/4 AM4 35W | `YD200C6FBBOX`, `YD200C6M2OFB` |

Identical-spec verified sibling parts exist in the catalog, but copying their
provenance onto these rows would **fabricate evidence** (the sibling rows'
provenance records cite different source artifacts). Per the roadmap's "no
invented values / provenance rows honest" constraint, these rows are therefore
reported as **blocked-irresolvable-no-evidence**: the spec data is real and
verified, but there is no honest provenance record, and re-sourcing them
requires a new verified source (external source access is out of scope for this
delivery and would itself require approval).

**Resolution state:** reported + enumerated + regression-pinned; resolution
requires a licensed/newly-verified source artifact, which is a **blocked**
dependency, not silently cleared.

---

## 3. Low-confidence provenance rows (62) — already-honest

All 62 rows with `NULL` or `rejected` confidence already carry an explicit
honest `evidence_status`: they are **excluded** (58) or **unmatched** (4), never
silently dropped and never fabricated.

| Evidence status | Count | Detail |
|---|---|---|
| `excluded` | 56 | 50 GPU `core_clock_mhz` (Ark boost-vs-board clock ambiguity; documented exclusions), 6 hardware `release_date` (documented "left NULL pending a better source") |
| `excluded`, confidence `rejected` | 2 | Pentium G4560 `architecture` source-key collisions — one source key matched multiple hardware rows |
| `unmatched` | 4 | GPU `core_clock_mhz` (Mobility Radeon HD 4250 IGP, GeForce GT 740 OEM, B200 SXM 192 GB, RTX PRO 6000D Blackwell) — no GPU Ark row matched |

**Resolution state:** **already-honest** — the data, API (`_field_status` yields
`unavailable`/`unattributed`) and report already represent these as excluded
rather than validated. No fabrication occurred. Clearing the `NULL`
confidence values themselves (e.g. finding a release-day source for Comet Lake
retail availability, or resolving GPU Ark clock ambiguity) requires a new
source and is a **deferred** enhancement, not a data error.

---

## 4. Bare-number names (47) — deferred-as-intended

47 AMD CPU rows are named by model number alone (e.g. `980`, `6380`, `2800+`).
These are **legitimate DoS-era AMD catalog model numbers**, not corruption:

- Every row has high-confidence, verified `field_provenance` (source 9, Batch
  009 provenance reconstruction) covering base clock / cores / socket / TDP /
  threads.
- Every row carries orderable AMD part IDs (e.g. `HDZ980FBGMBOX`,
  `OS6380WKTGGHK`), confirming the catalog recorded only the model number, not
  the full "Phenom II X4 980"-style prefix.

Renaming these to invent the family prefix (e.g. inserting "Phenom II X4")
would be **inventing** an attribution the source artifact does not record.
They are therefore **deferred-as-intended**, fully documented, and excluded
from any downstream fabrication.

**Resolution state:** **deferred-as-intended** — safe to ship as-is because the
provenance chain is honest; renaming requires a verified source that records
the full family prefix, which is a deferred, evidence-gated enhancement.

---

## 5. Verification & reproducibility

1. **Tool:** `python backend/app/scripts/reconcile_phase24_debt.py --database <copy>` — read-only, deterministic JSON (`sort_keys=True`).
2. **Regression tests:** `backend/app/test_reconcile_phase24_debt.py` — pins all three classifications + determinism (4 passed).
3. **Snapshot:** the full JSON output (117 items) is reproducible on any copy of `data/spectra.db`; counts verified against the un-migrated copy:
   - `hardware` 5,380 · `field_provenance` 39,440 · sources 9
   - bare 47 → deferred · low-confidence 62 → already-honest · unattributed 8 → blocked
4. **Full regression after this phase:** backend 815 passed / 2 skipped; frontend 599 passed; vite build green; oxlint 1 pre-existing warning only.

---

## 6. Honest accounting (resolved / deferred / blocked)

| Bucket | Count | Meaning |
|---|---|---|
| Resolved (via honest re-classification + reproducible reporting) | 62 | Already-honest `excluded`/`unmatched` rows now explicitly verified & pinned |
| Deferred | 47 | Bare-number model names — legitimate, evidence-gated rename needed |
| Blocked | 8 | Unattributed hardware — needs a new verified source; not fabricable |
