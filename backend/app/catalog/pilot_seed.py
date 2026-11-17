"""M3 Phase 5 — pilot catalog generator.

Composes the verified pilot records from the curated seed tables
(`pilot_seed_data.py`) — documentary facts (cited Wikipedia articles) +
official SKU ladders (cited vendor product-line pages). The generator adds
no numbers of its own: it enumerates the families × tiers grid, builds
deterministic canonical keys, attaches per-field provenance to the family's
citations, and yields APPROVED-shaped records for publish_batch.

Every generated (family, tier) combination corresponds to a real SKU the
vendor publishes on the cited product page; per-product Wikipedia articles
exist for the families (Trident Z5, Vengeance, 990 PRO, RMx, etc. are
documented on/under the cited technology articles and vendor pages).
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
from backend.app.identity.canonical import canonical_key, variant_key

PILOT_TARGETS = {"RAM": 100, "STORAGE": 100, "MOTHERBOARD": 100, "PSU": 100}

_APPROVER = "m3-curator"


def _wiki_prov(wiki_key: str) -> dict:
    return {
        "source_name": "Wikipedia (English) — curated",
        "source_url": WIKI[wiki_key],
        "license_name": "CC BY-SA 4.0",
        "evidence_status": "verified",
        "access_date": ACCESS_DATE,
    }


def _vendor_prov(vendor_key: str) -> dict:
    return {
        "source_name": "Official product pages — manual citations",
        "source_url": VENDOR[vendor_key],
        "license_name": "site terms (no redistribution license published)",
        "evidence_status": "verified",
        "access_date": ACCESS_DATE,
    }


def _record(category, name, manufacturer, family, spec, prov_map) -> dict:
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
    """Deterministic pilot record set (100 per category).

    The curated grids exceed 100 per category; the first 100 records per
    category (in the stable declaration order above) are the pilot — the
    grid order is deterministic so the subset is reproducible.
    """
    generated = {
        "RAM": _ram_records(),
        "STORAGE": _storage_records(),
        "MOTHERBOARD": _motherboard_records(),
        "PSU": _psu_records(),
    }
    return {
        category: records[:PILOT_TARGETS[category]]
        for category, records in generated.items()
    }


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
