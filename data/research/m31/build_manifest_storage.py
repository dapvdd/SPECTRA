"""Build data/research/m31/manifest_storage.json (M31 Task 5).

MATCHED entries only where per-SKU manufacturer evidence was obtained this
session (human-citation reads of official Sandisk/Kingston pages and PDF
datasheets). Every other inventory candidate is written UNRESOLVED with a
per-family source-access note — fail-closed, no fabrication.
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
OUT = ROOT / "data/research/m31/manifest_storage.json"

rows = json.loads(INV.read_text(encoding="utf-8"))
storage = [r for r in rows if r["category"] == "STORAGE"]
by_index = {r["index"]: r for r in storage}


# ---------------------------------------------------------------------------
# Verified evidence (per-SKU, official manufacturer documents)
# ---------------------------------------------------------------------------

def ev(field, value, source_value, locator, url, method="spec-table-row"):
    return FieldEvidence(
        spec_field=field, normalized_value=value, source_value=source_value,
        source_evidence_location=locator, curator_decision="APPROVED",
        source_url=url, match_method=method, access_date=ACCESS,
    )


SN850X_URL = ("https://www.sandisk.com/products/ssd/internal-ssd/"
              "wd-black-sn850x-nvme-ssd?sku={mpn}")
SN850X_LOC = "Sandisk WD_BLACK SN850X product page, Specs table (row: {row})"

KC3000_URL = "https://www.kingston.com/dataSheets/KC3000_en.pdf"
KC3000_LOC = "Kingston KC3000 datasheet (rev. Jul 27/2021), spec table"

A400_URL = "https://www.kingston.com/dataSheets/SA400S37_en.pdf"
A400_LOC = "Kingston A400 datasheet (rev. Sep 3/2024), spec table"

# MPNs verified verbatim on the cited documents:
# - SN850X model numbers from the Sandisk product-page per-SKU selectors
#   (WDS100T2X0E-00BCA0 ... WDS800T2XHE-00CDD0).
# - KC3000 part numbers from the datasheet "PART NUMBER" block
#   (SKC3000S/512G, SKC3000S/1024G, SKC3000D/2048G, SKC3000D/4096G).
# - A400 part numbers from the datasheet "KINGSTON PART NUMBERS" block
#   (SA400S37/240G, SA400S37/480G, SA400S37/960G).
# Spec values transcribed from the same documents' spec tables; claimed-vs-
# page diffs reconciled to official values and noted per SKU.
MATCHED_PLANS = {
    "135": {
        "mpn": "WDS100T2X0E-00BCA0",
        "read": (7300, "7,300 MB/s"),
        "spec": {"storage_type": "NVMe", "capacity_gb": 1024,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7300,
                 "form_factor": "M.2 2280"},
        "note": "claimed read 7300 matches page (1TB, PCIe Gen4 model); "
                "1TB model number ends -00BCA0 (with heatsink variant "
                "-00BCA0/00BCE per page selector; -X0E denotes PCIe4)",
    },
    "136": {
        "mpn": "WDS200T2X0E-00BCA0",
        "read": (6600, "6,600 MB/s"),
        "spec": {"storage_type": "NVMe", "capacity_gb": 2048,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 6600,
                 "form_factor": "M.2 2280"},
        "note": "claimed read 7300 reconciled to page value 6600 MB/s "
                "(2TB model)",
    },
    "137": {
        "mpn": "WDS400T2X0E-00BCA0",
        "read": (7300, "7,300 MB/s"),
        "spec": {"storage_type": "NVMe", "capacity_gb": 4096,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7300,
                 "form_factor": "M.2 2280"},
        "note": "claimed read 7300 matches page (4TB model)",
    },
    "141": {
        "mpn": "SKC3000S/512G",
        "spec": {"storage_type": "NVMe", "capacity_gb": 512,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7000,
                 "write_mb_s": 3900, "form_factor": "M.2 2280"},
        "note": "512GB write 3900 MB/s per datasheet capacity row; "
                "other capacities read/write 7000/7000",
    },
    "142": {
        "mpn": "SKC3000S/1024G",
        "spec": {"storage_type": "NVMe", "capacity_gb": 1024,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7000,
                 "write_mb_s": 7000, "form_factor": "M.2 2280"},
        "note": "datasheet: 7,000MB/s read/write across 1TB-4TB",
    },
    "143": {
        "mpn": "SKC3000D/2048G",
        "spec": {"storage_type": "NVMe", "capacity_gb": 2048,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7000,
                 "write_mb_s": 7000, "form_factor": "M.2 2280"},
        "note": "datasheet: 7,000MB/s read/write across 1TB-4TB",
    },
    "144": {
        "mpn": "SKC3000D/4096G",
        "spec": {"storage_type": "NVMe", "capacity_gb": 4096,
                 "interface": "PCIe 4.0 x4", "read_mb_s": 7000,
                 "write_mb_s": 7000, "form_factor": "M.2 2280"},
        "note": "datasheet: 7,000MB/s read/write across 1TB-4TB",
    },
    "153": {
        "mpn": "SA400S37/240G",
        "spec": {"storage_type": "SATA SSD", "capacity_gb": 240,
                 "interface": "SATA III", "read_mb_s": 500,
                 "write_mb_s": 350, "form_factor": "2.5-inch"},
        "note": "datasheet: 240GB — up to 500MB/s read and 350MB/s write",
    },
    "154": {
        "mpn": "SA400S37/480G",
        "spec": {"storage_type": "SATA SSD", "capacity_gb": 480,
                 "interface": "SATA III", "read_mb_s": 500,
                 "write_mb_s": 450, "form_factor": "2.5-inch"},
        "note": "datasheet: 480GB — up to 500MB/s read and 450MB/s write",
    },
    "155": {
        "mpn": "SA400S37/960G",
        "spec": {"storage_type": "SATA SSD", "capacity_gb": 960,
                 "interface": "SATA III", "read_mb_s": 500,
                 "write_mb_s": 450, "form_factor": "2.5-inch"},
        "note": "datasheet: 960GB — up to 500MB/s read and 450MB/s write",
    },
}

# Per-family UNRESOLVED notes (source-access evidence, no fabrication).
UNRESOLVED_NOTES = {
    ("Samsung", "870 EVO"): "samsung.com product pages are JS-rendered; "
    "per-SKU model numbers (MZ-77E…) not retrievable via polite fetch",
    ("Samsung", "870 QVO"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-77Q…) not retrievable",
    ("Samsung", "860 EVO"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-76E…) not retrievable",
    ("Samsung", "860 QVO"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-76Q…) not retrievable",
    ("Samsung", "990 PRO"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-V9P…) not retrievable",
    ("Samsung", "990 EVO"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-V9E…) not retrievable",
    ("Samsung", "980"): "samsung.com JS-rendered; per-SKU MPNs (MZ-V8V…) "
    "not retrievable",
    ("Samsung", "970 EVO Plus"): "samsung.com JS-rendered; per-SKU MPNs "
    "(MZ-V7S…) not retrievable",
    ("Western Digital", "WD Blue"): "westerndigital.com product pages are "
    "JS-rendered; per-SKU model numbers (WD10EZEX etc.) not retrievable",
    ("Western Digital", "WD Purple"): "westerndigital.com JS-rendered; "
    "per-SKU model numbers (WD…PURX) not retrievable",
    ("Western Digital", "SN770"): "westerndigital.com JS-rendered; per-SKU "
    "model numbers (WDS…G2X0E) not retrievable this session",
    ("Western Digital", "SN580"): "westerndigital.com JS-rendered; per-SKU "
    "model numbers not retrievable this session",
    ("Western Digital", "SN750 SE"): "westerndigital.com JS-rendered; "
    "per-SKU model numbers not retrievable this session",
    ("Seagate", "BarraCuda"): "seagate.com product pages are JS-rendered/"
    "redirect loops; per-SKU model numbers (ST…) not retrievable",
    ("Seagate", "IronWolf"): "seagate.com JS-rendered; per-SKU model "
    "numbers (ST…) not retrievable",
    ("Seagate", "FireCuda 530"): "seagate.com JS-rendered; per-SKU model "
    "numbers (ZP…) not retrievable",
    ("Seagate", "FireCuda 520"): "seagate.com JS-rendered; per-SKU model "
    "numbers not retrievable",
    ("Crucial", "MX500"): "crucial.com blocked polite fetch (WAF/403); "
    "per-SKU MPNs (CT…SSD1) not retrievable",
    ("Crucial", "BX500"): "crucial.com WAF/403; per-SKU MPNs not "
    "retrievable",
    ("Crucial", "P3 Plus"): "crucial.com WAF/403; per-SKU MPNs (CT…SSD5) "
    "not retrievable",
    ("Crucial", "P5 Plus"): "crucial.com WAF/403; per-SKU MPNs (CT…SSD3) "
    "not retrievable",
    ("Crucial", "T500"): "crucial.com WAF/403; per-SKU MPNs (CT…SSD9) not "
    "retrievable",
    ("Crucial", "SA510"): "crucial.com WAF/403; per-SKU MPNs (CT…SSD3) not "
    "retrievable",
    ("Kingston", "NV2"): "kingston.com NV2 page is redirect/category-only; "
    "AddToCart PartNumbers not served for NV2 (NV3 page data does not map "
    "to NV2 candidates — no family pass)",
    ("Kingston", "A2000"): "kingston.com A2000 discontinued page 404; no "
    "per-SKU MPN evidence",
    ("Kingston", "KC2500"): "kingston.com KC2500 page JS-gated; per-SKU "
    "part numbers (SKC2500S…) not retrievable",
    ("ADATA", "SX8200 Pro"): "adata.com product pages are JS-rendered; "
    "per-SKU MPNs (ASX8200PNP-…-C) not retrievable",
    ("ADATA", "Legend 960 Max"): "adata.com JS-rendered; per-SKU MPNs "
    "(ALEG-960M-…) not retrievable",
    ("ADATA", "Gammix S70 Blade"): "adata.com JS-rendered; per-SKU MPNs "
    "(AGAMMIXS70B-…) not retrievable",
    ("TeamGroup", "Swordfish"): "teamgroupinc.com product pages 404/"
    "redirect; per-SKU MPNs (TM8FF…) not retrievable",
    ("TeamGroup", "MP44"): "teamgroupinc.com JS-rendered; per-SKU MPNs "
    "(TM8FFD…) not retrievable",
}


def build():
    verified = []
    matched_count = 0
    for r in storage:
        idx = r["index"]
        plan = MATCHED_PLANS.get(idx)
        if plan is None:
            fam = (r["manufacturer"], r["product_family"])
            note = UNRESOLVED_NOTES.get(
                fam,
                "no per-SKU manufacturer evidence obtained this session; "
                "family left UNRESOLVED (fail-closed, no fabrication)",
            )
            verified.append(VerifiedSKU(
                category="STORAGE", name=r["name"],
                manufacturer=r["manufacturer"],
                product_family=r["product_family"], mpn="", per_sku_url="",
                source_doc_revision="", classification="UNRESOLVED",
                notes=note, candidate_index=idx,
            ))
            continue

        spec = plan["spec"]
        fields = []
        source_rows = {
            "storage_type": ("Product line: NVMe SSD" if "SN850X" in
                             plan["mpn"] else "Interface row / product title"),
            "capacity_gb": "Capacity row",
            "interface": "Interface row (PCIe 4.0 x4 NVMe)",
            "read_mb_s": ("Sequential read row: %s" % plan["read"][1]
                          if "read" in plan else
                          "Sequential read row: up to 500MB/s"),
            "write_mb_s": "Sequential write row",
            "form_factor": "Form factor row: M.2 2280",
        }
        urls = {"read": SN850X_URL.format(mpn=plan["mpn"])}
        for f, v in spec.items():
            if f == "read_mb_s" and "read" in plan:
                sv = plan["read"][1]
            elif f == "read_mb_s":
                sv = "up to 500MB/s"
            elif f == "write_mb_s":
                sv = {"3900": "3,900MB/s", "7000": "7,000MB/s",
                      "350": "350MB/s", "450": "450MB/s"}[str(v)]
            else:
                sv = str(v)
            locator = (KC3000_LOC if plan["mpn"].startswith("SKC3000")
                       else A400_LOC if plan["mpn"].startswith("SA400")
                       else SN850X_LOC.format(row=source_rows.get(f, "")))
            url = (KC3000_URL if plan["mpn"].startswith("SKC3000")
                   else A400_URL if plan["mpn"].startswith("SA400")
                   else SN850X_URL.format(mpn=plan["mpn"]))
            fields.append(ev(f, v, sv, locator, url))

        verified.append(VerifiedSKU(
            category="STORAGE", name=r["name"],
            manufacturer=r["manufacturer"],
            product_family=r["product_family"], mpn=plan["mpn"],
            per_sku_url=urls.get("read", ""), source_doc_revision=(
                "Sandisk product page, accessed 2026-11-23"
                if plan["mpn"].startswith("WDS") else
                "Kingston datasheet, accessed 2026-11-23"),
            spec=spec, fields=fields, classification="MATCHED",
            notes=plan["note"], candidate_index=idx,
        ))
        matched_count += 1

    man = new_manifest(verified, source="m31 storage research")
    save_manifest(man, OUT)
    print("MATCHED:", matched_count, "TOTAL:", len(verified), "->", OUT)


build()
