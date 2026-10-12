# Batch 014 — Source & Licence Audit

**Goal:** add modern CPU records using only sources whose reuse terms are clear and
whose values can be matched deterministically, and to distinguish manufacturer-verified
facts from third-party copies.

Sources were inspected in priority order: official manufacturer sources first, then
reusable open datasets, then reliable secondary sources. Terms were verified rather
than taken from earlier batch descriptions.

---

## 1. Sources considered

### 1.1 Intel ARK (`ark.intel.com`) — official — **NOT USABLE here**

The authoritative Intel processor database. It is not the source of the existing
catalog and offers no bulk reuse licence; Batches 009/010 recorded that its
redistribution rights are unknown. Re-scraping it for 141 SKUs would also require
re-acquiring data whose terms have not been cleared. **Rejected** (unknown
redistribution rights per the Batch 009/010 source assessment).

### 1.2 AMD product specification pages (`amd.com`) — official — **NOT USABLE here**

The AMD product specification pages are JS-rendered and, like Intel ARK, were
assessed in Batches 009/010 as having unknown redistribution rights. The existing
`amd-cpus.csv` snapshot (source id 9) does not contain the modern parts targeted
here. **Rejected.**

### 1.3 PassMark CPU benchmark catalog (source id 1) — **NOT USABLE**

The original catalog source. PassMark does not grant bulk dataset redistribution and
its licensing was explicitly called out in the brief as restricted. **Rejected;
excluded from production.**

### 1.4 TechPowerUp GPU database (source id 3) — **NOT APPLICABLE**

GPU-only; `robots.txt` forbids bulk dataset creation (Batch 002). **Rejected.**

### 1.5 English Wikipedia — **USED** (CC BY-SA 4.0, source id 5)

Wikipedia text and tables are published under the Creative Commons
Attribution-ShareAlike 4.0 International licence (CC BY-SA 4.0). Reuse is permitted
with attribution and share-alike. It has already been the accepted source for
Batches 001, 003, 004 and 005 (source id 5, `Wikipedia (English)`).

For this batch two kinds of pages were used:

* **Article pages** with per-SKU specification tables — `Raptor Lake`
  (14th-generation desktop section), `Meteor Lake`, `Arrow Lake (microprocessor)`,
  `Lunar Lake`.
* **`Template:` pages** whose product tables are transcluded into the
  microarchitecture articles — `Template:AMD Ryzen 9000 Series`,
  `Template:AMD Ryzen 8000 desktop APUs`, `Template:AMD Ryzen 8000 series`,
  `Template:AMD Ryzen Mobile 8040 series`, `Template:AMD Ryzen Mobile 8045 series`,
  `Template:AMD Ryzen AI Mobile 300 series`. These are the canonical, machine-readable
  product tables for the Zen 4/Zen 5 mobile and desktop-APU families.

Raw wikitext was fetched with `action=raw` and parsed locally.

---

## 2. Evidence captured and licence handling

All fetched sources are stored under `data/research/batch014/sources/`, together with
`manifest.json`, which records for every file: page title, canonical URL, raw URL,
byte length, SHA-256, licence (`CC BY-SA 4.0`) and the batch tables that use it.

Attribution is preserved at three levels:

1. `sources/manifest.json` — file-level URL + licence + attribution statement;
2. every candidate/patch row — `source_title`, `source_url`, `source_section`;
3. every `field_provenance` row — `source_id=5`, `source_url`, `license_name='CC BY-SA 4.0'`,
   an `attribution` string naming Wikipedia contributors and share-alike, and the
   `access_date` (2026-10-12).

Only factual specification values are imported; no article prose is reproduced.
Because derived data is committed as part of the repository, the share-alike term is
satisfied by keeping the source note attached to the derived values.

### Reliability gate (what is and is not imported)

| Field | Evidence basis | Decision |
|---|---|---|
| name / manufacturer | product-table row identity | **import** (canonicalised, see `04_...`) |
| architecture | the page's subject / table section | **import** (all) |
| cores / threads | P-core + E-core counts summed from the table | **import** (all) |
| base_clock_ghz | table "Base" column | **import** (all) |
| boost_clock_ghz | table "Turbo"/"Boost" column (**max boost**) | **import** (all) |
| tdp_w | table "TDP"/"Base power" column (**default/base power**, not configurable ceiling) | **import** (all) |
| release_date | full launch date only | **import** only when a full date exists (102/141) |
| process_node_nm | single-node families only | **import** for single-tile/single-node parts (76/141); NULL for multi-tile Intel |
| socket | desktop parts with a documented socket | **import** for Raptor Lake Refresh / Arrow Lake-S / AM5 (73/141); NULL for mobile |

Nothing is interpolated or inferred from a name pattern. Where the source gives only
a platform window (e.g. Meteor Lake `Q4'23`) or no date column (Lunar Lake), the
`release_date` is left NULL rather than fabricated.

---

## 3. Excluded / deferred (documented leads, not imported)

| Item | Reason |
|---|---|
| Intel `Processor 300` / `300T` (Raptor Lake Refresh table) | not `Core`-branded; outside the requested modern Core/Ultra/Ryzen scope |
| Intel `Core 7 245HX` (Arrow Lake-HX table) | non-`Ultra` Core 7 branding; inconsistent with the Core Ultra convention and possibly a distractor row |
| Arrow Lake "Plus" 2026 refresh tables | future/recently-announced platform, announcement vs launch date ambiguity; deferred |
| AMD Ryzen 9000 PRO / mobile 9000-series PRO tables | not part of the requested target set; the transient PRO rows seen in templates were not committed |
| Intel ARK / AMD.com | unknown redistribution rights (Batch 009/010) — documented lead only |
| PassMark / TechPowerUp | restricted bulk redistribution — documented lead only |

`05_database_patch.json` contains only the guarded, verified inserts; the three
excluded table rows are recorded in `_candidates.json` under `excluded`.

**Conclusion:** English Wikipedia (CC BY-SA 4.0, source id 5) passes the licence and
reliability gates for the modern CPU families targeted here, and is used with
per-value provenance. No restricted source is used.
