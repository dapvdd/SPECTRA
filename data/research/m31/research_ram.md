# RAM research notes (M31) — verified via official manufacturer pages only.

## Method
- Candidates: `data/research/m31/01_candidate_inventory.csv` (128 RAM rows, 14 families by manufacturer×family).
- Evidence: official pages only (corsair.com, kingston.com, gskill.com, crucial.com, teamgroupinc.com, adata.com). Corsair per-SKU pages fetched at `corsair.com/p/<MPN>` (page shows `SKU:` field + full Tech Specs table; MPN and spec values transcribed from that page). Aggregators/retailers unused.
- `source_doc_revision` = corsair.com product page, accessed 2026-11-22.

## Results (2026-11-22)
- 128 candidates -> 32 MATCHED (all with MPN + per_sku_url + APPROVED evidence for every spec field), 96 UNRESOLVED.
- MATCHED by family:
  - Corsair Vengeance (DDR5): 14 — CMK…GX5M…pages, speeds 5200/5600/6000/6400, single & dual.
  - Corsair Dominator Titanium: 6 — consolidated into Dominator Platinum RGB SKUs (CMT…GX5M…) on current corsair.com.
  - Corsair Vengeance LPX (DDR4): 9 — CMK…GX4M… pages.
  - Corsair Value Select (DDR4): 3 — only 1-module CMV…M1A… DIMMs still listed on corsair.com.
- UNRESOLVED families (12): G.Skill Trident Z5 RGB / Trident Z5 Neo RGB / Ripjaws S5 (gskill.com is JS-rendered, no MPN text served), Kingston Fury Beast / Fury Beast DDR4 / Fury Renegade (render compare-only, no per-variant MPNs; raw fetch 403), Crucial Pro / Crucial Basics (WAF block), TeamGroup T-Force Delta RGB (product path 404), ADATA XPG Lancer (per-SKU page not retrievable). Corsair Value Select 2-module kits + Vengeance 1x16@6400 single + a few Vengeance variants no longer present on corsair.com.

## Fail-closed handling
- MATCHED: MPN seen verbatim on official page; spec copied from that page's Tech Specs (Memory Size, Tested Speed, Tested Voltage, Memory Type, Package Memory Format). Claimed-vs-page diffs reconciled to official values and noted.
- UNRESOLVED: commented why (JS-render / WAF / 404 / SKU not present). No MPNs invented.

## Validation
`validate_manifest()` on `manifest_ram.json` -> "MANIFEST OK" (no blockers).
