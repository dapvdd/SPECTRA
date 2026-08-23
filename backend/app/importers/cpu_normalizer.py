import re


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None

    value = value.replace("™", "").replace("®", "")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_ghz(value: str | None) -> float | None:
    if not value:
        return None

    value = value.strip()

    match = re.fullmatch(
        r"(?:up\s+to\s+)?(\d+(?:\.\d+)?)\s*GHz",
        value,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1))


def parse_watt(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)\s*W", value, re.IGNORECASE)

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

def normalize_amd_row(row: dict[str, str]) -> dict[str, object | None]:
    return {
        "name": normalize_name(row.get("Model")),
        "manufacturer": "AMD",
        "type": "CPU",
        "cores": parse_int(row.get("# of CPU Cores")),
        "threads": parse_int(row.get("# of Threads")),
        "base_clock_ghz": parse_ghz(row.get("Base Clock")),
        "boost_clock_ghz": parse_ghz(row.get("Max. Boost Clock ¹ ²")),
        "tdp_w": parse_watt(row.get("Default TDP")),
        "socket": normalize_name(row.get("CPU Socket")),
        "release_date": normalize_name(row.get("Launch Date")),
    }

def normalize_intel_row(row: dict[str, str]) -> dict[str, object | None]:
    return {
        "name": normalize_name(row.get("CpuName")),
        "manufacturer": "Intel",
        "type": "CPU",
        "cores": parse_int(row.get("CoreCount")),
        "threads": parse_int(row.get("ThreadCount")),
        "base_clock_ghz": parse_ghz(row.get("ClockSpeed")),
        "boost_clock_ghz": parse_ghz(row.get("ClockSpeedMax")),
        "tdp_w": parse_watt(row.get("MaxTDP")),
        "process_node_nm": parse_int(row.get("Lithography", "").replace("nm", "").strip()),
        "external_id": row.get("CpuId"),
    }