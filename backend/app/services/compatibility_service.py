"""Build Planner compatibility engine (M2 Tasks 1-3).

Deterministic, database-write-free compatibility evaluation over the six
Build Planner component categories. Three compatibility states exist;
UNKNOWN is a first-class outcome: missing specification data is never
treated as proof of compatibility.

Structure:
- ``CompatibilityState`` â€” enum: COMPATIBLE / INCOMPATIBLE / UNKNOWN, plus
  NOT_APPLICABLE (a rule whose required components are absent; its outcome
  is not evidence either way).
- ``RuleResult`` â€” frozen dataclass with stable serialization: rule id,
  evaluated components, state, human-readable explanation, the spec fields
  consulted, provenance references, and what was missing.
- ``evaluate_rules`` â€” aggregation: any INCOMPATIBLE -> INCOMPATIBLE; no
  incompatibility but unresolved applicable checks -> UNKNOWN; all
  applicable checks confirmed -> COMPATIBLE.
- ``check_build_compatibility`` â€” loads specs for the requested component
  IDs and applies the M2 rule set (rule IDs are stable strings, version
  ``M2-RULES-v1``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.app.database import SessionLocal  # noqa: F401  (monkeypatch target)
from backend.app.models import (
    CPUSpecification,
    GPUSpecification,
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    StorageSpecification,
)
from backend.app.services.compatibility_model import (  # noqa: F401  (re-export)
    COMPATIBLE,
    COMPONENT_SLOTS,
    INCOMPATIBLE,
    NOT_APPLICABLE,
    RULES_VERSION,
    UNKNOWN,
    CompatibilityReport,
    CompatibilityState,
    RuleResult,
    evaluate_rules,
)
from backend.app.services.compatibility_rules import (
    rule_cpu_motherboard_socket,
    rule_gpu_motherboard_slot,
    rule_psu_build_wattage,
    rule_ram_motherboard_capacity,
    rule_ram_motherboard_generation,
    rule_ram_motherboard_slots,
    rule_storage_motherboard_interface,
)

# hardware.type -> spec relationship attribute on Hardware + ORM class.
_SPEC_BY_TYPE = {
    "CPU": ("cpu_specification", CPUSpecification),
    "GPU": ("gpu_specification", GPUSpecification),
    "RAM": ("ram_specification", RAMSpecification),
    "STORAGE": ("storage_specification", StorageSpecification),
    "MOTHERBOARD": ("motherboard_specification", MotherboardSpecification),
    "PSU": ("psu_specification", PSUSpecification),
}

# Request slot name -> hardware.type
_SLOT_TYPE = {
    "cpu": "CPU",
    "gpu": "GPU",
    "ram": "RAM",
    "storage": "STORAGE",
    "motherboard": "MOTHERBOARD",
    "psu": "PSU",
}



def load_build_specifications(
    session: Any,
    component_ids: dict[str, int | None],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Load spec rows for the requested component IDs.

    Returns ``(specs, ids_by_slot)`` where ``specs`` maps slot name -> spec
    dict (with ``hardware_id`` and ``name`` included) for every component
    that exists *and* belongs to the right category, and ``ids_by_slot``
    maps slot name -> hardware id for all provided (non-None) IDs.

    Raises:
        LookupError: slot names a hardware id that does not exist.
        ValueError: a hardware id exists but its type does not match the
            slot's expected category.
    """
    provided = {
        slot: component_ids[slot] for slot in COMPONENT_SLOTS if component_ids.get(slot) is not None
    }
    if not provided:
        return {}, {}

    ids = list(provided.values())
    rows = session.execute(
        select(Hardware.id, Hardware.type, Hardware.name).where(Hardware.id.in_(ids))
    ).all()
    row_by_id = {row[0]: (row[1], row[2]) for row in rows}

    for slot, hardware_id in provided.items():
        if hardware_id not in row_by_id:
            raise LookupError(
                f"No hardware record found for slot '{slot}' (id {hardware_id})."
            )
        expected = _SLOT_TYPE[slot]
        actual = row_by_id[hardware_id][0]
        if actual != expected:
            raise ValueError(
                f"Hardware id {hardware_id} for slot '{slot}' is type "
                f"'{actual}', expected '{expected}'."
            )

    specs: dict[str, dict[str, Any]] = {}
    for slot, hardware_id in provided.items():
        hardware_type, name = row_by_id[hardware_id]
        rel_name, spec_cls = _SPEC_BY_TYPE[hardware_type]
        spec_row = session.execute(
            select(spec_cls).where(spec_cls.hardware_id == hardware_id)
        ).scalar_one_or_none()
        spec_dict = {"hardware_id": hardware_id, "name": name}
        if spec_row is not None:
            for column in spec_cls.__table__.columns:
                if column.name in ("id", "hardware_id"):
                    continue
                spec_dict[column.name] = getattr(spec_row, column.name)
        specs[slot] = spec_dict
    return specs, provided


def _provenance_for_fields(
    session: Any, hardware_ids: list[int], fields: list[str]
) -> list[dict[str, Any]]:
    """Fetch provenance rows for the (table_name, field_name) pairs a rule used."""
    if not hardware_ids or not fields:
        return []
    field_pairs = [
        tuple(f.split(".", 1)) for f in fields if "." in f
    ]
    if not field_pairs:
        return []
    from backend.app.models import FieldProvenance  # local import: avoid cycles

    rows = session.execute(
        select(FieldProvenance).where(
            FieldProvenance.hardware_id.in_(hardware_ids),
            FieldProvenance.benchmark_result_id.is_(None),
        )
    ).scalars().all()
    wanted = set(field_pairs)
    return [
        {
            "table_name": row.table_name,
            "field_name": row.field_name,
            "evidenced_value": row.evidenced_value,
            "evidence_status": row.evidence_status,
            "source_url": row.source_url,
        }
        for row in rows
        if (row.table_name, row.field_name) in wanted
    ]


def check_build_compatibility(component_ids: dict[str, int | None]) -> dict[str, Any]:
    """Load specs and apply the M2 rule set; returns the report dict.

    Read-only: opens its own session, never writes, always closes.
    Raises LookupError / ValueError for bad IDs (mapped to 404 / 422 by the
    API layer).
    """
    with SessionLocal() as session:
        specs, provided = load_build_specifications(session, component_ids)
        ids_echo: dict[str, int | None] = {
            slot: provided.get(slot) for slot in COMPONENT_SLOTS
        }

        cpu = specs.get("cpu")
        gpu = specs.get("gpu")
        ram = specs.get("ram")
        storage = specs.get("storage")
        motherboard = specs.get("motherboard")
        psu = specs.get("psu")

        present = set(provided)
        results: list[RuleResult] = []

        def ids_for(*slots: str) -> dict[str, int | None]:
            return {slot: provided.get(slot) for slot in slots}

        # R1: CPU x Motherboard socket.
        if {"cpu", "motherboard"} <= present:
            results.append(
                rule_cpu_motherboard_socket(cpu, motherboard, ids=ids_for("cpu", "motherboard"))
            )
        # R2-R4: RAM x Motherboard.
        if {"ram", "motherboard"} <= present:
            results.append(
                rule_ram_motherboard_generation(ram, motherboard, ids=ids_for("ram", "motherboard"))
            )
            results.append(
                rule_ram_motherboard_capacity(ram, motherboard, ids=ids_for("ram", "motherboard"))
            )
            results.append(
                rule_ram_motherboard_slots(ram, motherboard, ids=ids_for("ram", "motherboard"))
            )
        # R5: Storage x Motherboard.
        if {"storage", "motherboard"} <= present:
            results.append(
                rule_storage_motherboard_interface(
                    storage, motherboard, ids=ids_for("storage", "motherboard")
                )
            )
        # R6: PSU x build draw (needs PSU + at least one of CPU/GPU).
        if psu is not None and (cpu is not None or gpu is not None):
            results.append(
                rule_psu_build_wattage(
                    psu,
                    {"cpu": cpu, "gpu": gpu},
                    ids=ids_for("psu", "cpu", "gpu"),
                )
            )
        # R7: GPU x Motherboard slot availability.
        if {"gpu", "motherboard"} <= present:
            results.append(
                rule_gpu_motherboard_slot(gpu, motherboard, ids=ids_for("gpu", "motherboard"))
            )

        report = evaluate_rules(results)

        # Attach provenance (read-only) for the fields each rule consulted.
        rule_dicts = []
        involved_ids = [v for v in provided.values() if v is not None]
        for rule in report.rule_results:
            rule_dict = rule.to_dict()
            rule_dict["provenance"] = _provenance_for_fields(
                session, involved_ids, list(rule.spec_fields)
            )
            rule_dicts.append(rule_dict)

        payload = report.to_dict()
        payload["rule_results"] = rule_dicts
        return payload

