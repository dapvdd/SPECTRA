def validate_cpu(data: dict[str, object | None]) -> list[str]:
    errors: list[str] = []

    if not data.get("name"):
        errors.append("name is required")

    if data.get("manufacturer") not in {"AMD", "Intel"}:
        errors.append("manufacturer must be AMD or Intel")

    if data.get("type") != "CPU":
        errors.append("type must be CPU")

    cores = data.get("cores")
    if cores is not None and (not isinstance(cores, int) or cores <= 0):
        errors.append("cores must be a positive integer")

    threads = data.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        errors.append("threads must be a positive integer")

    base_clock = data.get("base_clock_ghz")
    if base_clock is not None and (
        not isinstance(base_clock, (int, float)) or base_clock <= 0
    ):
        errors.append("base_clock_ghz must be positive")

    boost_clock = data.get("boost_clock_ghz")
    if boost_clock is not None and (
        not isinstance(boost_clock, (int, float)) or boost_clock <= 0
    ):
        errors.append("boost_clock_ghz must be positive")

    tdp = data.get("tdp_w")
    if tdp is not None and (
        not isinstance(tdp, (int, float)) or tdp <= 0
    ):
        errors.append("tdp_w must be positive")

    return errors