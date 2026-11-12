"""M2 hardware compatibility rules (Task 2).

Pure functions over plain spec dicts — no database access, no I/O, fully
deterministic. Rule IDs are stable strings registered in ``RULES`` (version
``M2-RULES-v1``, see compatibility_service).

Honest boundaries (verified in tests):
- Missing any required field -> UNKNOWN naming the missing field. Missing
  data is never treated as compatibility.
- Socket match does NOT claim BIOS support (no BIOS data exists).
- Nominal RAM speed never decides incompatibility (no XMP/QVL data).
- M.2 keying/protocol per slot is not modeled; only connector counts.
- GPU connector requirements are not evaluated (GPU spec lacks the fields).
- Motherboard records only the NUMBER of PCIe slots, so GPU interface checks
  stop at slot availability and generation matching stays UNKNOWN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from backend.app.services.compatibility_model import (
    COMPATIBLE,
    INCOMPATIBLE,
    NOT_APPLICABLE,
    UNKNOWN,
    CompatibilityState,
    RuleResult,
)

# PSU/TDP reference policy (M2.5): listed CPU/GPU TDP values are not
# measurements of system power draw, so TDP arithmetic can never confirm a
# PSU as COMPATIBLE. It yields a documented, clearly-labeled REFERENCE
# (sum of listed TDPs plus this fraction) with exactly two decisive uses:
# below the reference -> INCOMPATIBLE (hard headroom-floor constraint);
# at/above it -> UNKNOWN (advisory only; measured consumption and connector
# requirements are not recorded). This policy is intentionally simple and
# documented — not a fabrication of load curves.
PSU_TDP_REFERENCE_FRACTION = 0.3

_PCIE_PATTERN_PREFIX = "pcie"


def _missing(state_fields: list[tuple[str, Any]]) -> UNKNOWN | None:
    """Return UNKNOWN marker fields for the first None/absent entries."""
    missing = tuple(name for name, value in state_fields if value is None)
    if missing:
        return missing
    return None


def _make_result(
    rule_id: str,
    ids: dict[str, int | None],
    state: CompatibilityState,
    explanation: str,
    spec_fields: tuple[str, ...],
    missing_information: tuple[str, ...] = (),
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        component_hardware_ids=dict(ids),
        state=state,
        explanation=explanation,
        spec_fields=spec_fields,
        missing_information=missing_information,
        provenance=(),
    )


def rule_cpu_motherboard_socket(
    cpu: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    spec_fields = ("cpu_specifications.socket", "motherboard_specifications.socket")
    missing = _missing([
        ("cpu_specifications.socket", (cpu or {}).get("socket")),
        ("motherboard_specifications.socket", (motherboard or {}).get("socket")),
    ])
    if missing:
        return _make_result(
            "cpu-motherboard-socket", ids, UNKNOWN,
            "Cannot evaluate CPU/motherboard socket fit: socket data is "
            "missing for " + ", ".join(missing) + ".",
            spec_fields, missing,
        )
    cpu_socket, mobo_socket = cpu["socket"], motherboard["socket"]
    if cpu_socket == mobo_socket:
        return _make_result(
            "cpu-motherboard-socket", ids, COMPATIBLE,
            f"CPU socket {cpu_socket} matches motherboard socket {mobo_socket}. "
            "BIOS support is not evaluated (no BIOS compatibility data).",
            spec_fields,
        )
    return _make_result(
        "cpu-motherboard-socket", ids, INCOMPATIBLE,
        f"CPU socket {cpu_socket} does not match motherboard socket "
        f"{mobo_socket}.",
        spec_fields,
    )


def rule_ram_motherboard_generation(
    ram: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    spec_fields = ("ram_specifications.ddr_generation", "motherboard_specifications.ram_type")
    missing = _missing([
        ("ram_specifications.ddr_generation", (ram or {}).get("ddr_generation")),
        ("motherboard_specifications.ram_type", (motherboard or {}).get("ram_type")),
    ])
    if missing:
        return _make_result(
            "ram-motherboard-generation", ids, UNKNOWN,
            "Cannot evaluate RAM/motherboard memory-type fit: data is "
            "missing for " + ", ".join(missing) + ".",
            spec_fields, missing,
        )
    ram_gen, mobo_type = ram["ddr_generation"], motherboard["ram_type"]
    if ram_gen == mobo_type:
        return _make_result(
            "ram-motherboard-generation", ids, COMPATIBLE,
            f"RAM generation {ram_gen} matches motherboard memory support "
            f"{mobo_type}. Rated speed above board specification is not "
            "evaluated (no XMP/QVL data).",
            spec_fields,
        )
    return _make_result(
        "ram-motherboard-generation", ids, INCOMPATIBLE,
        f"RAM generation {ram_gen} does not match motherboard memory "
        f"support {mobo_type}: {ram_gen} modules are physically and "
        f"electrically incompatible with {mobo_type} slots.",
        spec_fields,
    )


def rule_ram_motherboard_capacity(
    ram: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    spec_fields = ("ram_specifications.capacity_gb", "motherboard_specifications.max_ram_gb")
    missing = _missing([
        ("ram_specifications.capacity_gb", (ram or {}).get("capacity_gb")),
        ("motherboard_specifications.max_ram_gb", (motherboard or {}).get("max_ram_gb")),
    ])
    if missing:
        return _make_result(
            "ram-motherboard-capacity", ids, UNKNOWN,
            "Cannot evaluate RAM capacity limit: data is missing for "
            + ", ".join(missing) + ".",
            spec_fields, missing,
        )
    capacity, max_ram = ram["capacity_gb"], motherboard["max_ram_gb"]
    if capacity <= max_ram:
        return _make_result(
            "ram-motherboard-capacity", ids, COMPATIBLE,
            f"RAM capacity {capacity} GB is within the motherboard maximum "
            f"{max_ram} GB.",
            spec_fields,
        )
    return _make_result(
        "ram-motherboard-capacity", ids, INCOMPATIBLE,
        f"RAM capacity {capacity} GB exceeds the motherboard maximum "
        f"{max_ram} GB.",
        spec_fields,
    )


def rule_ram_motherboard_slots(
    ram: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    spec_fields = ("ram_specifications.modules", "motherboard_specifications.ram_slots")
    missing = _missing([
        ("ram_specifications.modules", (ram or {}).get("modules")),
        ("motherboard_specifications.ram_slots", (motherboard or {}).get("ram_slots")),
    ])
    if missing:
        return _make_result(
            "ram-motherboard-slots", ids, UNKNOWN,
            "Cannot evaluate RAM slot fit: data is missing for "
            + ", ".join(missing) + ".",
            spec_fields, missing,
        )
    modules, slots = ram["modules"], motherboard["ram_slots"]
    if modules <= slots:
        return _make_result(
            "ram-motherboard-slots", ids, COMPATIBLE,
            f"{modules} RAM module(s) fit into {slots} slot(s).",
            spec_fields,
        )
    return _make_result(
        "ram-motherboard-slots", ids, INCOMPATIBLE,
        f"{modules} RAM module(s) exceed the {slots} available slot(s).",
        spec_fields,
    )


def rule_storage_motherboard_interface(
    storage: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    spec_fields = (
        "storage_specifications.storage_type",
        "motherboard_specifications.m2_slots",
        "motherboard_specifications.sata_ports",
    )
    storage_type = (storage or {}).get("storage_type")
    m2_slots = (motherboard or {}).get("m2_slots")
    sata_ports = (motherboard or {}).get("sata_ports")

    if storage_type is None:
        missing = ("storage_specifications.storage_type",)
        return _make_result(
            "storage-motherboard-interface", ids, UNKNOWN,
            "Cannot evaluate storage fit: storage_type is not recorded.",
            spec_fields, missing,
        )
    if m2_slots is None and sata_ports is None:
        missing = (
            "motherboard_specifications.m2_slots",
            "motherboard_specifications.sata_ports",
        )
        return _make_result(
            "storage-motherboard-interface", ids, UNKNOWN,
            "Cannot evaluate storage fit: motherboard connector counts are "
            "not recorded.",
            spec_fields, missing,
        )

    if storage_type == "NVMe":
        if m2_slots is None:
            missing = ("motherboard_specifications.m2_slots",)
            return _make_result(
                "storage-motherboard-interface", ids, UNKNOWN,
                "Cannot evaluate NVMe fit: m2_slots is not recorded for the "
                "motherboard.",
                spec_fields, missing,
            )
        if m2_slots > 0:
            return _make_result(
                "storage-motherboard-interface", ids, COMPATIBLE,
                f"NVMe storage can use one of {m2_slots} M.2 slot(s). "
                "Per-slot M.2 keying/protocol is not modeled.",
                spec_fields,
            )
        return _make_result(
            "storage-motherboard-interface", ids, INCOMPATIBLE,
            "NVMe storage requires an M.2 slot but the motherboard records "
            "0.",
            spec_fields,
        )

    # SATA SSD / HDD: needs a SATA port (an M.2 SATA keying map does not
    # exist in this schema, so M.2-borne SATA is not claimed either way).
    if sata_ports is None:
        missing = ("motherboard_specifications.sata_ports",)
        return _make_result(
            "storage-motherboard-interface", ids, UNKNOWN,
            "Cannot evaluate SATA storage fit: sata_ports is not recorded "
            "for the motherboard.",
            spec_fields, missing,
        )
    if sata_ports > 0:
        return _make_result(
            "storage-motherboard-interface", ids, COMPATIBLE,
            f"{storage_type} can use one of {sata_ports} SATA port(s).",
            spec_fields,
        )
    return _make_result(
        "storage-motherboard-interface", ids, INCOMPATIBLE,
        f"{storage_type} requires a SATA port but the motherboard records "
        "0.",
        spec_fields,
    )


def rule_psu_build_wattage(
    psu: dict[str, Any] | None,
    build: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    """PSU rated capacity vs a listed-TDP reference (two-tier, M2.5).

    Listed CPU/GPU TDP values are manufacturer ratings, not measurements of
    system power draw, and their sum is not a validated PSU requirement.
    Therefore:

    - wattage below the TDP reference (sum + PSU_TDP_REFERENCE_FRACTION)
      violates the documented headroom-floor constraint -> INCOMPATIBLE;
    - wattage at/above the reference -> UNKNOWN: the estimate is advisory
      and non-authoritative (no measured consumption, no connector data);
    - missing wattage or a missing TDP for a present component -> UNKNOWN;
    - no CPU/GPU selected -> NOT_APPLICABLE.

    GPU connector needs are not recorded in the schema, so connector fit is
    always declared missing information, never silently skipped.
    """
    spec_fields = (
        "psu_specifications.wattage",
        "cpu_specifications.tdp_w",
        "gpu_specifications.tdp_w",
    )
    wattage = (psu or {}).get("wattage")
    if wattage is None:
        missing = ("psu_specifications.wattage",)
        return _make_result(
            "psu-build-wattage", ids, UNKNOWN,
            "Cannot evaluate PSU capacity: wattage is not recorded.",
            spec_fields, missing,
        )

    tdp_parts: list[str] = []
    total_tdp = 0
    missing: list[str] = []
    for slot in ("cpu", "gpu"):
        spec = (build or {}).get(slot)
        if not spec:
            continue
        tdp = spec.get("tdp_w")
        if tdp is None:
            missing.append(f"{slot}_specifications.tdp_w")
        else:
            total_tdp += tdp
            tdp_parts.append(f"{slot.upper()} {tdp} W listed TDP")

    if missing:
        return _make_result(
            "psu-build-wattage", ids, UNKNOWN,
            "Cannot evaluate PSU capacity: listed TDP is not recorded for "
            + ", ".join(missing) + ".",
            spec_fields, tuple(missing),
        )
    if not tdp_parts:
        return _make_result(
            "psu-build-wattage", ids, NOT_APPLICABLE,
            "No CPU/GPU selected yet: PSU capacity check has nothing to "
            "size against.",
            spec_fields,
        )

    reference = math.floor(total_tdp * (1 + PSU_TDP_REFERENCE_FRACTION) + 0.5)
    connector_gaps = (
        "psu_specifications.pcie_8pin_count",
        "psu_specifications.pcie_12vhpwr",
        "gpu connector requirements",
    )
    connector_note = (
        " Connector requirements are not evaluated: PSU connector counts and "
        "GPU connector needs are not recorded for this comparison."
    )
    if wattage < reference:
        return _make_result(
            "psu-build-wattage", ids, INCOMPATIBLE,
            f"PSU {wattage} W is below the documented reference floor of "
            f"{reference} W (sum of listed TDPs {total_tdp} W — "
            f"{', '.join(tdp_parts)} — plus "
            f"{int(PSU_TDP_REFERENCE_FRACTION * 100)}% reference headroom; "
            "listed TDP values are not measured power consumption)."
            + connector_note,
            spec_fields, connector_gaps,
        )
    return _make_result(
        "psu-build-wattage", ids, UNKNOWN,
        f"PSU {wattage} W meets the non-authoritative reference of "
        f"{reference} W (sum of listed TDPs {total_tdp} W — "
        f"{', '.join(tdp_parts)} — plus "
        f"{int(PSU_TDP_REFERENCE_FRACTION * 100)}%), but listed TDP values "
        "are not measured power consumption and connector requirements are "
        "unknown, so compatibility cannot be confirmed." + connector_note,
        spec_fields, connector_gaps,
    )


def rule_gpu_motherboard_slot(
    gpu: dict[str, Any] | None,
    motherboard: dict[str, Any] | None,
    *,
    ids: dict[str, int | None],
) -> RuleResult:
    """GPU interface vs motherboard PCIe slot availability.

    The motherboard schema records only the number of PCIe slots, not their
    generation. Zero slots -> INCOMPATIBLE; otherwise UNKNOWN (generation
    matching and physical clearance are unknowable from this schema).
    """
    spec_fields = (
        "gpu_specifications.interface",
        "motherboard_specifications.pcie_slots",
    )
    interface = (gpu or {}).get("interface")
    pcie_slots = (motherboard or {}).get("pcie_slots")
    missing = _missing([
        ("gpu_specifications.interface", interface),
        ("motherboard_specifications.pcie_slots", pcie_slots),
    ])
    if missing:
        return _make_result(
            "gpu-motherboard-slot", ids, UNKNOWN,
            "Cannot evaluate GPU slot fit: data is missing for "
            + ", ".join(missing) + ".",
            spec_fields, missing,
        )
    if not str(interface).lower().startswith(_PCIE_PATTERN_PREFIX):
        # Apple MPX etc.: on-board packaging, not a PCIe card.
        return _make_result(
            "gpu-motherboard-slot", ids, NOT_APPLICABLE,
            f"GPU interface {interface} is not a PCIe card; slot rule does "
            "not apply.",
            spec_fields,
        )
    if pcie_slots > 0:
        return _make_result(
            "gpu-motherboard-slot", ids, UNKNOWN,
            f"GPU {interface} needs a PCIe slot: {pcie_slots} slot(s) "
            "recorded, but slot generation and clearance are not modeled, "
            "so the fit cannot be confirmed.",
            spec_fields,
        )
    return _make_result(
        "gpu-motherboard-slot", ids, INCOMPATIBLE,
        "GPU requires a PCIe slot but the motherboard records 0.",
        spec_fields,
    )


@dataclass(frozen=True)
class Rule:
    """One registered rule: stable id + evaluator entry point."""

    rule_id: str
    description: str
    evaluate: Callable[..., RuleResult]


RULES: tuple[Rule, ...] = (
    Rule(
        "cpu-motherboard-socket",
        "CPU socket vs motherboard socket (BIOS support not modeled).",
        rule_cpu_motherboard_socket,
    ),
    Rule(
        "ram-motherboard-generation",
        "RAM DDR generation vs motherboard supported memory type.",
        rule_ram_motherboard_generation,
    ),
    Rule(
        "ram-motherboard-capacity",
        "RAM total capacity vs motherboard maximum.",
        rule_ram_motherboard_capacity,
    ),
    Rule(
        "ram-motherboard-slots",
        "RAM module count vs motherboard slot count.",
        rule_ram_motherboard_slots,
    ),
    Rule(
        "storage-motherboard-interface",
        "Storage connector need vs motherboard connector counts.",
        rule_storage_motherboard_interface,
    ),
    Rule(
        "psu-build-wattage",
        "PSU capacity vs CPU+GPU draw with 30% headroom policy.",
        rule_psu_build_wattage,
    ),
    Rule(
        "gpu-motherboard-slot",
        "GPU PCIe interface vs motherboard slot availability.",
        rule_gpu_motherboard_slot,
    ),
)
