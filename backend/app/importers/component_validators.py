"""Per-category validators for the Build Planner CSV importer (M1 Task 2).

One config-driven validator: each category declares its field vocabulary
(name -> (python type, max length)) and ``validate_component_row`` coerces
and checks a single CSV row against it.

Contracts:
- Raises ``ValueError`` naming the offending field on any invalid input.
- Strips whitespace; empty/blank optional fields are removed from the output
  dict entirely (normalized to absent, never "").
- ``type`` must equal the category's required Hardware.type value.
- No fabrication: absent optional values are never invented.
"""

from __future__ import annotations

from typing import Any

# Category slug -> required Hardware.type value (closed vocabulary).
CATEGORY_TYPES: dict[str, str] = {
    "ram": "RAM",
    "storage": "STORAGE",
    "motherboard": "MOTHERBOARD",
    "psu": "PSU",
}

# Per-category field vocabulary: field -> (python type, max length).
# Spec fields mirror the four M1 models exactly (models/ram.py, storage.py,
# motherboard.py, psu.py). Max length 0 = numeric (no length limit).
_RAM_FIELDS: dict[str, tuple[type, int]] = {
    "ddr_generation": (str, 10),
    "capacity_gb": (int, 0),
    "speed_mhz": (int, 0),
    "modules": (int, 0),
    "ecc": (bool, 0),
    "voltage_v": (float, 0),
    "form_factor": (str, 30),
}

_STORAGE_FIELDS: dict[str, tuple[type, int]] = {
    "storage_type": (str, 20),
    "capacity_gb": (int, 0),
    "interface": (str, 40),
    "read_mb_s": (float, 0),
    "write_mb_s": (float, 0),
    "dram_cache": (bool, 0),
    "form_factor": (str, 30),
}

_MOTHERBOARD_FIELDS: dict[str, tuple[type, int]] = {
    "socket": (str, 30),
    "chipset": (str, 30),
    "form_factor": (str, 20),
    "ram_type": (str, 10),
    "ram_slots": (int, 0),
    "max_ram_gb": (int, 0),
    "m2_slots": (int, 0),
    "sata_ports": (int, 0),
    "pcie_slots": (int, 0),
}

_PSU_FIELDS: dict[str, tuple[type, int]] = {
    "wattage": (int, 0),
    "efficiency_rating": (str, 30),
    "modular": (bool, 0),
    "pcie_8pin_count": (int, 0),
    "pcie_12vhpwr": (int, 0),
}

_FIELDS: dict[str, dict[str, tuple[type, int]]] = {
    "ram": _RAM_FIELDS,
    "storage": _STORAGE_FIELDS,
    "motherboard": _MOTHERBOARD_FIELDS,
    "psu": _PSU_FIELDS,
}

# Closed value vocabularies (mirror the CHECK constraints in the models).
_ENUMS: dict[str, set[str]] = {
    "ddr_generation": {"DDR3", "DDR4", "DDR5", "DDR6"},
    "storage_type": {"NVMe", "SATA SSD", "HDD"},
    "efficiency_rating": {
        "80 Plus White", "80 Plus Bronze", "80 Plus Gold",
        "80 Plus Platinum", "80 Plus Titanium",
    },
}

_BOOL_VALUES = {
    "true": True, "false": False, "yes": True, "no": False,
    "1": True, "0": False, "y": True, "n": False,
}

_IDENTITY_MAX_LEN = {"name": 120, "manufacturer": 60}


def _coerce_bool(value: str, field: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in _BOOL_VALUES:
        raise ValueError(
            f"field '{field}' must be a boolean (true/false), got {value!r}"
        )
    return _BOOL_VALUES[lowered]


def _coerce_int(value: str, field: str) -> int:
    try:
        parsed = int(value.strip())
    except ValueError:
        raise ValueError(
            f"field '{field}' must be an integer, got {value!r}"
        ) from None
    if parsed <= 0:
        raise ValueError(
            f"field '{field}' must be a positive integer, got {parsed}"
        )
    return parsed


def _coerce_float(value: str, field: str) -> float:
    try:
        parsed = float(value.strip())
    except ValueError:
        raise ValueError(
            f"field '{field}' must be a number, got {value!r}"
        ) from None
    if parsed <= 0:
        raise ValueError(f"field '{field}' must be positive, got {parsed}")
    return parsed


def _coerce_str(value: str, field: str, max_len: int) -> str:
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise ValueError(
            f"field '{field}' exceeds max length {max_len}: got {len(cleaned)}"
        )
    return cleaned


def validate_component_row(category: str, row: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce one CSV row for ``category``.

    Returns the validated dict (identity + coerced spec fields, blank
    optional fields removed). Raises ValueError naming the offending field.
    """
    if category not in CATEGORY_TYPES:
        raise ValueError(
            f"unknown category '{category}' (expected one of {sorted(CATEGORY_TYPES)})"
        )

    errors: list[str] = []
    out: dict[str, Any] = {}

    # --- identity fields (required for every category) ---
    for field in ("name", "manufacturer"):
        raw = row.get(field)
        if raw is None or not str(raw).strip():
            errors.append(f"field '{field}' is required")
            continue
        try:
            out[field] = _coerce_str(str(raw), field, _IDENTITY_MAX_LEN[field])
        except ValueError as exc:
            errors.append(str(exc))

    # --- type must match the category's required Hardware.type ---
    raw_type = str(row.get("type") or "").strip()
    expected = CATEGORY_TYPES[category]
    if raw_type != expected:
        errors.append(
            f"field 'type' must be '{expected}' for category "
            f"'{category}', got '{raw_type}'"
        )

    # --- spec fields (optional; blank -> absent) ---
    for field, (py_type, max_len) in _FIELDS[category].items():
        raw = row.get(field)
        if raw is None or not str(raw).strip():
            continue  # optional: absent, never fabricated
        try:
            if py_type is int:
                out[field] = _coerce_int(str(raw), field)
            elif py_type is float:
                out[field] = _coerce_float(str(raw), field)
            elif py_type is bool:
                out[field] = _coerce_bool(str(raw), field)
            else:
                cleaned = _coerce_str(str(raw), field, max_len)
                if field in _ENUMS and cleaned not in _ENUMS[field]:
                    raise ValueError(
                        f"field '{field}' must be one of "
                        f"{sorted(_ENUMS[field])}, got '{cleaned}'"
                    )
                out[field] = cleaned
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError("; ".join(errors))
    return out
