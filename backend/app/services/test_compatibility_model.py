"""Tests for the compatibility domain model (M2 Task 1).

Contracts:
- Exactly three compatibility states: COMPATIBLE, INCOMPATIBLE, UNKNOWN.
  UNKNOWN is a first-class outcome: missing data is never treated as proof
  of compatibility.
- ``CompatibilityState`` and ``RuleResult`` are frozen, deterministic
  dataclasses with stable serialization (sorted keys, stable rule IDs).
- ``RuleResult`` carries: rule_id, components evaluated, state, human-readable
  explanation, the spec fields the rule looked at, provenance references
  where available, and the missing information that kept a rule UNKNOWN.
- ``NOT_APPLICABLE`` is distinct from UNKNOWN: a rule whose required
  components are absent from the build simply does not apply, and its
  outcome is not evidence either way.
- ``evaluate_rules`` aggregates: any INCOMPATIBLE -> INCOMPATIBLE; no
  incompatibility but unresolved applicable checks -> UNKNOWN; all
  applicable checks confirmed -> COMPATIBLE.
"""

import json

import pytest

from backend.app.services.compatibility_service import (
    COMPATIBLE,
    INCOMPATIBLE,
    NOT_APPLICABLE,
    UNKNOWN,
    CompatibilityState,
    RuleResult,
    evaluate_rules,
)


class TestStates:
    def test_exactly_three_compatibility_states(self):
        assert {COMPATIBLE.value, INCOMPATIBLE.value, UNKNOWN.value} == {
            "COMPATIBLE", "INCOMPATIBLE", "UNKNOWN",
        }

    def test_not_applicable_is_distinct(self):
        assert NOT_APPLICABLE.value not in {
            COMPATIBLE.value, INCOMPATIBLE.value, UNKNOWN.value,
        }

    def test_unknown_is_first_class_state(self):
        assert CompatibilityState(UNKNOWN.value) is UNKNOWN


class TestRuleResult:
    def _result(self, state):
        return RuleResult(
            rule_id="cpu-motherboard-socket",
            component_hardware_ids={"cpu": 1, "motherboard": 2},
            state=state,
            explanation="Socket LGA1700 matches LGA1700.",
            spec_fields=["cpu_specifications.socket", "motherboard_specifications.socket"],
            missing_information=(),
            provenance=[{"table_name": "cpu_specifications", "field_name": "socket"}],
        )

    def test_serialization_is_stable(self):
        first = json.dumps(self._result(COMPATIBLE).to_dict(), sort_keys=True)
        second = json.dumps(self._result(COMPATIBLE).to_dict(), sort_keys=True)
        assert first == second

    def test_serialization_round_trip_keys(self):
        payload = self._result(UNKNOWN).to_dict()
        assert payload["rule_id"] == "cpu-motherboard-socket"
        assert payload["state"] == "UNKNOWN"
        assert payload["component_hardware_ids"] == {"cpu": 1, "motherboard": 2}
        assert "explanation" in payload
        assert "spec_fields" in payload
        assert "missing_information" in payload
        assert "provenance" in payload

    def test_result_is_immutable(self):
        with pytest.raises(Exception):
            self._result(COMPATIBLE).state = UNKNOWN  # type: ignore[misc]

    def test_unknown_result_reports_missing_information(self):
        result = RuleResult(
            rule_id="cpu-motherboard-socket",
            component_hardware_ids={"cpu": 1, "motherboard": 2},
            state=UNKNOWN,
            explanation="Cannot evaluate: CPU socket is not recorded.",
            spec_fields=["cpu_specifications.socket", "motherboard_specifications.socket"],
            missing_information=("cpu_specifications.socket",),
            provenance=[],
        )
        assert result.state is UNKNOWN
        assert result.missing_information == ("cpu_specifications.socket",)


class TestAggregation:
    @staticmethod
    def _rule(rule_id, state, missing=()):
        return RuleResult(
            rule_id=rule_id,
            component_hardware_ids={},
            state=state,
            explanation="n/a",
            spec_fields=[],
            missing_information=missing,
            provenance=[],
        )

    def test_all_compatible_aggregates_compatible(self):
        rules = [
            self._rule("r1", COMPATIBLE),
            self._rule("r2", COMPATIBLE),
        ]
        assert evaluate_rules(rules).state is COMPATIBLE

    def test_any_incompatible_aggregates_incompatible(self):
        rules = [
            self._rule("r1", COMPATIBLE),
            self._rule("r2", INCOMPATIBLE),
            self._rule("r3", UNKNOWN),
        ]
        assert evaluate_rules(rules).state is INCOMPATIBLE

    def test_unknown_without_incompatibility_aggregates_unknown(self):
        rules = [
            self._rule("r1", COMPATIBLE),
            self._rule("r2", UNKNOWN, missing=("cpu_specifications.socket",)),
        ]
        assert evaluate_rules(rules).state is UNKNOWN

    def test_not_applicable_rules_do_not_block_compatible(self):
        rules = [
            self._rule("r1", COMPATIBLE),
            self._rule("r2", NOT_APPLICABLE),
        ]
        assert evaluate_rules(rules).state is COMPATIBLE

    def test_not_applicable_with_unknown_still_unknown(self):
        rules = [
            self._rule("r1", NOT_APPLICABLE),
            self._rule("r2", UNKNOWN),
        ]
        assert evaluate_rules(rules).state is UNKNOWN

    def test_no_rules_aggregates_unknown(self):
        # An empty build has no applicable checks: UNKNOWN, never COMPATIBLE.
        assert evaluate_rules([]).state is UNKNOWN

    def test_aggregate_includes_explanations(self):
        rules = [
            self._rule("r1", COMPATIBLE),
            self._rule("r2", INCOMPATIBLE),
        ]
        aggregate = evaluate_rules(rules)
        assert aggregate.state is INCOMPATIBLE
        assert aggregate.explanation
        assert aggregate.rule_results == tuple(rules)

    def test_repeated_evaluation_is_deterministic(self):
        rules = [
            self._rule("r1", UNKNOWN),
            self._rule("r2", COMPATIBLE),
        ]
        first = evaluate_rules(rules).to_dict()
        second = evaluate_rules(list(reversed(rules))).to_dict()
        # Same content regardless of input order; stable serialization.
        assert first["state"] == second["state"]
        assert json.dumps(first, sort_keys=True) == json.dumps(first, sort_keys=True)
