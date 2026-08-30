import re


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None

    value = re.sub(r"\s+", " ", value)

    return value.strip()


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

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*W",
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
    name = normalize_name(row.get("CpuName"))

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