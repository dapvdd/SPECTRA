"""MATCH / NEEDS_REVIEW / AMBIGUOUS / NOT_FOUND classifier for Sprint 18B.

Classifies normalized hardware records based on data completeness,
consistency, and recognizability.
"""

from enum import Enum


class Classification(str, Enum):
    MATCH = "MATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


_KNOWN_MANUFACTURERS = {"AMD", "Intel", "NVIDIA", "Apple", "Qualcomm", "ATI"}


def _has_required_cpu_fields(record: dict[str, object | None]) -> list[str]:
    missing = []
    if not record.get("name"):
        missing.append("name")
    if not record.get("manufacturer") or record.get("manufacturer") == "Unknown":
        missing.append("manufacturer")
    if record.get("cores") is None:
        missing.append("cores")
    if record.get("threads") is None:
        missing.append("threads")
    return missing


def _has_required_gpu_fields(record: dict[str, object | None]) -> list[str]:
    missing = []
    if not record.get("name"):
        missing.append("name")
    if not record.get("manufacturer") or record.get("manufacturer") == "Unknown":
        missing.append("manufacturer")
    if record.get("memory_gb") is None:
        missing.append("memory_gb")
    if not record.get("memory_type"):
        missing.append("memory_type")
    return missing


def _has_inconsistent_manufacturer(record: dict[str, object | None]) -> bool:
    name = record.get("name") or ""
    manufacturer = record.get("manufacturer") or ""
    if not name or not manufacturer or manufacturer == "Unknown":
        return False
    name_upper = name.upper()
    for known_mfr in _KNOWN_MANUFACTURERS:
        if known_mfr.upper() in name_upper and known_mfr != manufacturer:
            return True
    return False


def _has_ambiguous_name(record: dict[str, object | None]) -> bool:
    name = record.get("name") or ""
    if not name:
        return False
    if name.count("(") != name.count(")"):
        return True
    if "?" in name or "unknown" in name.lower():
        return True
    ambiguous_patterns = [
        "engineering sample",
        "engineering",
        "sample",
        "prototype",
        "pre-production",
        "not for sale",
        "n/a",
        "tbd",
    ]
    name_lower = name.lower()
    for pattern in ambiguous_patterns:
        if pattern in name_lower:
            return True
    return False


def classify_cpu(record: dict[str, object | None]) -> tuple[Classification, list[str]]:
    missing = _has_required_cpu_fields(record)
    reasons: list[str] = []

    if missing:
        reasons.append(f"missing required fields: {', '.join(missing)}")

    if _has_inconsistent_manufacturer(record):
        reasons.append("manufacturer inconsistent with name")

    if _has_ambiguous_name(record):
        reasons.append("ambiguous name pattern")

    critical_missing = {"name", "manufacturer"}
    if critical_missing.intersection(missing):
        return Classification.NOT_FOUND, reasons

    if len(missing) >= 2:
        return Classification.NOT_FOUND, reasons

    if missing or _has_ambiguous_name(record):
        return Classification.NEEDS_REVIEW, reasons

    if _has_inconsistent_manufacturer(record):
        return Classification.AMBIGUOUS, reasons

    return Classification.MATCH, reasons


def classify_gpu(record: dict[str, object | None]) -> tuple[Classification, list[str]]:
    missing = _has_required_gpu_fields(record)
    reasons: list[str] = []

    if missing:
        reasons.append(f"missing required fields: {', '.join(missing)}")

    if _has_inconsistent_manufacturer(record):
        reasons.append("manufacturer inconsistent with name")

    if _has_ambiguous_name(record):
        reasons.append("ambiguous name pattern")

    critical_missing = {"name", "manufacturer"}
    if critical_missing.intersection(missing):
        return Classification.NOT_FOUND, reasons

    if len(missing) >= 2:
        return Classification.NOT_FOUND, reasons

    if missing or _has_ambiguous_name(record):
        return Classification.NEEDS_REVIEW, reasons

    if _has_inconsistent_manufacturer(record):
        return Classification.AMBIGUOUS, reasons

    return Classification.MATCH, reasons


def classify_hardware(
    cpus: list[dict[str, object | None]],
    gpus: list[dict[str, object | None]],
) -> list[dict[str, object | None]]:
    results: list[dict[str, object | None]] = []

    for record in cpus:
        classification, reasons = classify_cpu(record)
        results.append(
            {
                "name": record.get("name"),
                "manufacturer": record.get("manufacturer"),
                "type": "CPU",
                "classification": classification.value,
                "reasons": reasons,
            }
        )

    for record in gpus:
        classification, reasons = classify_gpu(record)
        results.append(
            {
                "name": record.get("name"),
                "manufacturer": record.get("manufacturer"),
                "type": "GPU",
                "classification": classification.value,
                "reasons": reasons,
            }
        )

    return results
