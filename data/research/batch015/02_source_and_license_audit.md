# Batch 015 — Source & licence audit

Per-source findings for the nine registered sources, with the redistribution
status now stored on the registry. The findings are taken from the repository's
own prior research — `data/research/batch009/source_license_assessment.md` and
`data/research/batch010/source_permission_research.md` — not from assumption.
This is transparency, not legal advice; nothing was relicensed, and no
permission request was sent.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `clear` | A reuse licence is documented (share-alike may still apply). |
| `restricted` | Terms permit only personal/non-commercial use; redistribution needs permission. |
| `unknown` | Terms are inaccessible or grant nothing; **not** treated as permissive. |
| `unresolved` | Legacy data whose originating source is undocumented. |

## Per-source register

### 1 · PassMark CPU benchmark catalog (`benchmark-cpus.csv`) — `restricted`
- Publisher: PassMark Software Pty Ltd.
- Terms: reproduction is limited to unaltered material for personal,
  non-commercial or intra-organisation use; publication/commercial reuse needs
  permission. No bulk redistribution licence.
- Action: no further restricted PassMark data was imported in this batch.

### 2 · Geekbench Browser — Geekbench 7 CPU — `unknown`
- Publisher: Primate Labs Inc.
- Terms: not reachable during Batch 009/010 (HTTP 403/404); no reuse grant is
  documented in the repository.
- 1,040 benchmark rows depend on this source; they remain, honestly labelled as
  unknown rather than claimed as licensed.

### 3 · TechPowerUp GPU Database (`gpu_1986-2026.csv`) — `restricted`
- Publisher: TechPowerUp.
- Terms: `robots.txt` restricts to personal, non-commercial use and prohibits
  data mining/scraping and creating/providing cached or archived datasets
  without prior written permission.
- Action: no additional restricted TechPowerUp data was imported.

### 4 · GPU Ark GPU specifications & benchmarks — `clear` (CC BY 4.0)
- Publisher: GPU Ark.
- Licence: CC BY 4.0, documented in the repository (`data/raw/README.md`).
- Obligation: attribution, no share-alike.

### 5 · Wikipedia (English) — `clear` (CC BY-SA 4.0)
- Publisher: Wikimedia Foundation / Wikipedia contributors.
- Licence: CC BY-SA 4.0. Attribution **and** share-alike apply to
  redistributed derivatives.
- Coverage: 1,854 provenance rows (Batch 014's primary evidence source).

### 6 · Intel ARK (archived via Wayback Machine) — `unknown`
- Publisher: Intel Corporation.
- Terms: the Intel terms-of-use page returned HTTP 403 to automated access; no
  bulk reuse grant is documented.

### 7 · Unknown (source not documented in artifact) — `unresolved`
- Publisher: (none recorded).
- Origin: legacy Batch 008 placeholder for rows whose source artifact was not
  documented. Redistribution status is unresolved; must not be treated as
  licensed. 6 provenance rows.

### 8 · Intel ARK (`intel-cpus.csv` snapshot) — `unknown`
- Publisher: Intel Corporation.
- Redistributed via `felixsteinke/cpu-spec-dataset`, whose repository declares
  AGPL-3.0 for its **code only**, with no data licence. Intel ARK terms were
  inaccessible (403). No new Intel ARK data was imported.

### 9 · AMD product specifications (`amd-cpus.csv` snapshot) — `unknown`
- Publisher: Advanced Micro Devices, Inc.
- Redistributed via `felixsteinke/cpu-spec-dataset`. The AMD copyright page was
  accessed; no bulk data-reuse grant was found.

## What the batch deliberately did **not** do

- Did not relicense, remap or delete any source.
- Did not bulk-import more restricted PassMark or TechPowerUp data.
- Did not assume that public accessibility grants redistribution.
- Did not send permission requests on the user's behalf.

Machine-readable form: `_source_audit.json` (regenerate with
`build_source_audit.py`).
