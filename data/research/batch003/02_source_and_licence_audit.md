# Batch 003 — Source & Licence Audit

**Goal:** expand CPU metadata using only sources whose reuse terms are clear and
compatible, and whose values can be matched deterministically.

Sources were inspected in the priority order required by the brief: official
manufacturer sources first, then existing local snapshots, then reliable secondary
sources. Terms were verified rather than taken from earlier descriptions.

---

## 1. Sources considered

### 1.1 Intel ARK (`ark.intel.com`) — official — **NOT USABLE here**

Intel's official processor database is the ideal authority for Intel architecture,
process node and clocks. In Batch 001 the live ARK pages returned **HTTP 403**; only
archived (Wayback) copies of two SKUs could be read. ARK provides no bulk export and its
site terms do not grant a reuse licence for building a dataset. Bulk automated retrieval
would also run against the site's access controls. **Rejected**: not accessible, and no
reuse grant; the brief forbids bypassing access restrictions.

### 1.2 AMD product pages (`amd.com`) — official — **NOT USABLE here**

AMD CPU/GPU product pages render specifications client-side (JavaScript); an
unauthenticated server-side fetch returns a shell with no specification text (verified in
Batch 001). There is no official machine-readable bulk dataset and no reuse grant.
**Rejected**.

### 1.3 PassMark / CPUWorld (the project's `source_id 1`) — **NOT USABLE here**

This is the origin of the existing CPU rows (`benchmark-cpus.csv`), but the file is **not
present locally** in `data/raw/` (only GPU datasets are). The site does not grant a bulk
reuse licence, and re-acquiring it was out of scope. **Rejected** for this batch.

### 1.4 TechPowerUp GPU database — **NOT USABLE** (GPU only)

Already rejected for bulk reuse in Batch 002: `robots.txt` permits only personal,
non-commercial use and prohibits data mining / dataset creation. It is GPU-only and
irrelevant to CPU fields. **Rejected**.

### 1.5 GPU Ark — **NOT APPLICABLE** (GPU only)

CC BY 4.0 and usable for GPUs (Batch 002), but contains no CPU data.

### 1.6 Wikidata — **USABLE but not adopted this batch**

CC0 (public domain); a clean licence. It carries structured CPU properties, but pulling
3,000+ records via SPARQL and matching them reliably was a larger, riskier build than the
chosen path given the time budget. Recorded as a future option.

### 1.7 Wikipedia microarchitecture articles — **USED (CC BY-SA 4.0)**

Wikipedia text and tables are licensed **CC BY-SA 4.0** and are freely reusable with
attribution and share-alike. Crucially, Wikipedia has one article per CPU
microarchitecture/platform, whose model tables list that platform's processors — so the
article's subject *is* the architecture, making the mapping deterministic and auditable.
Batch 001 already used this source and stored local table extracts (all 44 of its
architecture proposals came from it).

---

## 2. Chosen source and evidence

**Source:** English Wikipedia microarchitecture articles (CC BY-SA 4.0), attributed as
`Wikipedia (CC BY-SA 4.0)` with the exact article URL per value.

Local evidence stored in the repository (so a reviewer can re-verify without fetching):

- Batch 001 extracts (already present): `data/research/batch001/sources/*.tables.txt`
- Batch 003 extracts (fetched during this batch):
  `data/research/batch003/sources/*.tables.txt`, with
  `data/research/batch003/sources/provenance.json` recording article URL, access date,
  licence and table counts for each page.

Articles used: `Alder Lake`, `Raptor Lake`, `Rocket Lake`, `Coffee Lake`, `Comet Lake`,
`Haswell_(microarchitecture)`, `Ivy_Bridge_(microarchitecture)`, `Kaby Lake`,
`Sandy_Bridge_(microarchitecture)`, `Skylake_(microarchitecture)`,
`Broadwell_(microarchitecture)`, `Ice_Lake_(microprocessor)`, `Tiger Lake`,
`Nehalem_(microarchitecture)`, `Westmere_(microarchitecture)`,
`Cannon_Lake_(microprocessor)`, `Whiskey Lake`, `Zen 2`, `Zen%2B` (Zen+), `Zen 3`,
`Zen 4`.

### Provenance/licence handling

- Every value in `03_evidence_table.csv` and `05_database_patch.json` records
  `source_name`, `source_url` (article), and a stable `source_reference`
  (`<extract file>::TABLE <n>`). Attribution is preserved in the committed artifacts.
- The extracts are factual specification tables; no prose is reproduced.

---

## 3. Reliability gate (what is and is not imported)

The source tables have merged, multi-row headers (hybrid P/E core columns, embedded GPU
clock columns, configurable-TDP columns). Values were validated against the database
before import:

| Field | Extraction reliability | Decision |
|---|---|---|
| architecture (article subject) | node cross-check: **390 agree / 0 disagree** (Intel) | **import** (all) |
| release_date | full-date parse: 7 agree / **0 disagree** | **import** (full dates only; quarter/year-only ignored) |
| process_node_nm (AMD) | family fact via confirmed architecture | **import** (Zen family only) |
| process_node_nm (Intel) | already 2,356/2,694 populated | not a source-supported gap |
| boost_clock_ghz | parse validation: 187 agree / **96 disagree** | **excluded** (unreliable) |
| tdp_w | parse validation: 369 agree / **8 disagree** | **excluded** (unreliable) |

Because boost/TDP extraction from the merged tables was demonstrably error-prone
(wrong-column capture on hybrid parts; T-variant TDP ambiguity), **no boost or TDP values
are imported** — correctness over row count. This is the honest state of the source; the
gap remains documented and open.

### Verification step that changed the source mapping

While validating, the file named `wiki_Zen_2B.tables.txt` was found to be the **Zen+**
article, not Zen 2: its infobox reads `Launched April 2018`, `Technology node 12 nm`,
`Successor Zen 2`, and its tables list Pinnacle Ridge / Picasso parts (Ryzen 3200G/3400G,
Athlon 300GE) which are Zen+ (12 nm). The mapping was corrected from `Zen 2` to `Zen+`
(and the AMD node for those rows from 7 nm to 12 nm) before any import. (The real Zen 2
article is `wiki_Zen_2.tables.txt`.) This is exactly the kind of mislabel the brief warns
about.

---

## 4. Rejected alternatives — summary

| Source | Why rejected |
|---|---|
| Intel ARK | HTTP 403 / no bulk reuse grant / access controls |
| AMD product pages | JS-rendered shell; no reuse grant |
| PassMark / CPUWorld | dataset not local; no bulk reuse grant |
| TechPowerUp | robots.txt forbids bulk dataset creation |
| GPU Ark | GPU only |
| boost/TDP from Wikipedia tables | unreliable per-model extraction (validated) |

**Conclusion:** Wikipedia microarchitecture articles (CC BY-SA 4.0) pass the licence and
reliability gates for architecture, release date, and AMD family process node, and are
used with per-value provenance. No blocked source is used.
