import re

# Generic shared primitives are hosted in backend.app.normalization so that
# new catalogs reuse one tested home. They are re-exported here (and re-exported
# by cpu_normalizer / gpu_normalizer) so the importer-facing API is unchanged.
from backend.app.normalization.primitives import (
    parse_int,
    parse_watt,
    normalize_name,
    strip_invisible_characters,
    INVISIBLE_CHARACTER_CATEGORIES,
)

def normalize_benchmark_cpu_name(
    value: str | None,
) -> str | None:
    if not value:
        return None

    value = normalize_name(value)

    if not value:
        return None

    name = value
    # Remove multi-CPU configuration prefixes
    # Examples:
    # [Dual CPU] AMD EPYC 7252
    # [Quad CPU] AMD Opteron 6276
    # [5-Way] AMD Ryzen 9 5950X
    name = re.sub(
        r"^\[(?:Dual CPU|Quad CPU|\d+-Way)\]\s*",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return name.strip()

def parse_benchmark_ghz(value: str | None) -> float | None:
    if not value:
        return None

    value = value.strip()

    # Normal format:
    # 3.6 GHz
    normal_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*GHz",
        value,
        re.IGNORECASE,
    )

    if normal_match:
        return float(normal_match.group(1))

    # Broken format:
    # 2.112.0 GHz -> 2.112
    broken_match = re.fullmatch(
        r"(\d+)\.(\d{3})\.0\s*GHz",
        value,
        re.IGNORECASE,
    )

    if broken_match:
        return float(
            f"{broken_match.group(1)}.{broken_match.group(2)}"
        )

    return None


def detect_manufacturer(name: str | None) -> str:
    if not name:
        return "Unknown"

    name_upper = name.upper()

    if name_upper.startswith("AMD"):
        return "AMD"

    if name_upper.startswith("INTEL"):
        return "Intel"

    if name_upper.startswith("APPLE"):
        return "Apple"

    if name_upper.startswith("QUALCOMM"):
        return "Qualcomm"

    if name_upper.startswith("ALLWINNER"):
        return "Allwinner"

    if name_upper.startswith("ARM"):
        return "ARM"

    return "Unknown"


def normalize_benchmark_row(
    row: dict[str, str],
) -> dict[str, object | None]:
    name = normalize_benchmark_cpu_name(
    row.get("CpuName")
)

    return {
        "name": name,
        "manufacturer": detect_manufacturer(name),
        "type": "CPU",
        "cores": parse_int(row.get("Cores")),
        "threads": parse_int(row.get("Threads")),
        "base_clock_ghz": parse_benchmark_ghz(
            row.get("ClockSpeed")
        ),
        "boost_clock_ghz": parse_benchmark_ghz(
            row.get("TurboSpeed")
        ),
        "tdp_w": parse_watt(row.get("TDP")),
        "socket": normalize_name(row.get("Socket")),
        "release_date": normalize_name(row.get("ReleaseDate")),
        "source_url": row.get("SourceUrl", "").strip() or None,
    }
