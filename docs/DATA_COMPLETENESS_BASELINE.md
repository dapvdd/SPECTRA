# DATA_COMPLETENESS_BASELINE.md — Phase H Doc 1/8

**Generated**: 2026-10-28
**Mission**: SPECTRA Operation Data Completeness — Phase A (inventory) + Phase B (segment enrichment)
**Database**: local copy of deployed DB (`data/spectra.db`); no production server touched

---

## 1. What this document is

This is the **baseline** — the verified starting state of the hardware catalog before
Phase C spec enrichment begins. Everything in this document is derived from direct
database queries or structured source artifacts. Nothing is estimated.

---

## 2. Inventory (Phase A)

Source: `data/research/phase_a_inventory.py` → `docs/DATA_COMPLETENESS_MATRIX.json`

| Metric | Value |
|---|---|
| Total hardware rows | 5,380 |
| CPU rows | 3,501 |
| GPU rows | 1,879 |
| Unique manufacturers | 4 (Intel, AMD, NVIDIA, ATI) |
| Duplicate name+manufacturer groups | 0 |
| Out-of-range spec values | 0 |
| Conflicting specs (same field, same record) | 0 |
| Ext_id populated | 3,575 / 5,380 (66.5%) |

**Manufacturer distribution**:
- Intel: 2,959 rows (55.0%)
- AMD: 1,439 rows (26.7%)
- NVIDIA: 876 rows (16.3%)
- ATI: 106 rows (2.0%)

**Integrity findings**:
- No two records share identical (name, manufacturer) — the hardware identity key is sound.
- Zero spec values outside documented ranges were found during Phase A audit.

---

## 3. Segment classification (Phase B)

Source: `data/research/segment_classifier.py` → `backend/app/migrations/backfill_segment.py`

The segment field is filled **deterministically** from each manufacturer's published
product naming convention. A record is classified only when the token in its name
carries a single, unambiguous meaning. Where a token has different meanings across
families (e.g., bare `M` in `Quadro M2000` vs `FirePro M2000` vs `Tesla M2050`),
the classifier returns NULL rather than guess.

### 3.1 Classification rules (15 distinct rules)

| # | Rule | Token matched | Segment | Count |
|---|---|---|---|---|
| 1 | `server_family` | Xeon / EPYC / Tesla / Instinct | server | 1,209 |
| 2 | `firepro_S` | FirePro Sxxxx | server | (incl. above) |
| 3 | `firepro_D` | FirePro Dxxxx | server | (incl. above) |
| 4 | `cpu_mobile_suffix` | U / H / HX / HK / HS / E / M | mobile | 387 |
| 5 | `explicit_mobile_word` | " Mobile" / " Laptop" / " Mobility" | mobile | 245 |
| 6 | `workstation_family` | Quadro / FirePro (non-M) / Radeon Pro / Arc Pro / RTX A… | workstation | 238 |
| 7 | `nvidia_classic_M` | GeForce GTX/RTX NNNM | mobile | 109 |
| 8 | `maxq` | Max-Q / Max-Q | mobile | 53 |
| 9 | `amd_mobility` | "Mobility Radeon" | mobile | 31 |
| 10 | `amd_rx_M` | Radeon RX NNNM / HD NNNM | mobile | 26 |
| 11 | `amd_R_M` | Radeon R5/R7 M230… | mobile | (incl. above) |
| 12 | `firepro_M` | FirePro Mxxxx | mobile | 14 |
| 13 | `firepro_WM` | FirePro WxxxxM | mobile | 7 |
| 14 | `nvidia_MX` | NNNMX / MX450/550… | mobile | 14 |
| 15 | `radeonpro_XM` | Radeon Pro NNNxM | mobile | 3 |

### 3.2 Refused-by-design (NULL — deliberate non-classification)

| Token | Example | Reason refused |
|---|---|---|
| `P` suffix | `Core i5-6402P` (desktop) vs `i5-1240P` (mobile) | Ambiguous across Intel product lines |
| Bare `GeForce RTX/GTX` | `GeForce RTX 3060` | No mobile marker; could be desktop |
| Bare `M` + digits | `Quadro M2000` / `FirePro M2000` / `Tesla M2050` | Different segments from same token |
| `HD / UHD / Iris Graphics` | `Intel HD Graphics 620` | Not deterministically mobile |
| Apple Silicon | `Apple M1` | Unambiguous but unverified without cross-reference |

### 3.3 Result

| Segment | Count | % of total |
|---|---|---|
| mobile | 1,047 | 19.5% |
| server | 1,209 | 22.5% |
| workstation | 238 | 4.4% |
| **classified total** | **2,494** | **46.3%** |
| NULL (honest unknown) | 2,886 | 53.7% |
| **total** | **5,380** | **100%** |

---

## 4. Sources (post-Phase B)

| ID | Name | License | Status |
|---|---|---|---|
| 1 | PassMark CPU benchmark catalog | restricted | active |
| 2 | Geekbench Browser — Geekbench 7 CPU | unknown | active |
| 3 | TechPowerUp GPU Database | restricted | active |
| 4 | GPU Ark GPU specifications & benchmarks | CC BY 4.0 | clear |
| 5 | Wikipedia (English) | CC BY-SA 4.0 | clear |
| 6 | Intel ARK (Wayback) | unknown | active |
| 7 | Unknown (not documented) | — | legacy |
| 8 | Intel ARK (intel-cpus.csv snapshot) | unknown | active |
| 9 | AMD product specs (amd-cpus.csv) | unknown | active |
| **10** | **Derived from manufacturer naming conventions** | **clear** | **Phase B** |

Total provenance rows: 39,440 (up from 36,946 baseline)

---

## 5. Honest bounds (what is NOT in this catalog)

These are not gaps to fill by guessing. They are documented absences:

| Gap | Count | Reason |
|---|---|---|
| GPU benchmarks | 0 | No source met all licensing + provenance requirements |
| Prices / MSRP | 0 | Not ingested per mission rules |
| Fabricated specs | 0 | Any unknown field is NULL, never invented |
| CPU boost_clock_ghz | 1,076 missing (30.7% gap) | Source (Intel ARK) has unknown license status |
| CPU process_node_nm | 1,028 missing (29.4% gap) | Same; also architecture inference needs provenance note |
| GPU length_mm | 1,113 missing (59.2% gap) | Source (TechPowerUp) is restricted; GPU Ark incomplete |
| GPU interface | 1,030 missing (54.8% gap) | Same restriction |

---

## 6. Idempotence & integrity guarantees

After Phase B backfill:

- ✅ 0 classifiable-but-NULL records (re-running classifier on current DB: 0 new classifications)
- ✅ 0 segment-value overrides (column was NULL for all 5,380 before batch; additive only)
- ✅ 0 provenance/segment conflicts
- ✅ 0 orphan provenance rows (segment provenance rows only exist for classified records)
- ✅ 0 duplicate segment provenance rows (one per classified record)
- ✅ 703 backend tests passing, 572 frontend tests passing

---

## 7. Files created this session

```
data/research/segment_classifier.py          # Core classifier (15 rules, deterministic)
data/research/test_segment_classifier.py     # 29 unit tests (all passing)
backend/app/migrations/backfill_segment.py  # Idempotent apply + provenance writer
data/research/verify_backfill.py             # Post-apply spot-checks
data/research/verify_completeness.py         # Idempotence + consistency checker
```

---

## 8. Next steps (Phase C)

Phase C (spec enrichment) can safely address:
- Fields where a **clear-licensed source** exists (GPU Ark for interface on NVIDIA/AMD)
- Fields derivable from **architecture → process node** mapping (documented as inference)

Phase C must stop and report if:
- The only viable source has `restricted` or `unknown` license status
- The field requires a credentialed API or paid dataset

Current blockers (do not proceed without user authorization):
- **Benchmark ingestion**: requires a source meeting all 4 criteria (license, provenance, accessibility, reproducibility) — none identified
- **Pricing ingestion**: requires licensed/priced data not available to this session
