import re
import unicodedata

# Control and format characters carry no visible text. They are never part of a
# hardware name, and they survive plain whitespace collapsing because they are
# not Unicode whitespace, so they must be removed explicitly or they silently
# break exact-match identity resolution downstream.
INVISIBLE_CHARACTER_CATEGORIES = frozenset({"Cc", "Cf"})


def strip_invisible_characters(value: str) -> str:
    return "".join(
        character
        for character in value
        if unicodedata.category(character) not in INVISIBLE_CHARACTER_CATEGORIES
    )


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None

    # Collapse whitespace before removing invisible characters so that a
    # control character acting as a separator becomes a space instead of
    # silently joining two words together.
    value = re.sub(r"\s+", " ", value)
    value = strip_invisible_characters(value)

    return value.strip()

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


def parse_watt(value: str | None) -> float | None:
    if not value:
        return None

    # A wattage is a plain non-negative decimal followed by a complete watt
    # unit. The lookbehind rejects digits that belong to a longer numeric
    # token, so a signed value ("-5 W") or scientific notation ("1e3 W") is
    # not silently reduced to a different magnitude. The trailing word
    # boundary rejects a "w" that merely starts a longer word.
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

    match = re.fullmatch(
        r"\s*(\d+)\s*",
        value,
    )

    if not match:
        return None

    return int(match.group(1))


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
