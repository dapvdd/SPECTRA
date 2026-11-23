# M3.1 SKU Verification Manifest

**Date**: 2026-11-23. Machine-readable source of truth: `data/research/m31/manifest_{ram,storage,psu}.json` (fail-closed `validate_manifest` clean) and `data/research/m31/02_resolution_report.json`.

## Verified SKUs (49)

Evidence contract per SKU: MPN seen verbatim on the cited official document; per-SKU URL; every populated spec field carries APPROVED FieldEvidence with a source_reference locator, an allowed match_method, and an access date. All match_methods below are `spec-table-row` unless marked otherwise.

### RAM — Corsair (32, access 2026-11-22, corsair.com/p/<MPN>)

| MPN | Family | Variant | Spec (capacity/speed/modules/voltage) |
|---|---|---|---|
| CMK16GX5M1B5200C40 | Vengeance | module-1x16-ddr55200 | 16GB DDR5-5200, 1×16, 1.25V |
| CMK32GX5M1B5200C40 | Vengeance | module-1x32-ddr55200 | 32GB DDR5-5200, 1×32, 1.25V |
| CMK16GX5M1B5600C40 | Vengeance | module-1x16-ddr55600 | 16GB DDR5-5600, 1×16, 1.25V |
| CMK32GX5M1B5600C40 | Vengeance | module-1x32-ddr55600 | 32GB DDR5-5600, 1×32, 1.25V |
| CMK16GX5M1D6000Z38 | Vengeance | module-1x16-ddr56000 | 16GB DDR5-6000, 1×16, 1.35V |
| CMK32GX5M1B6000Z38 | Vengeance | module-1x32-ddr56000 | 32GB DDR5-6000, 1×32, 1.35V |
| CMK16GX5M2B5200C40 | Vengeance | kit-2x16-ddr55200 | 32GB (2×16) DDR5-5200, 1.25V |
| CMK32GX5M2B5200C40 | Vengeance | kit-2x32-ddr55200 | 64GB (2×32) DDR5-5200, 1.25V |
| CMK16GX5M2B5600C40 | Vengeance | kit-2x16-ddr55600 | 32GB (2×16) DDR5-5600, 1.25V |
| CMK32GX5M2X5600C32 | Vengeance | kit-2x32-ddr55600 | 64GB (2×32) DDR5-5600, 1.35V |
| CMK16GX5M2B6000C38 | Vengeance | kit-2x16-ddr56000 | 32GB (2×16) DDR5-6000, 1.35V |
| CMK32GX5M2X6400C38 | Vengeance | kit-2x32-ddr56400 | 64GB (2×32) DDR5-6400, 1.40V |
| CMK64GX5M2B5200C40 | Vengeance | kit-2x64-ddr55200 | 128GB (2×64) DDR5-5200 |
| CMK64GX5M2B6000C40 | Vengeance | kit-2x64-ddr56000 | 128GB (2×64) DDR5-6000 |
| CMK64GX5M2B6400C32 | Vengeance | kit-2x64-ddr56400 | 128GB (2×64) DDR5-6400 |
| CMK64GX5M2L5600C40 | Vengeance | kit-2x64-ddr55600 | 128GB (2×64) DDR5-5600 |
| CMT32GX5M2B6000C30 | Dominator Titanium | kit-2x16-ddr56000 | 32GB (2×16) DDR5-6000 |
| CMT64GX5M2B6000C40 | Dominator Titanium | kit-2x32-ddr56000 | 64GB (2×32) DDR5-6000 |
| CMT32GX5M2X6600C32 | Dominator Titanium | kit-2x16-ddr56600 | 32GB (2×16) DDR5-6600 |
| CMT64GX5M2X6600C32 | Dominator Titanium | kit-2x32-ddr56600 | 64GB (2×32) DDR5-6600 |
| CMT32GX5M2B6400C32 | Dominator Titanium | kit-2x16-ddr56400 | 32GB (2×16) DDR5-6400 |
| CMT64GX5M2B6400C32 | Dominator Titanium | kit-2x32-ddr56400 | 64GB (2×32) DDR5-6400 |
| CMK16GX4M1A2666C16 | Vengeance LPX | module-1x16-ddr42666 | 16GB DDR4-2666 |
| CMK32GX4M2A2666C16 | Vengeance LPX | kit-2x16-ddr42666 | 32GB (2×16) DDR4-2666 |
| CMK16GX4M2A2666C16 | Vengeance LPX | kit-2x8-ddr42666 | 16GB (2×8) DDR4-2666 |
| CMK16GX4M1E3200C16 | Vengeance LPX | module-1x16-ddr43200 | 16GB DDR4-3200 |
| CMK32GX4M2E3200C16 | Vengeance LPX | kit-2x16-ddr43200 | 32GB (2×16) DDR4-3200 |
| CMK16GX4M2D3600C18 | Vengeance LPX | kit-2x8-ddr43600 | 16GB (2×8) DDR4-3600 |
| CMK32GX4M2D3600C16 | Vengeance LPX | kit-2x16-ddr43600 | 32GB (2×16) DDR4-3600 |
| CMK16GX4M1Z3600C18 | Vengeance LPX | module-1x16-ddr43600 | 16GB DDR4-3600 |
| CMV16GX4M1A2400C16 | Value Select | module-1x16-ddr42400 | 16GB DDR4-2400 |
| CMV16GX4M1A2666C18 | Value Select | module-1x16-ddr42666 | 16GB DDR4-2666 |
| CMV8GX4M1A2400C16 | Value Select | module-1x8-ddr42400 | 8GB DDR4-2400 |

(The exact per-SKU spec/evidence values are in `manifest_ram.json`; this table summarizes.)

### STORAGE — WD / Kingston (10, access 2026-11-23)

| MPN | Family | Variant | Read/Write MB/s | Evidence |
|---|---|---|---|---|
| WDS100T2X0E-00BCA0 | WD_BLACK SN850X | nvme-1024gb-pcie4.0x4 | 7300 / — | sandisk.com product page (per-SKU selector) |
| WDS200T2X0E-00BCA0 | WD_BLACK SN850X | nvme-2048gb-pcie4.0x4 | 6600 / — | sandisk.com product page |
| WDS400T2X0E-00BCA0 | WD_BLACK SN850X | nvme-4096gb-pcie4.0x4 | 7300 / — | sandisk.com product page |
| SKC3000S/512G | Kingston KC3000 | nvme-512gb-pcie4.0x4 | 7000 / 3900 | kingston.com KC3000 datasheet PDF |
| SKC3000S/1024G | Kingston KC3000 | nvme-1024gb-pcie4.0x4 | 7000 / 7000 | kingston.com KC3000 datasheet PDF |
| SKC3000D/2048G | Kingston KC3000 | nvme-2048gb-pcie4.0x4 | 7000 / 7000 | kingston.com KC3000 datasheet PDF |
| SKC3000D/4096G | Kingston KC3000 | nvme-4096gb-pcie4.0x4 | 7000 / 7000 | kingston.com KC3000 datasheet PDF |
| SA400S37/240G | Kingston A400 | sata-ssd-240gb-sataiii | 500 / 350 | kingston.com A400 datasheet PDF |
| SA400S37/480G | Kingston A400 | sata-ssd-480gb-sataiii | 500 / 450 | kingston.com A400 datasheet PDF |
| SA400S37/960G | Kingston A400 | sata-ssd-960gb-sataiii | 500 / 450 | kingston.com A400 datasheet PDF |

SN850X write values are present in `manifest_storage.json` only where the cited page documents them; unspecified fields stay NULL.

### PSU — Corsair (7, access 2026-11-23, corsair.com/ww/en/p/psu/<MPN>/…)

| MPN | Family | Variant | Wattage | Efficiency | Modular |
|---|---|---|---|---|---|
| CP-9020197-NA | RMx (2021) | 550w-gold-mod | 550 | 80 PLUS Gold | fully |
| CP-9020198-NA | RMx (2021) | 650w-gold-mod | 650 | 80 PLUS Gold | fully |
| CP-9020199-NA | RMx (2021) | 750w-gold-mod | 750 | 80 PLUS Gold | fully |
| CP-9020200-NA | RMx (2021) | 850w-gold-mod | 850 | 80 PLUS Gold | fully |
| CP-9020251-NA | RMx SHIFT | 750w-gold-mod | 750 | 80 PLUS Gold | fully |
| CP-9020252-NA | RMx SHIFT | 850w-gold-mod | 850 | 80 PLUS Gold | fully |
| CP-9020253-NA | RMx SHIFT | 1000w-gold-mod | 1000 | 80 PLUS Gold | fully |

RMx 2021: ATX12V v2.4 / EPS 2.92. RMx SHIFT: ATX12V v3.1 / EPS 2.92. Per-SKU PCIe/12VHPWR connector counts are not published on the SHIFT pages; the claimed-spec fields (`pcie_8pin_count`, `pcie_12vhpwr`) were NOT carried into the verified spec — they stay NULL rather than inherit family-level claims.

## MOTHERBOARD — none verified (100 UNRESOLVED)

ASUS/MSI/Gigabyte/ASRock product pages are JS-rendered/generic; no per-SKU MPN evidence was obtainable. All 100 motherboard candidates remain UNRESOLVED with notes (`02_resolution_report.json`); no manifest file exists because no verified SKU was produced.

## Unresolved candidates (394)

Documented per candidate with source-access reasons in `02_resolution_report.json` (family notes reproduced in the research notes files). Headline causes: JS-rendered vendor catalogs (Samsung, Seagate, WD, Seasonic, be quiet!, Cooler Master, Thermaltake, G.Skill, ADATA, TeamGroup, board vendors), WAF/403 (Crucial), discontinued/retired pages (Kingston NV2/A2000/KC2500, EVGA PSUs), and inventory candidates whose exact variant is absent from current vendor lineups (RAM 11 REPLACED are documented in the same report).
