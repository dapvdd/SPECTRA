"""Standalone normalization for Sprint 18B sample data.

Independent of the existing importer pipeline. Normalizes hardware names,
parses specifications, and handles edge cases (invisible characters,
malformed values, missing fields).
"""

import re
import unicodedata

INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf"})
INVISIBLE_SPACE_CHARS = frozenset({"\u00a0", "\u2007", "\u202f", "\ufeff"})

_MANUFACTURER_CANONICAL = {
    "AMD": "AMD",
    "INTEL": "Intel",
    "NVIDIA": "NVIDIA",
    "APPLE": "Apple",
    "QUALCOMM": "Qualcomm",
    "ATI": "ATI",
}


def strip_invisible_characters(value: str) -> str:
    return "".join(
        ch
        for ch in value
        if unicodedata.category(ch) not in INVISIBLE_CATEGORIES
        and ch not in INVISIBLE_SPACE_CHARS
    )


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value)
    value = strip_invisible_characters(value)
    return value.strip() or None


def normalize_manufacturer(value: str | None) -> str:
    name = normalize_name(value)
    if not name:
        return "Unknown"
    return _MANUFACTURER_CANONICAL.get(name.upper(), name)


def parse_ghz(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    match = re.fullmatch(r"(?:up\s+to\s+)?(\d+(?:\.\d+)?)\s*GHz", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def parse_mhz(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*MHz", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def parse_watt(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(
        r"(?<![\d.eE+-])(\d+(?:\.\d+)?)\s*(?:W|Watts?)\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1))


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*", value)
    if not match:
        return None
    return int(match.group(1))


def parse_memory_gb(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(KB|MB|GB)", text, re.IGNORECASE)
    if not match:
        return None
    multipliers = {"KB": 1.0 / (1024.0**2), "MB": 1.0 / 1024.0, "GB": 1.0}
    return float(match.group(1)) * multipliers[match.group(2).upper()]


def parse_length_mm(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)\s*mm", value.strip(), re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def normalize_cpu_row(row: dict[str, str]) -> dict[str, object | None]:
    return {
        "name": normalize_name(row.get("name")),
        "manufacturer": normalize_manufacturer(row.get("manufacturer")),
        "type": "CPU",
        "cores": parse_int(row.get("cores")),
        "threads": parse_int(row.get("threads")),
        "base_clock_ghz": parse_ghz(row.get("base_clock")),
        "boost_clock_ghz": parse_ghz(row.get("boost_clock")),
        "tdp_w": parse_watt(row.get("tdp")),
        "socket": normalize_name(row.get("socket")),
        "release_date": normalize_name(row.get("release_date")),
    }


def normalize_gpu_row(row: dict[str, str]) -> dict[str, object | None]:
    return {
        "name": normalize_name(row.get("name")),
        "manufacturer": normalize_manufacturer(row.get("manufacturer")),
        "type": "GPU",
        "memory_gb": parse_memory_gb(row.get("memory_gb")),
        "memory_type": normalize_name(row.get("memory_type")),
        "core_clock_mhz": parse_mhz(row.get("core_clock")),
        "boost_clock_mhz": parse_mhz(row.get("boost_clock")),
        "tdp_w": parse_watt(row.get("tdp")),
        "interface": normalize_name(row.get("interface")),
        "length_mm": parse_length_mm(row.get("length_mm")),
        "release_date": normalize_name(row.get("release_date")),
    }


def normalize_sample(
    cpus: list[dict[str, str]], gpus: list[dict[str, str]]
) -> tuple[list[dict[str, object | None]], list[dict[str, object | None]]]:
    return (
        [normalize_cpu_row(row) for row in cpus],
        [normalize_gpu_row(row) for row in gpus],
    )
