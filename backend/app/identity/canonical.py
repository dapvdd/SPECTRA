"""M3 Phase 1 — canonical identity construction.

Implements the contract in docs/m3/M3_IDENTITY_RULES.md §3:
deterministic, byte-stable identity keys over normalized manufacturer +
type + family/model + category-specific variant components.

Design rules:
- pure functions, no I/O, no database access;
- normalization reuses backend.app.normalization.primitives (the same
  strip/collapse rules the CPU/GPU importers use) so identity cannot drift
  from import normalization;
- missing variant components are omitted (never the string "unknown") so a
  key never encodes missingness as if it were a value;
- the same inputs always produce a byte-identical key.
"""
from __future__ import annotations

from backend.app.normalization.primitives import (
    normalize_name,
    strip_invisible_characters,
)

# Manufacturer alias map (docs/m3/M3_IDENTITY_RULES.md R1). Keys are lowercase
# alias forms; values are the canonical display forms used in the catalog.
ALIASES: dict[str, str] = {
    "g.skill": "G.Skill",
    "gskill": "G.Skill",
    "g-skill": "G.Skill",
    "wd": "Western Digital",
    "western digital": "Western Digital",
    "westerndigital": "Western Digital",
    "sandisk": "SanDisk",
    "samsung semiconductor": "Samsung",
    "samsung": "Samsung",
    "kingston": "Kingston",
    "crucial": "Crucial",
    "corsair": "Corsair",
    "teamgroup": "TeamGroup",
    "team group": "TeamGroup",
    "adata": "ADATA",
    "asus": "ASUS",
    "msi": "MSI",
    "gigabyte": "Gigabyte",
    "asrock": "ASRock",
    "seasonic": "Seasonic",
    "be quiet!": "be quiet!",
    "evga": "EVGA",
    "intel": "Intel",
    "amd": "AMD",
    "nvidia": "NVIDIA",
}


def normalize_manufacturer(value: str | None) -> str:
    """Return the canonical display manufacturer for a raw input.

    Unknown manufacturers keep their trimmed input; they never silently map.
    """
    if value is None:
        return ""
    stripped = strip_invisible_characters(value).strip()
    return ALIASES.get(stripped.lower(), stripped)


def _clean_component(value: object) -> str:
    """Lowercase, NFKC-safe, whitespace-collapsed key component."""
    text_value = str(value) if value is not None else ""
    cleaned = strip_invisible_characters(text_value).strip().lower()
    return " ".join(cleaned.split())


def variant_key(hardware_type: str, spec: dict) -> str:
    """Category-specific variant component of the canonical key.

    Missing components are omitted entirely (never the token "unknown") so a
    key never treats missing data as a value.
    """
    parts: list[str] = []
    t = (hardware_type or "").upper()

    if t == "RAM":
        modules = spec.get("modules")
        capacity = spec.get("capacity_gb")
        gen = _clean_component(spec.get("ddr_generation", "")).replace(" ", "")
        speed = spec.get("speed_mhz")
        if modules and modules > 1 and capacity:
            parts.append(f"kit-{int(modules)}x{int(capacity) // int(modules)}")
        elif capacity:
            parts.append(f"module-1x{int(capacity)}")
        # Generation and speed form ONE combined token (e.g. ddr56000) so the
        # key shape stays stable whether both, one, or neither is known.
        gen_speed = gen + (str(int(speed)) if speed else "")
        if gen_speed:
            parts.append(gen_speed)
        return "-".join(parts)

    if t == "STORAGE":
        stype = _clean_component(spec.get("storage_type", "")).replace(" ", "-")
        capacity = spec.get("capacity_gb")
        interface = _clean_component(spec.get("interface", "")).replace(" ", "")
        if stype:
            parts.append(stype)
        if capacity:
            parts.append(f"{int(capacity)}gb")
        if interface:
            parts.append(interface)
        return "-".join(parts)

    if t == "MOTHERBOARD":
        ff = _clean_component(spec.get("form_factor", "")).replace(" ", "-")
        socket = _clean_component(spec.get("socket", "")).replace(" ", "")
        chipset = _clean_component(spec.get("chipset", "")).replace(" ", "-")
        parts += [p for p in (ff, socket, chipset) if p]
        return "-".join(parts)

    if t == "PSU":
        wattage = spec.get("wattage")
        eff = _clean_component(spec.get("efficiency_rating", ""))
        eff_token = eff.replace("80 plus", "").replace("80-plus", "").strip().replace(" ", "-")
        modular = spec.get("modular")
        if wattage:
            parts.append(f"{int(wattage)}w")
        if eff_token:
            parts.append(eff_token)
        if modular is True:
            parts.append("mod")
        elif modular is False:
            parts.append("nonmod")
        return "-".join(parts)

    # Non-planner types (CPU/GPU or unknown): variant is the empty suffix.
    return ""


def canonical_key(
    manufacturer: str,
    hardware_type: str,
    family_or_model: str,
    variant: str | None = None,
) -> str:
    """Deterministic identity key: manufacturer|type|model|variant.

    All components are cleaned (lowercase, whitespace collapsed, invisible
    characters stripped); manufacturer aliases collapse per
    normalize_manufacturer; empty variant components are omitted; the result
    is capped at 300 characters (VARCHAR(300)).
    """
    manufacturer_norm = _clean_component(normalize_manufacturer(manufacturer))
    model_norm = _clean_component(family_or_model)
    variant_norm = _clean_component(variant or "")
    components = [c for c in (manufacturer_norm, hardware_type.lower(),
                              model_norm, variant_norm) if c]
    key = "|".join(components)
    if len(key) <= 300:
        return key
    # Naive truncation at the cap can cut the variant component off
    # entirely, silently merging distinct SKUs (identity collapse). Keep a
    # deterministic 16-hex-digit suffix of the full key's SHA-256 so two
    # different inputs never share a truncated key (collision probability
    # ~2^-64 per pair), while the readable prefix is preserved.
    import hashlib

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{key[:283]}~{digest}"


def duplicate_candidates(
    keyed_rows: list[tuple[str, dict]],
) -> list[list[dict]]:
    """Group rows that produced an identical canonical key.

    Duplicate keys are conflict candidates (never auto-merged). Returns a
    list of groups (each a list of the original row dicts), only for keys
    shared by more than one row, in first-appearance order.
    """
    groups: dict[str, list[dict]] = {}
    for key, row in keyed_rows:
        groups.setdefault(key, []).append(row)
    return [rows for rows in groups.values() if len(rows) > 1]
