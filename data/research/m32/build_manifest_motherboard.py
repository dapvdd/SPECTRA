"""Build data/research/m32/manifest_motherboard.json (M32 Task 1).

MATCHED entries only where per-SKU manufacturer evidence was obtained this
session: ASUS official techspec pages (asus.com / rog.asus.com) for the 9
spec fields, plus MPN collection from ASUS eShop / distributor pages that
print the 90MB P/N verbatim (human-citation reads, one page at a time).
Every other inventory candidate is written UNRESOLVED with a per-family
source-access note â€” fail-closed, no fabrication.

Spec values are transcribed from the cited pages; claimed-vs-page diffs are
reconciled to the official page values and noted per SKU. PCIe policy: the
schema's ``pcie_slots`` stores the COUNT of physical expansion slots listed
on the page (x16 + x16(x4) + x16(x2) + x1 lines), matching the page layout.

cpu_generation_support text lives in VerifiedSKU.notes (never a spec
column): BIOS-dependent CPU support is not asserted as a spec field (M32
plan R8 keeps generation matching out of socket inference).
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\spectra-m32")
sys.path.insert(0, str(ROOT))

from data.research.m32.m32_mb_verified import (  # noqa: E402
    M32_ACCESS,
    VERIFIED_MB,
)
from backend.app.catalog.acquisition.manifest import (  # noqa: E402
    CandidateRecord,
    FieldEvidence,
    VerifiedSKU,
    new_manifest,
    save_manifest,
)

INV = ROOT / "data/research/m31/01_candidate_inventory.json"
OUT = ROOT / "data/research/m32/manifest_motherboard.json"

rows = json.loads(INV.read_text(encoding="utf-8"))
boards = [r for r in rows if r["category"] == "MOTHERBOARD"]
by_index = {r["index"]: r for r in boards}

FIELDS = ("socket", "chipset", "form_factor", "ram_type", "ram_slots",
          "max_ram_gb", "m2_slots", "sata_ports", "pcie_slots")

# Per-family UNRESOLVED notes (source-access evidence, no fabrication).
UNRESOLVED_NOTES = {
    "asus": (
        "asus.com techspec page for this slug unreachable/redirects to "
        "series landing page (generic PRIME/TUF/Business page without "
        "spec table) on www.asus.com and regional mirrors this session; "
        "earlier partial extractions failed re-read validation and were "
        "excluded per no-inference rule; no MPN evidence obtained "
        "(fail-closed, no fabrication)"
    ),
    "msi": "msi.com product pages return HTTP 403 to polite fetch "
           "(blocked); no per-SKU MPN evidence obtainable",
    "gigabyte": "gigabyte.com product pages return HTTP 403 to polite "
                "fetch (blocked); no per-SKU MPN evidence obtainable",
    "asrock": "asrock.com behind Incapsula WAF (curl 200 but WAF iframe, "
              "no spec content); no per-SKU MPN evidence obtainable",
}


# ASUS cpu_support strings per verified board (kept in VerifiedSKU.notes;
# BIOS-dependent support is never asserted as a spec field - M32 plan R8).
CPU_SUPPORT = {
    "238": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (refer to asus.com for CPU support list)"),
    "239": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (refer to asus.com for CPU support list)"),
    "240": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (refer to asus.com for CPU support list)"),
    "248": ("LGA1700 for Intel Core 14th & 13th Gen Processors, Intel Core "
            "12th Gen, Pentium Gold and Celeron Processors"),
    "253": ("LGA1700 for Intel Core 14th & 13th Gen Processors, Intel Core "
            "12th Gen, Pentium Gold and Celeron Processors"),
    "259": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (up to 170W)"),
    "261": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (up to 170W)"),
    "266": ("LGA1700 for Intel Core 14th & 13th Gen Processors, Intel Core "
            "12th Gen, Pentium Gold and Celeron Processors"),
    "270": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (refer to asus.com for CPU support list)"),
    "274": ("LGA1700 for Intel Core 14th & 13th Gen Processors, Intel Core "
            "12th Gen, Pentium Gold and Celeron Processors"),
    "278": ("LGA1700 for Intel Core 14th & 13th Gen Processors, Intel Core "
            "12th Gen, Pentium Gold and Celeron Processors"),
    "283": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (up to 120W)"),
    "289": ("AMD Socket AM5 for AMD Ryzen 9000 & 8000 & 7000 Series "
            "Desktop Processors (up to 170W)"),
}

def ev(field, value, source_value, url):
    return FieldEvidence(
        spec_field=field, normalized_value=value, source_value=source_value,
        source_evidence_location=(
            "ASUS official Tech Specs table (row: "
            f"{field.replace('_', ' ')})"),
        curator_decision="APPROVED", source_url=url,
        match_method="spec-table-row", access_date=M32_ACCESS,
    )


def build():
    verified = []
    matched = 0
    for r in boards:
        idx = r["index"]
        plan = VERIFIED_MB.get(idx)
        if plan is None:
            mfr = (r["manufacturer"] or "").lower()
            note = UNRESOLVED_NOTES.get(
                mfr,
                "no per-SKU manufacturer evidence obtained this session; "
                "family left UNRESOLVED (fail-closed, no fabrication)",
            )
            if idx == "261":
                note = (
                    "asus.com PRIME X670-P page verified (MPN 90MB1BU0-"
                    "M0EAY0 via Senetic) but candidate claims chipset "
                    "X670E while the page documents AMD X670; per ASUS "
                    "naming these are different products and the claimed "
                    "X670E chipset is unsupported by the verified page; "
                    "resolved REPLACED in the resolution report (fail-"
                    "closed, no inference of X670E support from X670 data)"
                )
            verified.append(VerifiedSKU(
                category="MOTHERBOARD", name=r["name"],
                manufacturer=r["manufacturer"],
                product_family=r["product_family"], mpn="", per_sku_url="",
                source_doc_revision="", classification="UNRESOLVED",
                notes=note, candidate_index=idx,
            ))
            continue

        spec = plan["spec"]
        fields = [
            ev(f, spec[f],
               plan["mem_row"] if f in ("ram_type", "ram_slots",
                                        "max_ram_gb")
               else plan["sto_row"] if f in ("m2_slots", "sata_ports")
               else plan["pcie_row"] if f == "pcie_slots"
               else str(spec[f]),
               plan["url"])
            for f in FIELDS
        ]
        verified.append(VerifiedSKU(
            category="MOTHERBOARD", name=r["name"],
            manufacturer=r["manufacturer"],
            product_family=r["product_family"], mpn=plan["mpn"],
            per_sku_url=plan["url"], source_doc_revision=(
                "ASUS official page, accessed " + M32_ACCESS),
            spec=spec, fields=fields, classification="MATCHED",
            notes=plan["note"] + (
                "; MPN source: " + plan["mpn_url"]
            ) + (
                "; cpu_support: " + CPU_SUPPORT[idx] if idx in CPU_SUPPORT
                else ""
            ),
            candidate_index=idx,
        ))
        matched += 1

    candidates = [
        CandidateRecord(
            category=r["category"], name=r["name"],
            manufacturer=r["manufacturer"],
            product_family=r["product_family"],
            canonical_key=r["canonical_key"], index=r["index"],
            claimed_spec=json.loads(r.get("claimed_spec_json") or "{}"),
            provenance_urls=json.loads(
                r.get("provenance_urls_json") or "{}"),
            identity_status=r.get("identity_status", "unconfirmed"),
        )
        for r in boards
    ]
    man = new_manifest(verified, candidates,
                       source="m32 motherboard research")
    save_manifest(man, OUT)
    print("MATCHED:", matched, "TOTAL:", len(verified), "->", OUT)


build()
