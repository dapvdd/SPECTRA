# M3 Phase 0 — Source Feasibility (RAM / Storage / Motherboard / PSU)

**Date**: 2026-11-16
**Branch**: `feat/m3-catalog-expansion`
**Method**: Repository evidence (batch009/010/015 research) + fresh web verification of
the Wikipedia copyright policy on 2026-11-16 (Wikipedia:Copyrights, policy page,
"Permission is granted to copy, distribute and/or modify Wikipedia's text under the
terms of the Creative Commons Attribution-ShareAlike 4.0 International License" —
attribution + share-alike required; images are separately licensed and are NOT used).

## 1. Verdict per category (Gate 0)

| Category | Viable legal path demonstrated? | Path | Verdict |
|---|---|---|---|
| RAM | **Yes** | Curated records citing Wikipedia CC BY-SA 4.0 pages (DDR4/DDR5 SDRAM, per-product articles) + official product pages as corroboration; imported via owner-manual provenance (batch_no=0, evidence_status=verified) | **Cleared for curated import** (bounded rate) |
| Storage | **Yes** | Same as RAM (per-product Wikipedia articles exist for major NVMe/SATA/HDD lines) | **Cleared for curated import** |
| Motherboard | **Yes** | Same as RAM (board families documented on Wikipedia; sockets/chipsets documented exhaustively) | **Cleared for curated import** |
| PSU | **Yes** | Same as RAM (80 Plus programme documented; unit families documented) | **Cleared for curated import** |
| (CPU/GPU) | Existing | GPU Ark CC BY 4.0 bulk dataset already used by Batch 018 | unchanged, out of M3 scope |

No category is blocked. No bulk `clear`-licensed dataset for the 4 new categories
was found (see §3), so automated bulk import is NOT claimed; the demonstrated path
is curated/manual import with verifiable citations through the existing
owner-manual provenance mechanism (`ensure_owner_manual_source`, `batch_no=0`,
`evidence_status='verified'`), extended in Phase 2 with a declarative adapter so
the workflow is reproducible end-to-end.

## 2. Source matrix

Legend: Access = mechanism used in M3. Automation = permitted automated extraction?
Permission evidence = where the licence/term statement is recorded.

### 2.1 Wikipedia (English)

| Attribute | Value |
|---|---|
| Official URL | https://en.wikipedia.org/ (+ REST API https://en.wikipedia.org/api/rest_v1/) |
| Source type | Community encyclopedia (tertiary), CC BY-SA 4.0 + GFDL dual-licensed text |
| Data fields available | Product family/model names, DDR generations, speed/MT/s vocabularies, voltage ranges, JEDEC standards, socket/chipset families, interface types, form factors, 80 Plus levels |
| License / access conditions | **CC BY-SA 4.0** (text). Attribution + share-alike required. Verified 2026-11-16 from Wikipedia:Copyrights policy page |
| Automation permission | Yes — Wikimedia explicitly publishes API access for reuse; the Wikimedia ToS permit API consumption within rate limits |
| Rate limits | REST API: polite usage; Wikimedia asks bulk users to set a descriptive User-Agent and stay within documented limits (no hard published number for light use) |
| Stability | High (API versioned); article text evolves → revision-ID is stored in provenance |
| Model/MPN availability | **Partial** — product families and technologies well covered; specific MPNs inconsistently present → MPN optional; identity per `M3_IDENTITY_RULES.md` |
| Expected data quality | Medium-high for categorical/family facts; low for per-SKU exact numbers → per-SKU numbers only imported with an explicit per-product citation |
| Permission evidence | `data/research/batch010/source_permission_research.md` (§2: Wikipedia CC BY-SA 4.0 verified), fresh 2026-11-16 fetch of Wikipedia:Copyrights (this file, §header) |

**Share-alike handling**: SPECTRA stores *factual specification values* (numbers,
enum tokens, names). Facts are not copyrightable expression; where Wikipedia
*expressive text* is used to justify a curated fact, the provenance row records the
source URL + revision and SPECTRA's own catalog data pages carry the CC BY-SA
attribution notice (implemented in Phase 7 UX attribution panel). This satisfies
BY; SA applies to *derivative expressive content*, which the catalog's factual
records are not — the determination is documented rather than silently assumed
(see `M3_SOURCE_REGISTRY.md` §legal notes).

### 2.2 Official manufacturer product pages (Intel, AMD, ASUS, MSI, Gigabyte, ASRock, G.Skill, Corsair, Crucial, Samsung, Western Digital, Kingston, Seasonic, be quiet!, EVGA)

| Attribute | Value |
|---|---|
| Official URL | e.g. https://www.gskill.com/product/…, https://www.corsair.com/…, https://www.asus.com/motherboards/… |
| Source type | Manufacturer spec sheets (primary) |
| Data fields available | Exact per-SKU: MPN, capacity, speed, timings, voltage, form factor; socket/chipset; wattage/efficiency; interface/protocol; connector inventory |
| License / access conditions | **Unknown / not documented for redistribution** — pages are visible publicly but carry no dataset licence; site ToS generally reserve content |
| Automation permission | **Not established** → treated as unknown |
| Rate limits | Unpublished |
| Stability | Medium (marketing pages change/rename) |
| Model/MPN availability | **Excellent** (MPN is authoritative here) |
| Expected data quality | Highest per-SKU |
| Permission evidence | batch009/batch010 assessments: "unknown — terms inaccessible or grant nothing; not treated as permissive" |
| **M3 decision** | Used **as corroboration for curated manual entries** (a human reads the page and records the value + URL as the citation in provenance). **No automated crawling of these domains in M3.** Corroboration citations point at the official page URL; the import mechanism stays the owner-manual path |

### 2.3 GPU Ark (existing, out of M3 category scope)

CC BY 4.0, clear (batch010 §2, registry id 4). GPU-only dataset; not extended to
the 4 new categories (no RAM/storage/MB/PSU data published there). Listed in the
registry for completeness; zero M3 ingestion from it.

### 2.4 Prohibited sources (carried forward)

| Source | Status | M3 behaviour |
|---|---|---|
| PassMark | restricted | Never imported; not cited as justification for any value |
| TechPowerUp | restricted | Never imported; not cited |
| Geekbench Browser | unknown | Benchmarks only; out of M3 scope |
| Any "spec scraper" aggregator sites | unknown | Not used |

## 3. Bulk-dataset search result (honest negative)

Searches over the repository research and fresh web verification found **no
explicitly licensed bulk dataset** (CC0/CC BY/ODbL or equivalent) covering RAM,
storage, motherboard, or PSU SKUs. Datasets that superficially appear viable were
rejected:

- GitHub "hardware datasets" aggregations — no data licence declared → unknown.
- Retail-feed exports (Amazon/CDI/Best Buy APIs) — require commercial agreements
  not available to this project → not obtainable in M3.
- OpenBenchmarking/Phoronix test data — benchmarks, not specs; licence OK for
  results but no per-SKU spec coverage → out of scope.

Consequence: M3 does **not** claim an automated bulk path; it claims the
mission's fallback (path 4: manually curated records with verifiable official
citations) and delivers the pilot through it. The numeric target (400) is a
stretch goal; data integrity outranks count.

## 4. Acquisition architecture impact (feeds Phase 2)

- One declarative adapter per *mechanism*, not per manufacturer:
  1. `WikipediaCuratedAdapter` — curated rows citing Wikipedia article revisions
     (license clear; attribution + SA note recorded per record).
  2. `ManualOfficialCitationAdapter` — curated rows citing official product
     pages (license_status of the citation recorded as `unknown`; the *record*
     is imported as owner-manual with `evidence_status='verified'` because a
     human verified the value against the cited official page at access time;
     the source row keeps its honest `unknown` status).
- Both flow through the existing `SourceLicenseGate` semantics: the gate
  applies to *automated bulk extraction*; owner-manual entries are the
  documented fallback and are labelled as such end-to-end (UX shows
  "Owner-curated, cited" with the citation link).
- Rate limits/bounded concurrency apply to any future automated adapter; the
  two M3 adapters are human-in-the-loop and perform no network fetches at
  import time (URLs are stored as citations, not fetched by the pipeline).

## 5. Gate 0 evidence summary

| Gate 0 requirement | Status |
|---|---|
| ≥1 viable + legally usable acquisition path per category | **PASS** (curated Wikipedia CC BY-SA 4.0 + official-page-cited manual entries, §2.1/§2.2) |
| No inference of permission from public visibility | **PASS** (manufacturer pages explicitly stay `unknown`; no crawling) |
| Prohibited sources excluded | **PASS** (§2.4) |
| Evidence links | This file §2 + `M3_SOURCE_REGISTRY.md` + batch009/010/015 research files |
