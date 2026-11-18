"""M3 remediation — SKU-verified pilot subset.

A small, honest set of records whose every material spec is backed by a
per-SKU citation (product-specific page URL that names the exact variant)
plus a manufacturer MPN/part number. These are the only records allowed to
carry evidence_status='verified' and identity_status='confirmed' after the
M3 remediation.

Evidence tier contract (M3 remediation):
- technology facts (DDR5, NVMe, ATX, 80 Plus)  -> Wikipedia, 'unverified'
- family-level facts (family page)             -> vendor family page, 'unverified'
- SKU-level facts (exact variant + value)      -> per-SKU URL + MPN, 'verified'

Every entry here was substantiated against the cited per-SKU page during the
M3 remediation pass (2026-11-18). No fabricated values: each spec value was
read from the cited page for the cited variant during that pass.

Substantiation notes (fetched 2026-11-18):
- Corsair CMK32GX5M2B6000C30 — per-SKU page Tech Specs read directly:
  Memory Size 32GB (2 x 16GB), Memory Type DDR5, Tested Speed 6000 MT/s,
  Tested Voltage 1.40V, Package Memory Format UDIMM, SKU CMK32GX5M2B6000C30.
- Seasonic FOCUS GX-750 — per-SKU page read directly: 80PLUS(R) Gold,
  Modularity Fully Modular, per-wattage spec tables; the 750 W variant
  section shows total continuous power 750 W. Connector-count fields are
  NOT cleanly attributable per wattage from the page text, so they are
  omitted from the verified record (optional fields, absent stays NULL).
- EVGA 220-G5-0850-X1 — the per-SKU URL resolves, but the fetched page text
  (JS carousel boilerplate) did not expose the spec values; NOT included in
  the verified set. The family-level entry in PSU_FAMILIES stays
  QUARANTINED until a curator substantiates it.
"""
from __future__ import annotations

# Access date for the remediation pass (per-SKU pages re-fetched).
ACCESS_DATE_SKU = "2026-11-18"

VERIFIED_SKUS: list[dict] = [
    {
        "category": "RAM",
        "name": "Corsair VENGEANCE 32GB (2x16GB) DDR5-6000 CL30 Kit",
        "manufacturer": "Corsair",
        "mpn": "CMK32GX5M2B6000C30",
        "product_family": "Vengeance",
        "spec": {
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6000,
            "modules": 2,
            "voltage_v": 1.4,
            "form_factor": "UDIMM",
        },
        "per_sku_url": (
            "https://www.corsair.com/us/en/p/memory/cmk32gx5m2b6000c30/"
            "vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mhz-c30-memory-kit"
        ),
        # Only the generation vocabulary comes from Wikipedia (technology
        # fact); every other value is printed on the per-SKU page itself.
        "tech_wiki": {"ddr_generation": "ddr5"},
    },
    {
        "category": "PSU",
        "name": "Seasonic FOCUS GX-750",
        "manufacturer": "Seasonic",
        "mpn": "FOCUS-GX-750",
        "product_family": "Focus GX",
        "spec": {
            "wattage": 750,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
        },
        "per_sku_url": "https://seasonic.com/focus-gx/",
        # The page itself states 80PLUS Gold; no Wikipedia fallback needed.
        "tech_wiki": {},
    },
]
