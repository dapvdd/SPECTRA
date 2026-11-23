"""Build data/research/m31/manifest_psu.json (M31 Task 4-continuation).

MATCHED entries only for Corsair RMx (2021) and RMx SHIFT SKUs whose official
corsair.com product pages were read this session (per-SKU URL
corsair.com/ww/en/p/psu/<MPN>/... shows the MPN + full tech-spec table).
Every other PSU candidate is UNRESOLVED with a source-access note.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\spectra-m31")
sys.path.insert(0, str(ROOT))

from backend.app.catalog.acquisition.manifest import (  # noqa: E402
    FieldEvidence,
    VerifiedSKU,
    new_manifest,
    save_manifest,
)

ACCESS = "2026-11-23"
INV = ROOT / "data/research/m31/01_candidate_inventory.json"
OUT = ROOT / "data/research/m31/manifest_psu.json"

rows = json.loads(INV.read_text(encoding="utf-8"))
psu = [r for r in rows if r["category"] == "PSU"]


def ev(field, value, source_value, locator, url, method="spec-table-row"):
    return FieldEvidence(
        spec_field=field, normalized_value=value, source_value=source_value,
        source_evidence_location=locator, curator_decision="APPROVED",
        source_url=url, match_method=method, access_date=ACCESS,
    )


# Verified 2026-11-23 from official corsair.com product pages (per-SKU URL
# https://www.corsair.com/ww/en/p/psu/<MPN>/...; "Continuous Power W",
# "80 PLUS Efficiency", "Modular" read from each page's tech-spec table).
RMX2021 = {
    "344": {"mpn": "CP-9020197-NA", "watt": 550,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020197-NA/"
                   "rmx-series-rm550x-550-watt-80-plus-gold-fully-modular-"
                   "atx-psu-cp-9020197-na"},
    "345": {"mpn": "CP-9020198-NA", "watt": 650,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020198-NA/"
                   "rmx-series-rm650x-650-watt-80-plus-gold-fully-modular-"
                   "atx-psu-cp-9020198-na"},
    "346": {"mpn": "CP-9020199-NA", "watt": 750,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020199-NA/"
                   "rmx-series-rm750x-750-watt-80-plus-gold-fully-modular-"
                   "atx-psu-cp-9020199-na"},
    "347": {"mpn": "CP-9020200-NA", "watt": 850,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020200-NA/"
                   "rmx-series-rm850x-850-watt-80-plus-gold-fully-modular-"
                   "atx-psu-cp-9020200-na"},
}
RMXSHIFT = {
    "348": {"mpn": "CP-9020251-NA", "watt": 750,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020251-NA/"
                   "rm750x-shift-80-plus-gold-fully-modular-atx-power-"
                   "supply-cp-9020251-na"},
    "349": {"mpn": "CP-9020252-NA", "watt": 850,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020252-NA/"
                   "rm850x-shift-80-plus-gold-fully-modular-atx-power-"
                   "supply-cp-9020252-na"},
    "350": {"mpn": "CP-9020253-NA", "watt": 1000,
            "url": "https://www.corsair.com/ww/en/p/psu/CP-9020253-NA/"
                   "rm1000x-shift-80-plus-gold-fully-modular-atx-power-"
                   "supply-cp-9020253-na"},
}

UNRESOLVED_NOTES = {
    ("Corsair", "RMx"): "RMx 1000/1200/1600W (Platinum/ATX3.1 variants) not "
    "present on current corsair.com RMx listing; no per-SKU page found",
    ("Corsair", "RMx Shift"): "covered by RMx SHIFT entries (750/850/1000W); "
    "no separate family page",
    ("Corsair", "RMx Shift 1200"): "RM1200x SHIFT page not retrievable "
    "(corsair.com JS catalog)",
    ("Corsair", "RMx 1000 Shift"): "alias of RM1000x SHIFT — verified at "
    "index 350 (Corsair RMx Shift family)",
    ("Corsair", "RMx 1300 Shift"): "RM1300x SHIFT page not retrievable",
    ("Corsair", "RMx 650 Shift"): "alias of RM650x SHIFT — no SHIFT SKU at "
    "650W exists in Corsair's current catalog; candidate variant unverifiable",
    ("Corsair", "RMx 750 Shift"): "alias of RM750x SHIFT — verified at "
    "index 348",
    ("Corsair", "RMx 1600i"): "RM1600i page not retrievable (JS catalog); "
    "no per-SKU evidence",
    ("Seasonic", "Focus GX"): "seasonic.com product pages JS-rendered; "
    "per-SKU URLs not retrievable",
    ("Seasonic", "Focus GX-ATX 3"): "seasonic.com JS-rendered; per-SKU "
    "URLs not retrievable",
    ("Seasonic", "Focus SGX"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime TX"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime PX"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 650"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 750"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 850"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 1000"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 1200"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 1300"): "seasonic.com JS-rendered",
    ("Seasonic", "Focus GX 1600"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime TX 1300"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime PX 650"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime PX 750"): "seasonic.com JS-rendered",
    ("Seasonic", "Prime PX 850"): "seasonic.com JS-rendered",
    ("be quiet!", "Pure Power 12 M"): "bequiet.com JS-rendered (unit-list "
    "page); per-SKU BN-number pages not retrievable",
    ("be quiet!", "Pure Power 12 M 650"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 12 M 750"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 12 M 850"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 12 M 1000"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 12 M 1200"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 12 M 1300"): "bequiet.com JS-rendered",
    ("be quiet!", "Dark Power 13"): "bequiet.com JS-rendered",
    ("be quiet!", "Dark Power 13 750"): "bequiet.com JS-rendered",
    ("be quiet!", "Dark Power 13 850"): "bequiet.com JS-rendered",
    ("be quiet!", "Dark Power 13 1000"): "bequiet.com JS-rendered",
    ("be quiet!", "Dark Power Pro 13 1300"): "bequiet.com JS-rendered",
    ("be quiet!", "Smart BX3"): "bequiet.com JS-rendered",
    ("be quiet!", "Pure Power 11 FM 650"): "bequiet.com JS-rendered; "
    "discontinued lines partly removed",
    ("Cooler Master", "MWE Gold 850 V2"): "coolermaster.com catalog pages "
    "JS-rendered; per-SKU MPY-… pages not retrievable",
    ("Cooler Master", "MWE White V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "Vengeance Gold"): "coolermaster.com JS-rendered",
    ("Cooler Master", "V750 Gold V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "V850 Gold V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "V650 Gold V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "V550 Gold V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "MWE Gold 650 V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "MWE Gold 750 V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "MWE Gold 1000 V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "MWE Gold 1050 V2"): "coolermaster.com JS-rendered",
    ("Cooler Master", "MWE Gold 1250 V2"): "coolermaster.com JS-rendered",
    ("EVGA", "SuperNOVA G5"): "evga.com support/sales pages retired after "
    "EVGA PSU exit; no official per-SKU page available",
    ("EVGA", "SuperNOVA GT 1000"): "evga.com pages retired; no official "
    "per-SKU page available",
    ("EVGA", "SuperNOVA 650 G7"): "evga.com pages retired",
    ("EVGA", "SuperNOVA 750 G7"): "evga.com pages retired",
    ("EVGA", "SuperNOVA 850 G7"): "evga.com pages retired",
    ("EVGA", "SuperNOVA 1000 G7"): "evga.com pages retired",
    ("EVGA", "SuperNOVA 1300 G7"): "evga.com pages retired",
    ("Thermaltake", "Smart BX3"): "thermaltake.com product pages "
    "JS-rendered; per-SKU PS-… pages not retrievable",
    ("Thermaltake", "Smart BM3"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower GX3"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower GX3 1050"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower PF1"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower PF1 650"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower PF1 750"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower PF1 1000"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Toughpower PF1 1050"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Magic FX 1000"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Smart BM3 550"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Smart BM3 650"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Smart BM3 750"): "thermaltake.com JS-rendered",
    ("Thermaltake", "Smart BM3 850"): "thermaltake.com JS-rendered",
}


def build():
    verified = []
    matched = 0
    for r in psu:
        idx = r["index"]
        plan = RMX2021.get(idx) or RMXSHIFT.get(idx)
        if plan is None:
            fam = (r["manufacturer"], r["product_family"])
            note = UNRESOLVED_NOTES.get(
                fam,
                "no per-SKU manufacturer evidence obtained this session; "
                "family left UNRESOLVED (fail-closed, no fabrication)",
            )
            verified.append(VerifiedSKU(
                category="PSU", name=r["name"],
                manufacturer=r["manufacturer"],
                product_family=r["product_family"], mpn="", per_sku_url="",
                source_doc_revision="", classification="UNRESOLVED",
                notes=note, candidate_index=idx,
            ))
            continue

        spec = {"wattage": plan["watt"],
                "efficiency_rating": "80 Plus Gold", "modular": True}
        fields = [
            ev("wattage", plan["watt"], f"{plan['watt']} Watts",
               "Tech Specs table, row 'Continuous Power W'", plan["url"]),
            ev("efficiency_rating", "80 Plus Gold", "Gold / 80 PLUS Gold",
               "Tech Specs table, row '80 PLUS Efficiency'", plan["url"]),
            ev("modular", True, "Fully Modular",
               "Tech Specs table, row 'Modular'", plan["url"]),
        ]
        revision = ("corsair.com product page, accessed 2026-11-23")
        verified.append(VerifiedSKU(
            category="PSU", name=r["name"], manufacturer="Corsair",
            product_family=("RMx (2021)" if idx in RMX2021
                            else "RMx Shift"),
            mpn=plan["mpn"], per_sku_url=plan["url"],
            source_doc_revision=revision, spec=spec, fields=fields,
            classification="MATCHED",
            notes=("RMx (2021) series page: ATX12V v2.4 / EPS 2.92; "
                   "pcie_12vhpwr claimed 0 — page does not list 12VHPWR "
                   "connector for this model"
                   if idx in RMX2021 else
                   "RMx SHIFT series page: ATX12V v3.1 / EPS 2.92; "
                   "12V-2x6 presence per series page, per-SKU connector "
                   "counts not listed on page — left NULL in spec"),
            candidate_index=idx,
        ))
        matched += 1

    man = new_manifest(verified, source="m31 PSU research")
    save_manifest(man, OUT)
    print("MATCHED:", matched, "TOTAL:", len(verified), "->", OUT)


build()
