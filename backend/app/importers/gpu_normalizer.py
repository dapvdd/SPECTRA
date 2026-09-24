"""Normalize raw GPU CSV rows (TechPowerUp-derived dataset).

Values are parsed strictly from the supplied source fields. Missing or
malformed values become None and are never estimated. Memory bandwidth is
parsed directly from ``Memory__Bandwidth`` (GB/s, TB/s, MB/s in the source);
no value is derived or fabricated. Release dates keep their source precision:
"Jan 30th, 2025" becomes "2025-01-30" while a year-only "2022" stays "2022".
"""

import re
from datetime import datetime

from backend.app.importers.benchmark_normalizer import (
    normalize_name,
    parse_watt,
)

_MEMORY_UNIT_TO_GB = {
    "KB": 1.0 / (1024.0 ** 2),
    "MB": 1.0 / 1024.0,
    "GB": 1.0,
}

_BANDWIDTH_UNIT_TO_GBPS = {
    "MB/S": 1.0 / 1000.0,
    "GB/S": 1.0,
    "TB/S": 1000.0,
}

_MANUFACTURER_CANONICAL = {
    "NVIDIA": "NVIDIA",
    "AMD": "AMD",
    "INTEL": "Intel",
    "ATI": "ATI",
}

_ORDINAL_SUFFIX = re.compile(r"(\d)(?:st|nd|rd|th)", re.IGNORECASE)


def detect_gpu_manufacturer(brand: str | None) -> str:
    text = normalize_name(brand or "")

    if not text:
        return "Unknown"

    return _MANUFACTURER_CANONICAL.get(text.upper(), text)


def normalize_gpu_name(
    name: str | None,
    brand: str | None = None,
) -> str | None:
    normalized = normalize_name(name or "")

    if not normalized:
        return None

    if brand:
        prefix = brand.strip().lower() + " "
        if normalized.lower().startswith(prefix):
            normalized = normalize_name(normalized[len(prefix):])

    return normalized or None


def parse_mhz(value: str | None) -> float | None:
    text = (value or "").strip()

    if not text:
        return None

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*MHz",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1))


def parse_memory_size_gb(value: str | None) -> float | None:
    text = (value or "").strip()

    if not text:
        return None

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(KB|MB|GB)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1)) * _MEMORY_UNIT_TO_GB[
        match.group(2).upper()
    ]


def parse_vram_bandwidth_gbps(value: str | None) -> float | None:
    text = (value or "").strip()

    if not text:
        return None

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(GB/s|TB/s|MB/s)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1)) * _BANDWIDTH_UNIT_TO_GBPS[
        match.group(2).upper()
    ]


def parse_length_mm(value: str | None) -> float | None:
    text = (value or "").strip()

    if not text:
        return None

    match = re.match(
        r"(\d+(?:\.\d+)?)\s*mm",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1))


def parse_release_date(value: str | None) -> str | None:
    text = (value or "").strip()

    if not text:
        return None

    if re.fullmatch(r"\d{4}", text):
        return text

    cleaned = _ORDINAL_SUFFIX.sub(r"\1", text)

    try:
        parsed = datetime.strptime(cleaned, "%b %d, %Y")
    except ValueError:
        return None

    return parsed.strftime("%Y-%m-%d")


def normalize_memory_type(value: str | None) -> str | None:
    text = normalize_name(value or "")

    if not text:
        return None

    return text


def normalize_interface(value: str | None) -> str | None:
    return normalize_name(value or "")


def normalize_gpu_row(row: dict[str, object | None]) -> dict[str, object | None]:
    brand = (row.get("Brand") or "").strip()
    name = (row.get("Name") or "").strip()

    return {
        "name": normalize_gpu_name(name, brand),
        "manufacturer": detect_gpu_manufacturer(brand),
        "type": "GPU",
        "release_date": parse_release_date(
            row.get("Graphics Card__Release Date")
        ),
        "architecture": normalize_name(
            row.get("Graphics Processor__Architecture")
        ),
        "memory_gb": parse_memory_size_gb(
            row.get("Memory__Memory Size")
        ),
        "memory_type": normalize_memory_type(
            row.get("Memory__Memory Type")
        ),
        "core_clock_mhz": parse_mhz(
            row.get("Clock Speeds__GPU Clock")
        ),
        "boost_clock_mhz": parse_mhz(
            row.get("Clock Speeds__Boost Clock")
        ),
        "vram_bandwidth_gbps": parse_vram_bandwidth_gbps(
            row.get("Memory__Bandwidth")
        ),
        "tdp_w": parse_watt(row.get("Board Design__TDP")),
        "interface": normalize_interface(
            row.get("Graphics Card__Bus Interface")
        ),
        "length_mm": parse_length_mm(
            row.get("Board Design__Length")
        ),
    }