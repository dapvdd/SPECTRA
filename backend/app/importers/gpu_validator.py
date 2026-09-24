ALLOWED_MANUFACTURERS = frozenset(
    {"NVIDIA", "AMD", "Intel", "ATI"}
)


def _is_positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def _is_in_range(value: object, low: float, high: float) -> bool:
    return _is_positive_number(value) and low <= value <= high


def validate_gpu(data: dict[str, object | None]) -> list[str]:
    errors: list[str] = []

    if not data.get("name"):
        errors.append("name is required")

    if data.get("type") != "GPU":
        errors.append("type must be GPU")

    manufacturer = data.get("manufacturer")
    if manufacturer not in ALLOWED_MANUFACTURERS:
        errors.append(
            "manufacturer must be NVIDIA, AMD, Intel, or ATI"
        )

    memory_gb = data.get("memory_gb")
    if memory_gb is not None and not _is_in_range(memory_gb, 1, 128):
        errors.append("memory_gb must be between 1 and 128")

    core_clock = data.get("core_clock_mhz")
    if core_clock is not None and not _is_in_range(core_clock, 100, 4000):
        errors.append("core_clock_mhz must be between 100 and 4000")

    boost_clock = data.get("boost_clock_mhz")
    if boost_clock is not None and not _is_in_range(boost_clock, 100, 4000):
        errors.append("boost_clock_mhz must be between 100 and 4000")

    bandwidth = data.get("vram_bandwidth_gbps")
    if bandwidth is not None and not _is_positive_number(bandwidth):
        errors.append("vram_bandwidth_gbps must be positive")

    tdp_w = data.get("tdp_w")
    if tdp_w is not None and not _is_in_range(tdp_w, 1, 1500):
        errors.append("tdp_w must be between 1 and 1500")

    length_mm = data.get("length_mm")
    if length_mm is not None and not _is_positive_number(length_mm):
        errors.append("length_mm must be positive")

    return errors