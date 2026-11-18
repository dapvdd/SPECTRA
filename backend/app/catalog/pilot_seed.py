"""M3 Phase 5 — pilot catalog generator.

Composes the pilot records from the curated seed tables
(`pilot_seed_data.py`) — documentary facts (cited Wikipedia articles) +
official SKU ladders (cited vendor product-line pages).

M3 remediation (evidence honesty):
- A vendor FAMILY page (Trident Z5 listing, Focus GX series page) and a
  Wikipedia technology article are NOT SKU-level sources. They support
  family/technology facts only.
- evidence_status='verified' requires a per-SKU citation (product.aspx?pn=,
  per-model page) OR an MPN field on the record.
- Generated family×tier combinations without SKU-level citations are marked
  evidence_status='unverified' on their SKU-specific fields and the record's
  identity_status is 'unconfirmed', record_status 'QUARANTINED' (fail-closed:
  unverified records cannot be published without re-review).

The generator adds no numbers of its own: it enumerates the families × tiers
grid, builds deterministic canonical keys, attaches per-field provenance to
the family's citations, and stamps evidence honestly.
"""
from __future__ import annotations

from backend.app.catalog.pilot_seed_data import (
    ACCESS_DATE,
    MOTHERBOARD_FAMILIES,
    PSU_FAMILIES,
    RAM_FAMILIES,
    STORAGE_FAMILIES,
    VENDOR,
    WIKI,
)
from backend.app.catalog.pilot_sku_verified import (
    ACCESS_DATE_SKU,
    VERIFIED_SKUS,
    _verified_prov,
)
from backend.app.identity.canonical import canonical_key, variant_key

PILOT_TARGETS = {"RAM": 100, "STORAGE": 100, "MOTHERBOARD": 100, "PSU": 100}

_APPROVER = "m3-curator"


def _wiki_prov(wiki_key: str) -> dict:
    """Technology-level citation (Wikipedia): NEVER 'verified'.

    'uncertain' is the DB-vocabulary term for family/technology-tier
    evidence (field_provenance CHECK: verified|uncertain|excluded|unmatched).
    """
    return {
        "source_name": "Wikipedia (English) — curated",
        "source_url": WIKI[wiki_key],
        "license_name": "CC BY-SA 4.0",
        "evidence_status": "uncertain",
        "access_date": ACCESS_DATE,
    }


def _vendor_prov(vendor_key: str) -> dict:
    """Vendor family-page citation: NEVER 'verified' (family pages are not
    per-SKU sources)."""
    return {
        "source_name": "Official product pages — manual citations",
        "source_url": VENDOR[vendor_key],
        "license_name": "site terms (no redistribution license published)",
        "evidence_status": "uncertain",
        "access_date": ACCESS_DATE,
    }


def _record(category, name, manufacturer, family, spec, prov_map) -> dict:
    """Build one pilot record with honest evidence stamps.

    A record is identity-confirmed + APPROVED only when its provenance map
    contains at least one per-SKU citation (or an MPN field). Otherwise it
    is identity-'unconfirmed', record_status 'QUARANTINED'.
    """
    is_sku_backed = any(
        isinstance(p, dict) and p.get("evidence_status") == "verified"
        for p in prov_map.values()
    )
    if not is_sku_backed:
        # No per-SKU evidence: the record's identity is unconfirmed and it
        # cannot be APPROVED — it enters the pipeline QUARANTINED.
        return {
            "category": category,
            "name": name,
            "manufacturer": manufacturer,
            "product_family": family,
            "identity_status": "unconfirmed",
            "record_status": "QUARANTINED",
            "approved_by": None,
            "canonical_key": canonical_key(
                manufacturer, category, name,
                variant_key(category, spec),
            ),
            "spec": spec,
            "provenance": prov_map,
        }
    return {
        "category": category,
        "name": name,
        "manufacturer": manufacturer,
        "product_family": family,
        "identity_status": "confirmed",
        "record_status": "APPROVED",
        "approved_by": _APPROVER,
        "canonical_key": canonical_key(
            manufacturer, category, name,
            variant_key(category, spec),
        ),
        "spec": spec,
        "provenance": prov_map,
    }


def _ram_records() -> list[dict]:
    records = []
    for family, mfr, gen, speeds, voltage, vendor_key, configs in RAM_FAMILIES:
        wiki_key = gen.lower()  # ddr4/ddr5 articles
        for speed in dict.fromkeys(speeds):
            for modules, per_module in configs:
                capacity = modules * per_module
                kit_word = "Kit" if modules > 1 else "Module"
                name = (f"{mfr} {family} {capacity}GB "
                        f"({modules}x{per_module}GB) {gen}-{speed} {kit_word}")
                spec = {
                    "ddr_generation": gen,
                    "capacity_gb": capacity,
                    "speed_mhz": speed,
                    "modules": modules,
                    "voltage_v": voltage,
                    "form_factor": "UDIMM",
                }
                prov = {f: _wiki_prov(wiki_key) for f in spec}
                prov["speed_mhz"] = _vendor_prov(vendor_key)
                prov["capacity_gb"] = _vendor_prov(vendor_key)
                records.append(_record(
                    "RAM", name, mfr, family, spec, prov))
    return records


def _storage_records() -> list[dict]:
    records = []
    for (family, mfr, stype, capacities, interface, read_map, form_factor,
         vendor_key, wiki_key) in STORAGE_FAMILIES:
        for capacity in capacities:
            name = f"{mfr} {family} {capacity}GB {stype}"
            spec = {
                "storage_type": stype,
                "capacity_gb": capacity,
                "interface": interface,
                "read_mb_s": float(read_map[capacity]),
                "form_factor": form_factor,
            }
            prov = {f: _wiki_prov(wiki_key) for f in spec}
            prov["capacity_gb"] = _vendor_prov(vendor_key)
            prov["read_mb_s"] = _vendor_prov(vendor_key)
            records.append(_record(
                "STORAGE", name, mfr, family, spec, prov))
    return records


def _motherboard_records() -> list[dict]:
    records = []
    for (board, mfr, socket, chipset, form_factor, ram_type, ram_slots,
         max_ram, m2, sata, pcie, vendor_key, wiki_key) in MOTHERBOARD_FAMILIES:
        name = f"{mfr} {board}"
        spec = {
            "socket": socket,
            "chipset": chipset,
            "form_factor": form_factor,
            "ram_type": ram_type,
            "ram_slots": ram_slots,
            "max_ram_gb": max_ram,
            "m2_slots": m2,
            "sata_ports": sata,
            "pcie_slots": pcie,
        }
        prov = {f: _wiki_prov(wiki_key) for f in spec}
        prov["ram_slots"] = _vendor_prov(vendor_key)
        prov["max_ram_gb"] = _vendor_prov(vendor_key)
        records.append(_record(
            "MOTHERBOARD", name, mfr, board, spec, prov))
    return records


def _psu_records() -> list[dict]:
    records = []
    for (family, mfr, wattages, efficiency, modular, pcie8, vhpwr,
         vendor_key) in PSU_FAMILIES:
        for wattage in dict.fromkeys(wattages):
            name = f"{mfr} {family} {wattage}W"
            spec = {
                "wattage": wattage,
                "efficiency_rating": efficiency,
                "modular": modular,
                "pcie_8pin_count": pcie8,
                "pcie_12vhpwr": vhpwr,
            }
            prov = {f: _vendor_prov(vendor_key) for f in spec}
            prov["efficiency_rating"] = _wiki_prov("80plus")
            records.append(_record(
                "PSU", name, mfr, family, spec, prov))
    return records


def build_pilot_records() -> dict[str, list[dict]]:
    """Honest pilot record set (M3 remediation).

    Two record populations:
    - SKU-verified subset (pilot_sku_verified.VERIFIED_SKUS): every material
      spec carries a per-SKU citation + MPN -> evidence_status='verified',
      identity_status='confirmed', record_status='APPROVED'. Publishable.
    - Generated family×tier enumeration (pilot_seed_data grids): family/
      technology citations only -> evidence_status='unverified',
      identity_status='unconfirmed', record_status='QUARANTINED'. Included
      for audit and future curation; never publishable as-is.

    The old 100/category target is gone: no fabricated SKUs to hit it.
    """
    generated = {
        "RAM": _ram_records(),
        "STORAGE": _storage_records(),
        "MOTHERBOARD": _motherboard_records(),
        "PSU": _psu_records(),
    }

    merged: dict[str, list[dict]] = {}
    for category, records in generated.items():
        # SKU-verified entries first (deterministic order), then the
        # generated (quarantined) enumeration.
        verified = [_sku_record(s) for s in VERIFIED_SKUS
                    if s["category"] == category]
        merged[category] = verified + records
    return merged


def _sku_record(entry: dict) -> dict:
    """Build one SKU-verified record from a VERIFIED_SKUS entry.

    Every material spec field cites the per-SKU page with
    evidence_status='verified' plus a source_reference locator and an
    allowed match_method (Layer 3 of the evidence-gate contract);
    technology-level fields that the per-SKU page does not establish cite
    Wikipedia with evidence_status='uncertain'.
    """
    spec: dict = entry["spec"]
    prov_map: dict = {}
    for field_name in spec:
        if field_name in entry.get("tech_wiki", {}):
            prov_map[field_name] = _wiki_prov(entry["tech_wiki"][field_name])
        else:
            prov_map[field_name] = _verified_prov(
                field_name, entry["per_sku_url"], entry["category"]
            )
    record = _record(
        entry["category"], entry["name"], entry["manufacturer"],
        entry["product_family"], spec, prov_map,
    )
    # SKU anchor: the MPN field makes the evidence gate's SKU reference
    # explicit on the record itself (defense in depth for auditors).
    record["mpn"] = entry["mpn"]
    return record


def iter_batches(
    records: dict[str, list[dict]], sizes: list[int]
):
    """Yield cumulative bounded batches: 10 → 25 → 50 → 100 per category.

    Each yielded batch contains only the NEW records since the previous size
    (deltas), so importing all batches in order publishes exactly the target
    set per category, once.
    """
    for category in ("RAM", "STORAGE", "MOTHERBOARD", "PSU"):
        previous = 0
        for size in sizes:
            batch = records[category][previous:size]
            previous = size
            if batch:
                yield batch
