# Batch 009 — Source & License Assessment

Date: 2026-10-10

Scope: the three original base-import data sources (CPU specifications, GPU
specifications, CPU benchmarks) and the 44 legacy TechPowerUp GPU clock
values. Web research is separated from repository evidence. URLs are recorded
only where they were actually accessed today (2026-10-10); automated fetches
that returned 403/404 are listed as blocked and no conclusion is drawn from
them. This is not legal advice.

---

## 1. Summary table

| Dataset | Publisher | Repository evidence | Web evidence (2026-10-10) | Redistribution rights |
|---|---|---|---|---|
| `intel-cpus.csv` (Intel ARK snapshot) | Intel; redistributed by `felixsteinke/cpu-spec-dataset` | Repo licence = AGPL-3.0 (code); no data licence declared | Intel terms page → **403 blocked** | unknown |
| `amd-cpus.csv` (AMD specs export) | AMD; redistributed by felixsteinke | Repo README documents it as an AMD.com export | AMD copyright page accessed — no data-reuse grant found | unknown |
| `benchmark-cpus.csv` (PassMark catalog) | PassMark Software Pty Ltd | Source row 1 exists; no licence field pre-batch-009 | PassMark Disclaimer/Terms accessed — personal, non-commercial use only; permission required for publication/commercial reproduction | restricted |
| `gpu_1986-2026.csv` (TechPowerUp GPU DB snapshot) | TechPowerUp | batch 002/008 recorded the robots.txt restriction | robots.txt accessed — personal, non-commercial only; data-mining, dataset creation, commercial use prohibited without written permission | restricted |
| `processor-benchmarks.csv` (Geekbench 7 Browser catalog) | Primate Labs (Geekbench Browser) | Source row 2 exists; no licence documented | primatelabs.com/legal → **403**; geekbench.com/legal → **404** | unknown |
| `cpuworld-cpus.csv` | CPU-World | Named in `docs/DATA_SOURCES.md` | not accessed | not imported (no DB cell reconciles); unknown |

Rule followed: **a web page being publicly reachable does not grant a
redistribution licence, and an unknown licence is never treated as
permissive.**

## 2. PassMark (cpubenchmark.net) — restricted

Accessed `https://www.passmark.com/legal/disclaimer.php` (2026-10-10). The
terms state:

> "You may download, display, print and reproduce this material in unaltered
> form only (retaining this notice) for your personal, non-commercial use or
> use within your organisation."

> "Information on the Site may not be reproduced in whole or in part for
> general publication or commercial purposes without the permission of the
> Host."

Conclusion: no bulk redistribution licence. Reproducing the catalog or its
values for any general publication or commercial purpose requires PassMark's
permission. Attribution obligation not established beyond retaining the
copyright notice in unaltered reproductions.

## 3. TechPowerUp — restricted; permission contact documented

Accessed `https://www.techpowerup.com/robots.txt` (2026-10-10). The robots
file states content is "made available for your personal, non-commercial
use", that data mining / scraping is "prohibited without prior written
permission", and explicitly prohibits "creating or providing archived or
cached data sets containing our content to others" and "any commercial
purposes". Contact offered: `w1zzard@techpowerup.com`.

Conclusion: no redistribution licence. This applies to the 44 legacy GPU
clock values and to the base `gpu_1986-2026.csv` import as a whole.

## 4. Intel ARK / AMD specification pages — unknown

- Intel: the terms-of-use page returned HTTP 403 to automated access on
  2026-10-10; no reuse grant is documented in the repository either. Intel
  ARK has, in every prior batch (001, 008), been treated as having "no bulk
  reuse grant documented".
- AMD: `https://www.amd.com/en/corporate/copyright` was accessed; no
  data-reuse grant for bulk export content was found on that page.

Neither is inferred to be permissive. Both are "unknown" and further review
(or written confirmation) is required before any redistribution.

## 5. Geekbench / Primate Labs — unknown (not accessible)

Both `https://www.primatelabs.com/legal/` (403) and
`https://www.geekbench.com/legal/` (404) were unreachable from automated
tooling on 2026-10-10. No conclusion is drawn about the terms. The browser
catalog values are treated as unknown-for-redistribution.

## 6. felixsteinke/cpu-spec-dataset — code AGPL-3.0, data unlicensed

Verified from the downloaded archive `cpu-spec-dataset-main.zip` (LICENSE
file, AGPL-3.0) and from the GitHub page (2026-10-10). The AGPL applies to
the repository code. The `dataset/*.csv` files carry no separate data-licence
notice; the README attributes each file to its origin site. Therefore the
licence status of the dataset content is determined by the origin sites
above, not by AGPL.

## 7. Impact on Batch 009

- This batch persists **provenance metadata only** (which source artifact and
  cell supports a stored value). Provenance attribution is not a
  redistribution right, so recording it does not require a redistribution
  licence.
- Every persisted base-import provenance row carries the relevant
  restricted/unknown licence status in `license_notes`.
- No base-import artifact was re-imported or redistributed. No dataset was
  bulk-imported. No values changed.

## 8. TechPowerUp 44-value disposition recommendation

Recommendation: **restrict from future redistribution pending written
permission, while retaining the values in the database flagged for review.**

Rationale:
- The values are already stored; retaining them does not cause a new
  publication. Removing them would be destructive without a clear technical or
  legal justification, and 16 of 44 were independently cross-checked against
  NVIDIA official product pages (batch 001/008).
- The robots.txt restriction is explicit and current: any future
  redistribution (dataset export, published copy, bundled artifact) must first
  obtain written permission from TechPowerUp (`w1zzard@techpowerup.com`).
- The current state already implements "retain while clearly flagged": the 44
  provenance rows carry the reuse restriction in `license_notes`. The added
  requirement is a positive gate on redistribution, not a deletion.

No legal disposition is represented as resolved; permission is genuinely not
yet obtained.