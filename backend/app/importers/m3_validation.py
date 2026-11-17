"""M3 Phase 3 — category validation rules.

Implements docs/m3 contract (mission §5): unit semantics, range checks,
cross-field consistency, missing-data classification, source conflict
detection, and deterministic quality scoring. Fail-closed: any CRITICAL-class
problem keeps a record out of the approved publication set.

Design rules:
- pure functions, no I/O;
- unit semantics are enforced honestly: RAM speed is stored in the legacy
  ``speed_mhz`` column but validated as a transfer rate (MT/s) because the
  source documents quote MT/s — the column name is a known historical
  misnomer, documented rather than silently reinterpreted;
- MB/s vs Gb/s: sequential throughput sanity bounds catch the classic
  Gb/s-labeled-as-MB/s transcription error;
- a PSU's ``wattage`` is rated output power, never a TDP claim; values below
  the smallest real ATX envelope fail closed;
- PCIe generation strings are vocabulary, never compatibility claims.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Result primitives
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass
class MissingClassification:
    critical: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    canonical_key: str
    field: str
    values: dict[str, object]  # source_name -> value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Conflict(key={self.canonical_key!r}, field={self.field!r})"


@dataclass
class ValidationOutcome:
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality_score: int | None = None


# ---------------------------------------------------------------------------
# Per-category vocabularies
# ---------------------------------------------------------------------------

# Critical fields: a record missing any of these cannot be APPROVED.
_CRITICAL_FIELDS: dict[str, tuple[str, ...]] = {
    "RAM": ("ddr_generation", "capacity_gb", "speed_mhz", "modules"),
    "STORAGE": ("storage_type", "capacity_gb", "interface"),
    "MOTHERBOARD": ("socket", "form_factor"),
    "PSU": ("wattage", "efficiency_rating"),
}

# Everything spec-level that is not critical is optional (absent stays NULL).
_OPTIONAL_FIELDS: dict[str, tuple[str, ...]] = {
    "RAM": ("ecc", "voltage_v", "form_factor"),
    "STORAGE": ("read_mb_s", "write_mb_s", "dram_cache", "form_factor"),
    "MOTHERBOARD": ("chipset", "ram_type", "ram_slots", "max_ram_gb",
                    "m2_slots", "sata_ports", "pcie_slots"),
    "PSU": ("modular", "pcie_8pin_count", "pcie_12vhpwr"),
}

# Inclusive sanity ranges (unit semantics encoded here; see module docstring).
_RANGES: dict[str, dict[str, tuple[int | float, int | float]]] = {
    "RAM": {
        "capacity_gb": (1, 2048),
        "speed_mhz": (800, 12000),      # MT/s transfer rate sanity
        "modules": (1, 8),
        "voltage_v": (1.0, 2.0),
    },
    "STORAGE": {
        "capacity_gb": (8, 131072),     # 8 GB .. 128 TB
        "read_mb_s": (40, 12500),       # >12,500 MB/s smells like Gb/s
        "write_mb_s": (20, 12500),
    },
    "MOTHERBOARD": {
        "ram_slots": (1, 16),
        "max_ram_gb": (2, 8192),
        "m2_slots": (0, 12),
        "sata_ports": (0, 16),
        "pcie_slots": (0, 12),
    },
    "PSU": {
        "wattage": (100, 8000),         # smallest ATX .. largest known
        "pcie_8pin_count": (0, 12),
        "pcie_12vhpwr": (0, 6),
    },
}

# Cross-field consistency rules; each returns None when consistent, else a
# failure message. Registered per category.
_CROSS_FIELD_RULES: dict[str, tuple] = {}


def _rule_ram_kit_consistency(spec: dict) -> str | None:
    modules, capacity = spec.get("modules"), spec.get("capacity_gb")
    # Fail-closed on malformed (non-numeric) values: a string or bool here
    # becomes an explicit blocker, never a TypeError mid-batch.
    for field_name, value in (("modules", modules), ("capacity_gb", capacity)):
        failure = _type_check_failure(field_name, value)
        if failure:
            return failure
    if modules and capacity and capacity % modules != 0:
        return (
            f"capacity_gb {capacity} is not divisible by modules {modules} "
            "(kit consistency)"
        )
    return None


def _rule_mobo_slots_vs_max_ram(spec: dict) -> str | None:
    slots, max_ram = spec.get("ram_slots"), spec.get("max_ram_gb")
    for field_name, value in (("ram_slots", slots), ("max_ram_gb", max_ram)):
        failure = _type_check_failure(field_name, value)
        if failure:
            return failure
    if slots and max_ram:
        per_slot = max_ram / slots
        # No DIMM larger than 256 GB exists in the desktop DDR4/DDR5 era.
        if per_slot > 256:
            return (
                f"max_ram_gb {max_ram} over {slots} slots implies "
                f"{per_slot:.0f} GB/DIMM — beyond known modules"
            )
    return None


_CROSS_FIELD_RULES["RAM"] = (_rule_ram_kit_consistency,)
_CROSS_FIELD_RULES["MOTHERBOARD"] = (_rule_mobo_slots_vs_max_ram,)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _type_check_failure(field_name: str, value: object) -> str | None:
    """Fail-closed type gate for numeric spec fields.

    Only real int/float values may participate in range comparisons. A
    malformed value (string like ``"32"`` or ``"abc"``, or a bool, which is
    an int subclass and would silently pass as 1) must become an explicit
    rejection reason — never a TypeError that aborts a whole publication
    batch with an opaque traceback. None stays "field absent".
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (
            f"field '{field_name}' has non-numeric value {value!r} "
            f"(type {type(value).__name__}) — refusing to compare; "
            "fix the unit transcription or curate the row"
        )
    return None


def unit_checks(hardware_type: str, spec: dict) -> CheckResult:
    """Unit-semantics validation (MT/s sanity, MB/s vs Gb/s, rated watts)."""
    failures: list[str] = []
    ranges = _RANGES.get(hardware_type, {})
    for field_name, (low, high) in ranges.items():
        value = spec.get(field_name)
        if value is None:
            continue
        type_failure = _type_check_failure(field_name, value)
        if type_failure:
            failures.append(type_failure)
            continue
        if not (low <= value <= high):
            failures.append(
                f"field '{field_name}' value {value} outside unit-sanity range "
                f"[{low}, {high}] — likely a unit confusion (MB/s vs Gb/s, "
                "MHz vs MT/s) or a data error"
            )
    return CheckResult(passed=not failures, failures=failures)


def range_checks(hardware_type: str, spec: dict) -> CheckResult:
    """Type-level range validation (aliases unit_checks' bounds explicitly)."""
    return unit_checks(hardware_type, spec)


def cross_field_checks(hardware_type: str, spec: dict) -> CheckResult:
    """Category-specific consistency rules."""
    failures: list[str] = []
    for rule in _CROSS_FIELD_RULES.get(hardware_type, ()):
        failure = rule(spec)
        if failure:
            failures.append(failure)
    return CheckResult(passed=not failures, failures=failures)


def classify_missing(hardware_type: str, spec: dict) -> MissingClassification:
    """Classify absent fields as critical (blocks approval) or optional."""
    critical = [
        f for f in _CRITICAL_FIELDS.get(hardware_type, ())
        if spec.get(f) in (None, "")
    ]
    optional = [
        f for f in _OPTIONAL_FIELDS.get(hardware_type, ())
        if spec.get(f) in (None, "")
    ]
    return MissingClassification(critical=critical, optional=optional)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def detect_conflicts(records: list[dict]) -> list[Conflict]:
    """Same canonical key + differing fact values -> conflicts (never merged).

    Only compatibility-bearing spec fields participate; identity fields and
    source metadata do not. Records without a canonical key are skipped.
    """
    by_key: dict[str, list[dict]] = {}
    for record in records:
        key = record.get("canonical_key")
        if key:
            by_key.setdefault(key, []).append(record)

    conflicts: list[Conflict] = []
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        record_type = group[0].get("_type", "")
        spec_fields = sorted(
            set(_CRITICAL_FIELDS.get(record_type, ()))
            | set(_OPTIONAL_FIELDS.get(record_type, ()))
        )
        # Fall back to all shared non-meta fields when the type is unknown.
        field_names = spec_fields or sorted(
            {k for r in group for k in r}
            - {"canonical_key", "source_name", "name", "manufacturer", "_type"}
        )
        for field_name in field_names:
            values: dict[str, object] = {}
            for record in group:
                if field_name in record:
                    values[str(record.get("source_name", "?"))] = record[field_name]
            distinct = {repr(v) for v in values.values()}
            if len(distinct) > 1:
                conflicts.append(
                    Conflict(canonical_key=key, field=field_name, values=values)
                )
    return conflicts


# ---------------------------------------------------------------------------
# Quality scoring (deterministic; never manufactures compatibility)
# ---------------------------------------------------------------------------


def quality_score(hardware_type: str, record: dict) -> int:
    """0-100 completeness/verifiability score.

    Deterministic: identical records always score identically. The score
    measures *data completeness*, never compatibility certainty.
    """
    critical = _CRITICAL_FIELDS.get(hardware_type, ())
    optional = _OPTIONAL_FIELDS.get(hardware_type, ())
    if not critical and not optional:
        return 0
    total = len(critical) + len(optional)
    populated_critical = sum(1 for f in critical if record.get(f) not in (None, ""))
    populated_optional = sum(1 for f in optional if record.get(f) not in (None, ""))
    # Critical fields carry 80% of the weight; optional 20%.
    score = round(
        80 * (populated_critical / len(critical)) if critical else 0
        + 20 * (populated_optional / len(optional)) if optional else 0
    )
    # The expression above binds ambiguously without parentheses in Python's
    # conditional expressions; compute defensively:
    score = 0
    if critical:
        score += round(80 * populated_critical / len(critical))
    if optional:
        score += round(20 * populated_optional / len(optional))
    return int(min(score, 100))


# ---------------------------------------------------------------------------
# Fail-closed gate
# ---------------------------------------------------------------------------


def validate_record(
    hardware_type: str, record: dict, *, conflict_free: bool = True,
    identity_confirmed: bool = True,
) -> ValidationOutcome:
    """Full gate: unit + range + cross-field + critical fields + conflicts.

    Returns a ValidationOutcome; ``passed`` False means the record cannot
    enter the approved publication set (fail-closed).
    """
    blockers: list[str] = []
    warnings: list[str] = []

    unit = unit_checks(hardware_type, record)
    blockers += unit.failures

    cross = cross_field_checks(hardware_type, record)
    blockers += cross.failures

    missing = classify_missing(hardware_type, record)
    blockers += [f"critical field missing: {f}" for f in missing.critical]
    warnings += [f"optional field missing: {f}" for f in missing.optional]

    if not conflict_free:
        blockers.append("unresolved source conflict")
    if not identity_confirmed:
        blockers.append("identity not confirmed (provisional)")

    return ValidationOutcome(
        passed=not blockers,
        blockers=blockers,
        warnings=warnings,
        quality_score=quality_score(hardware_type, record),
    )
