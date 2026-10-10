# Batch 010 — Source & Permission Research

Date: 2026-10-10

This continues Batch 009's source/licensing work. It separates (a) facts from
repository artifacts, (b) facts verified from authoritative external pages
that were genuinely accessed, and (c) unresolved assumptions / missing
permissions. It is not legal advice. No permission request was sent on the
user's behalf and no restricted dataset was imported.

## 1. Facts supported by repository artifacts

- `sources` (ids 1–9) and the base-import provenance persisted in batch 009
  cover PassMark (`benchmark-cpus.csv`), Geekbench Browser 7, TechPowerUp GPU
  Database, GPU Ark, Wikipedia, Intel ARK (Wayback cross-check), the batch-008
  "Unknown" placeholder, and the batch-009 Intel ARK / AMD snapshot sources.
- `felixsteinke/cpu-spec-dataset` (the distribution used for the CPU exports)
  declares AGPL-3.0 for its code; its `dataset/*.csv` files carry no data
  licence. (LICENSE + README in `cpu-spec-dataset-main.zip`.)
- Batch 009 reconciliation assigned all 3,575 CPU external identifiers to the
  Intel ARK / AMD snapshot sources with value-level evidence (see
  `identifier_source_audit.md` and `id_audit_results.json`).
- Primate Labs / Geekbench reuse has never been documented in the repository.

## 2. Facts verified from authoritative external pages (accessed 2026-10-10)

| Publisher | URL accessed | Access on | Finding |
|---|---|---|---|
| PassMark Software | `https://www.passmark.com/legal/disclaimer.php` | 2026-10-10 | Terms restrict reproduction to unaltered material for personal, non-commercial use or use within an organisation; reproduction in whole/part for general publication or commercial purposes requires permission. |
| PassMark Software | `https://www.cpubenchmark.net/` | 2026-10-10 | Homepage re-confirms data is user-submitted + internal testing; footer links the Disclaimer/Terms; no bulk-reuse grant. |
| TechPowerUp | `https://www.techpowerup.com/robots.txt` | 2026-10-10 | Contents for personal, non-commercial use; data mining/scraping prohibited without prior written permission; explicitly prohibits "creating or providing archived or cached data sets containing our content to others" and commercial purposes; contact `w1zzard@techpowerup.com`. |
| Primate Labs | `https://www.primatelabs.com/legal/` | 2026-10-10 | **HTTP 403** — terms not accessible; no conclusion drawn. |
| Geekbench | `https://www.geekbench.com/legal/` | 2026-10-10 | **HTTP 404** — not accessible; no conclusion drawn. |
| OpenBenchmarking.org | `https://openbenchmarking.org/` | 2026-10-10 | **HTTP 403** — result-data licence still unverifiable. |
| felixsteinke/cpu-spec-dataset | `https://github.com/felixsteinke/cpu-spec-dataset` | 2026-10-10 | AGPL-3.0 (code); README documents the origin sites of each dataset CSV. |

## 3. Per-source standing (unchanged from batch 009 unless noted)

| Source | Redistribution licence | Attribution obligation | Next step |
|---|---|---|---|
| PassMark (`benchmark-cpus.csv`) | Restricted (personal/non-commercial; permission for publication) | Retain copyright notice in unaltered copies only | Written permission before any publication/export |
| TechPowerUp (`gpu_1986-2026.csv`, incl. 44 legacy clocks) | Restricted (personal, non-commercial; no dataset creation) | Not established | Written permission from `w1zzard@techpowerup.com`; keep 44 values flagged, do not redistribute |
| Intel ARK / AMD exports | Unknown (`intel`/`amd` snapshots); no grant documented | Unknown | Written confirmation from the publishers before redistribution |
| Geekbench Browser 7 (`processor-benchmarks.csv`) | Unknown (terms inaccessible) | Unknown | Manual review of Primate Labs terms; written confirmation before redistribution |
| GPU Ark | **CC BY 4.0** (documented in repo: `data/raw/README.md`) — this is the one established permissive licence | Attribution required | Surface attribution in any redistribution (existing batch-008 records) |
| Wikipedia (English) | **CC BY-SA 4.0** (documented) | Attribution + share-alike | Legal confirmation of share-alike handling before export (unchanged) |

## 4. 44 legacy TechPowerUp GPU clock values

Recommendation carried forward from batch 009 and confirmed: **retain flagged
for review, restrict from any future redistribution pending written
permission**. The values remain in the database; their provenance rows record
the reuse restriction in `license_notes`. Redistribution (dataset export,
published copy, bundled artifact) must first obtain TechPowerUp's written
permission. No permission has been requested or received; nothing is
represented as resolved.

## 5. Draft permission-request template

A reuse permission-request template is provided in
`permission_request_template.md`. It is a draft only — nothing was sent.

## 6. Open items and evidence still needed

1. **Primate Labs (Geekbench)**: a reachable terms page or a written answer.
2. **PassMark**: written permission for any publication/commercial reproduction.
3. **Intel / AMD**: written confirmation that the exported specification values
   may be redistributed.
4. **TechPowerUp**: written permission for the 44 legacy clock values (and, if
   wanted later, a small attributed gaming-benchmark set).
5. **OpenBenchmarking**: manual browser review of result-data licence (site
   403-blocks automated tooling).

No new gaming benchmark dataset was found that satisfies publisher +
verifiable licence + methodology + reproducible structure; the position from
batch 009 is unchanged. No gaming benchmark data was added.