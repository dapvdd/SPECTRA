"""Build Planner compatibility engine (M2 Tasks 1-3).

Deterministic, database-write-free compatibility evaluation over the six
Build Planner component categories. Three compatibility states exist;
UNKNOWN is a first-class outcome: missing specification data is never
treated as proof of compatibility.

Structure:
- ``CompatibilityState`` — enum: COMPATIBLE / INCOMPATIBLE / UNKNOWN, plus
  NOT_APPLICABLE (a rule whose required components are absent; its outcome
  is not evidence either way).
- ``RuleResult`` — frozen dataclass with stable serialization: rule id,
  evaluated components, state, human-readable explanation, the spec fields
  consulted, provenance references, and what was missing.
- ``evaluate_rules`` — aggregation: any INCOMPATIBLE -> INCOMPATIBLE; no
  incompatibility but unresolved applicable checks -> UNKNOWN; all
  applicable checks confirmed -> COMPATIBLE.
- ``check_build_compatibility`` — loads specs for the requested component
  IDs and applies the M2 rule set (rule IDs are stable strings, version
  ``M2-RULES-v1``).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

RULES_VERSION = "M2-RULES-v1"

# Component slot names used in requests, rule results, and explanations.
COMPONENT_SLOTS = ("cpu", "gpu", "ram", "storage", "motherboard", "psu")


class CompatibilityState(enum.Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


COMPATIBLE = CompatibilityState.COMPATIBLE
INCOMPATIBLE = CompatibilityState.INCOMPATIBLE
UNKNOWN = CompatibilityState.UNKNOWN
NOT_APPLICABLE = CompatibilityState.NOT_APPLICABLE


@dataclass(frozen=True)
class RuleResult:
    """Outcome of one compatibility rule.

    ``missing_information`` names the spec fields whose absence kept this
    rule UNKNOWN (empty for COMPATIBLE/INCOMPATIBLE/NOT_APPLICABLE).
    """

    rule_id: str
    component_hardware_ids: dict[str, int | None]
    state: CompatibilityState
    explanation: str
    spec_fields: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    provenance: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "component_hardware_ids": dict(self.component_hardware_ids),
            "state": self.state.value,
            "explanation": self.explanation,
            "spec_fields": list(self.spec_fields),
            "missing_information": list(self.missing_information),
            "provenance": [dict(p) for p in self.provenance],
        }


@dataclass(frozen=True)
class CompatibilityReport:
    """Aggregated compatibility outcome for a (partial) build."""

    state: CompatibilityState
    explanation: str
    rules_version: str
    rule_results: tuple[RuleResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "explanation": self.explanation,
            "rules_version": self.rules_version,
            "rule_results": [r.to_dict() for r in self.rule_results],
        }


def evaluate_rules(rules: list[RuleResult]) -> CompatibilityReport:
    """Aggregate rule results with the fixed M2 semantics.

    - Any INCOMPATIBLE -> INCOMPATIBLE (the most safety-relevant outcome wins).
    - Otherwise any UNKNOWN -> UNKNOWN (unresolved required checks).
    - Otherwise (all applicable rules COMPATIBLE, possibly some
      NOT_APPLICABLE) -> COMPATIBLE.
    - No rules at all -> UNKNOWN: an empty build proves nothing.
    """
    if not rules:
        return CompatibilityReport(
            state=UNKNOWN,
            explanation=(
                "No compatibility checks apply: no component pairs with "
                "enough recorded data are selected yet."
            ),
            rules_version=RULES_VERSION,
            rule_results=(),
        )

    states = [rule.state for rule in rules]
    if INCOMPATIBLE in states:
        bad = [r for r in rules if r.state is INCOMPATIBLE]
        return CompatibilityReport(
            state=INCOMPATIBLE,
            explanation=(
                "Incompatible build: "
                + " ".join(r.explanation for r in bad)
            ),
            rules_version=RULES_VERSION,
            rule_results=tuple(rules),
        )
    if UNKNOWN in states:
        unknown = [r for r in rules if r.state is UNKNOWN]
        return CompatibilityReport(
            state=UNKNOWN,
            explanation=(
                "Compatibility could not be fully confirmed: "
                + " ".join(r.explanation for r in unknown)
            ),
            rules_version=RULES_VERSION,
            rule_results=tuple(rules),
        )
    return CompatibilityReport(
        state=COMPATIBLE,
        explanation="All applicable compatibility checks passed.",
        rules_version=RULES_VERSION,
        rule_results=tuple(rules),
    )
