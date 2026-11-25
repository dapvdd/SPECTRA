# M3.2 Task 1 — Motherboard Verified Acquisition (progress)

Date: 2026-11-23 · Branch: feat/m32-compatibility-intelligence · Worktree: C:\Users\user\spectra-m32

## Result

- `data/research/m32/manifest_motherboard.json`: **13 MATCHED / 87 UNRESOLVED / 0 INVALID** (100 candidates), fail-closed validation clean (`validate_manifest` = no blockers; `load_manifest` re-validates on reload).
- `data/research/m32/02_resolution_report_motherboard.json`: MOTHERBOARD counters = 12 MATCHED + 1 REPLACED + 87 UNRESOLVED.
- All 13 verified SKUs carry: non-empty MPN (ASUS eShop / ASUS webshop / distributor P/N citations), per_sku_url (official ASUS techspec/ROG spec page), 9 per-field APPROVED FieldEvidence entries (match_method `spec-table-row`, access_date 2026-11-23), diffs-vs-claim notes, cpu_support text in notes (never a spec column).

## Verified MPNs (page + P/N citations)

| idx | Board | MPN | Spec page |
|---|---|---|---|
| 238 | PRIME B650-PLUS | 90MB1BS0-M0AAY0 | asus.com techspec |
| 239 | TUF Gaming B650-PLUS WIFI | 90MB1BZ0-M0AAY0 | asus.com techspec |
| 240 | ROG Strix B650E-F Gaming WiFi | 90MB1BQ0-M0AAY0 | rog.asus.com spec |
| 248 | PRIME Z790-P | 90MB1CK0-M1EAY0 | asus.com techspec |
| 253 | PRIME B760-PLUS | 90MB1EF0-M1AAY0 | asus.com techspec |
| 259 | PRIME B650M-A WIFI II | 90MB1EG0-M0EAY0 | asus.com techspec |
| 261 | PRIME X670-P | 90MB1BU0-M0EAY0 | asus.com techspec |
| 266 | TUF Gaming Z790-Plus WIFI | 90MB1D80-MVAAY0 | asus.com techspec |
| 270 | TUF Gaming B650M-Plus WIFI | 90MB1BF0-M0EAY0 | asus.com techspec |
| 274 | PRIME B760M-A | 90MB1EK0-M1EAY0 | asus.com techspec |
| 278 | TUF Gaming B760-Plus WIFI | 90MB1ER0-MVAAY0 | asus.com techspec |
| 283 | PRIME A620M-K | 90MB1F40-M0EAY0 | asus.com/za techspec |
| 289 | PRIME B650M-A II | 90MB1EH0-M0EAY0 | asus.com techspec |

## Claimed-vs-page discrepancies (page authoritative, noted per SKU)

- 238: m2_slots 3→2, pcie_slots 5→4 (physical slot count policy)
- 239: m2_slots 4→3
- 240: pcie_slots 5→4
- 248: m2_slots 4→3, pcie_slots 5→4
- 253: pcie_slots 5→4
- 261: max_ram_gb 192→256, m2_slots 4→3, sata_ports 4→6
- 270: max_ram_gb 192→256
- 274: max_ram_gb 192→256
- 278: pcie_slots 5→4
- 283: sata_ports 2→4

## Blocked (UNRESOLVED with access notes; no fabrication)

- MSI (22 cands): msi.com HTTP 403 to polite fetch.
- Gigabyte (19): gigabyte.com HTTP 403.
- ASRock (16): Incapsula WAF (200 but WAF iframe, no content).
- ASUS blocked slugs (15): 249, 281, 286, 292, 296, 298, 301, 304, 306, 310, 315, 322, 328, 331, 335 — pages redirect to series landing (no spec table) on global + regional mirrors; earlier partial extractions for 301/310/331/335 failed re-read validation and were excluded per no-inference rule.
- 261 special case: family verified (PRIME X670-P = X670 chipset) but candidate claims X670E → REPLACED with explanatory note (no inference of X670E support from X670 data).

Target was ≥25 verified; actual 13 (ASUS-only reachability). Per mission fallback clause: actual verified count reported, other phases proceed. No data fabricated.
