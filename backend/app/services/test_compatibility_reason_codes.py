"""M3.2 Task 2 — machine-readable reason codes + new rules R8/R9 (TDD).

Reason codes (stable vocabulary, M32 plan):
- SOCKET_MISMATCH / SOCKET_MATCH
- DDR_GENERATION_MISMATCH / DDR_GENERATION_MATCH
- RAM_CAPACITY_EXCEEDED / RAM_CAPACITY_WITHIN_MAX
- RAM_SLOTS_EXCEEDED / RAM_SLOTS_FIT
- STORAGE_NO_M2_SLOT / STORAGE_M2_SLOT_AVAILABLE
- STORAGE_NO_SATA_PORT / STORAGE_SATA_PORT_AVAILABLE
- PSU_WATTAGE_BELOW_REFERENCE / PSU_WATTAGE_UNKNOWN_ADEQUACY
- GPU_NO_PCIE_SLOT / GPU_SLOT_GENERATION_UNKNOWN
- *_UNKNOWN variants when a rule is UNKNOWN on missing data (field names
  ride in ``missing_information``; the code stays stable)

Contract:
- ``reason_code`` is an optional RuleResult field (backward-compatible:
  omitted/None serializes as None and existing payloads keep their shape).
- Every state a rule can emit maps to exactly one stable code; UNKNOWN from
  missing data uses the rule's ``*_UNKNOWN`` code.
- R8 cpu-motherboard-generation: CPU socket can never imply a CPU
  generation (no generation column exists in the schema), so the rule is
  UNKNOWN unless BOTH sides carry a documented generation; BIOS-dependent
  support is never asserted; it never returns INCOMPATIBLE.
- R9 ram-motherboard-speed: nominal RAM speed above the board's recorded
  max speed is an advisory UNKNOWN, NEVER INCOMPATIBLE (no XMP/QVL data).
"""
import pytest

from backend.app.services.compatibility_model import (
    COMPATIBLE,
    INCOMPATIBLE,
    NOT_APPLICABLE,
    RULES_VERSION,
    UNKNOWN,
    RuleResult,
    evaluate_rules,
)
from backend.app.services.compatibility_rules import (
    RULES,
    rule_cpu_motherboard_generation,
    rule_ram_motherboard_speed,
    rule_cpu_motherboard_socket,
    rule_gpu_motherboard_slot,
    rule_psu_build_wattage,
    rule_ram_motherboard_capacity,
    rule_ram_motherboard_generation,
    rule_ram_motherboard_slots,
    rule_storage_motherboard_interface,
)


class TestReasonCodesExistingRules:
    """Every existing rule emits a stable reason_code for each outcome."""

    def test_socket_match_code(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "AM5"}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.reason_code == "SOCKET_MATCH"

    def test_socket_mismatch_code(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "LGA1700"}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.reason_code == "SOCKET_MISMATCH"

    def test_socket_missing_data_code(self):
        result = rule_cpu_motherboard_socket(
            {"socket": None}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.reason_code == "SOCKET_UNKNOWN"
        assert result.state is UNKNOWN

    def test_generation_match_and_mismatch_codes(self):
        match = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR5"}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        clash = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR4"}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        missing = rule_ram_motherboard_generation(
            {"ddr_generation": None}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        assert match.reason_code == "DDR_GENERATION_MATCH"
        assert clash.reason_code == "DDR_GENERATION_MISMATCH"
        assert missing.reason_code == "DDR_GENERATION_UNKNOWN"

    def test_capacity_codes(self):
        within = rule_ram_motherboard_capacity(
            {"capacity_gb": 64}, {"max_ram_gb": 128},
            ids={"ram": 3, "motherboard": 2},
        )
        over = rule_ram_motherboard_capacity(
            {"capacity_gb": 256}, {"max_ram_gb": 128},
            ids={"ram": 3, "motherboard": 2},
        )
        missing = rule_ram_motherboard_capacity(
            {"capacity_gb": 64}, {"max_ram_gb": None},
            ids={"ram": 3, "motherboard": 2},
        )
        assert within.reason_code == "RAM_CAPACITY_WITHIN_MAX"
        assert over.reason_code == "RAM_CAPACITY_EXCEEDED"
        assert missing.reason_code == "RAM_CAPACITY_UNKNOWN"

    def test_slots_codes(self):
        fit = rule_ram_motherboard_slots(
            {"modules": 2}, {"ram_slots": 4},
            ids={"ram": 3, "motherboard": 2},
        )
        over = rule_ram_motherboard_slots(
            {"modules": 6}, {"ram_slots": 4},
            ids={"ram": 3, "motherboard": 2},
        )
        missing = rule_ram_motherboard_slots(
            {"modules": None}, {"ram_slots": 4},
            ids={"ram": 3, "motherboard": 2},
        )
        assert fit.reason_code == "RAM_SLOTS_FIT"
        assert over.reason_code == "RAM_SLOTS_EXCEEDED"
        assert missing.reason_code == "RAM_SLOTS_UNKNOWN"

    def test_storage_codes(self):
        nvme_ok = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": 2, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        nvme_no = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": 0, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        sata_ok = rule_storage_motherboard_interface(
            {"storage_type": "HDD"}, {"m2_slots": 1, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        sata_no = rule_storage_motherboard_interface(
            {"storage_type": "HDD"}, {"m2_slots": 1, "sata_ports": 0},
            ids={"storage": 4, "motherboard": 2},
        )
        missing = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": None, "sata_ports": None},
            ids={"storage": 4, "motherboard": 2},
        )
        assert nvme_ok.reason_code == "STORAGE_M2_SLOT_AVAILABLE"
        assert nvme_no.reason_code == "STORAGE_NO_M2_SLOT"
        assert sata_ok.reason_code == "STORAGE_SATA_PORT_AVAILABLE"
        assert sata_no.reason_code == "STORAGE_NO_SATA_PORT"
        assert missing.reason_code == "STORAGE_INTERFACE_UNKNOWN"

    def test_psu_codes(self):
        below = rule_psu_build_wattage(
            {"wattage": 450},
            {"cpu": {"tdp_w": 125}, "gpu": {"tdp_w": 250}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        advisory = rule_psu_build_wattage(
            {"wattage": 750},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        no_load = rule_psu_build_wattage(
            {"wattage": 750}, {"cpu": None, "gpu": None},
            ids={"psu": 5, "cpu": None, "gpu": None},
        )
        assert below.reason_code == "PSU_WATTAGE_BELOW_REFERENCE"
        assert advisory.reason_code == "PSU_WATTAGE_UNKNOWN_ADEQUACY"
        assert no_load.reason_code == "PSU_WATTAGE_NOT_APPLICABLE"

    def test_gpu_codes(self):
        unknown_fit = rule_gpu_motherboard_slot(
            {"interface": "PCIe 4.0 x16"}, {"pcie_slots": 2},
            ids={"gpu": 2, "motherboard": 3},
        )
        no_slot = rule_gpu_motherboard_slot(
            {"interface": "PCIe 4.0 x16"}, {"pcie_slots": 0},
            ids={"gpu": 2, "motherboard": 3},
        )
        assert unknown_fit.reason_code == "GPU_SLOT_GENERATION_UNKNOWN"
        assert no_slot.reason_code == "GPU_NO_PCIE_SLOT"


class TestReasonCodeContract:
    def test_reason_code_is_optional_and_defaults_none(self):
        # Backward-compatible construction (M2 call sites keep working).
        result = RuleResult(
            rule_id="x", component_hardware_ids={}, state=UNKNOWN,
            explanation="e",
        )
        assert result.reason_code is None

    def test_to_dict_includes_reason_code(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "AM5"}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        payload = result.to_dict()
        assert payload["reason_code"] == "SOCKET_MATCH"

    def test_every_registered_rule_result_has_a_reason_code(self):
        # A rule result from each registered evaluator must always carry a
        # non-empty reason_code: machine readability is mandatory.
        sample = {
            "cpu-motherboard-socket": rule_cpu_motherboard_socket(
                {"socket": "AM5"}, {"socket": "AM5"},
                ids={"cpu": 1, "motherboard": 2}),
            "ram-motherboard-generation": rule_ram_motherboard_generation(
                {"ddr_generation": "DDR5"}, {"ram_type": "DDR5"},
                ids={"ram": 3, "motherboard": 2}),
            "ram-motherboard-capacity": rule_ram_motherboard_capacity(
                {"capacity_gb": 32}, {"max_ram_gb": 192},
                ids={"ram": 3, "motherboard": 2}),
            "ram-motherboard-slots": rule_ram_motherboard_slots(
                {"modules": 2}, {"ram_slots": 4},
                ids={"ram": 3, "motherboard": 2}),
            "storage-motherboard-interface":
                rule_storage_motherboard_interface(
                    {"storage_type": "NVMe"},
                    {"m2_slots": 2, "sata_ports": 4},
                    ids={"storage": 4, "motherboard": 2}),
            "psu-build-wattage": rule_psu_build_wattage(
                {"wattage": 750},
                {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
                ids={"psu": 5, "cpu": 1, "gpu": 2}),
            "gpu-motherboard-slot": rule_gpu_motherboard_slot(
                {"interface": "PCIe 4.0 x16"}, {"pcie_slots": 2},
                ids={"gpu": 2, "motherboard": 3}),
            "cpu-motherboard-generation":
                rule_cpu_motherboard_generation(
                    {"socket": "AM5", "generation": "Zen 4"},
                    {"socket": "AM5", "chipset": "B650",
                     "cpu_generation_support": "AMD Ryzen 7000 Series"},
                    ids={"cpu": 1, "motherboard": 2}),
            "ram-motherboard-speed": rule_ram_motherboard_speed(
                {"speed_mhz": 5600}, {"max_speed_mhz": 7600},
                ids={"ram": 3, "motherboard": 2}),
        }
        for rule in RULES:
            result = sample[rule.rule_id]
            assert result.reason_code, rule.rule_id
            assert result.reason_code == result.reason_code.upper()

    def test_rules_version_bumped(self):
        # M32 extends the vocabulary; consumers key on the version string.
        assert RULES_VERSION == "M32-RULES-v2"


class TestCpuMotherboardGenerationRule:
    """R8: generation advisory — socket never implies generation."""

    def _rule(self):
        from backend.app.services.compatibility_rules import (
            rule_cpu_motherboard_generation,
        )
        return rule_cpu_motherboard_generation

    def test_registered(self):
        from backend.app.services.compatibility_rules import RULES
        ids = [rule.rule_id for rule in RULES]
        assert "cpu-motherboard-generation" in ids

    def test_missing_generation_data_is_unknown(self):
        rule = self._rule()
        # Realistic M3 shapes: CPU spec has no generation column at all.
        result = rule(
            {"socket": "AM5", "tdp_w": 65},
            {"socket": "AM5", "chipset": "B650"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert result.reason_code == "CPU_GENERATION_UNKNOWN"
        # BIOS-dependent support is never asserted either way.
        text = result.explanation.lower()
        assert "bios" in text
        assert "bios supports" not in text
        assert "bios compatible" not in text

    def test_documented_generation_match_is_compatible(self):
        rule = self._rule()
        result = rule(
            {"socket": "AM5", "generation": "Zen 4"},
            {"socket": "AM5", "chipset": "B650",
             "cpu_generation_support": "AMD Ryzen 9000 & 8000 & 7000"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is COMPATIBLE
        assert result.reason_code == "CPU_GENERATION_MATCH"

    def test_documented_generation_mismatch_is_unknown_never_incompatible(self):
        rule = self._rule()
        # Both sides documented but the board does not list the CPU's
        # generation: without BIOS data this stays an advisory UNKNOWN.
        result = rule(
            {"socket": "AM5", "generation": "Zen 5"},
            {"socket": "AM5", "chipset": "B650",
             "cpu_generation_support": "AMD Ryzen 7000"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert result.reason_code == "CPU_GENERATION_UNKNOWN"
        assert result.state is not INCOMPATIBLE

    def test_absent_components_not_applicable(self):
        rule = self._rule()
        result = rule(None, None, ids={"cpu": None, "motherboard": None})
        assert result.state is NOT_APPLICABLE
        assert result.reason_code == "CPU_GENERATION_NOT_APPLICABLE"


class TestRamMotherboardSpeedRule:
    """R9: nominal speed advisory — above-max speed is NEVER INCOMPATIBLE."""

    def _rule(self):
        from backend.app.services.compatibility_rules import (
            rule_ram_motherboard_speed,
        )
        return rule_ram_motherboard_speed

    def test_registered(self):
        from backend.app.services.compatibility_rules import RULES
        ids = [rule.rule_id for rule in RULES]
        assert "ram-motherboard-speed" in ids

    def test_speed_within_max_is_compatible(self):
        rule = self._rule()
        result = rule(
            {"speed_mhz": 5600}, {"max_speed_mhz": 7600},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE
        assert result.reason_code == "RAM_SPEED_WITHIN_MAX"

    def test_speed_above_max_is_unknown_advisory_never_incompatible(self):
        rule = self._rule()
        result = rule(
            {"speed_mhz": 8000}, {"max_speed_mhz": 6400},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert result.state is not INCOMPATIBLE
        assert result.reason_code == "RAM_SPEED_ABOVE_MAX_ADVISORY"
        text = result.explanation.lower()
        assert "xmp" in text or "expo" in text or "qvl" in text

    def test_missing_speed_data_is_unknown(self):
        rule = self._rule()
        result = rule(
            {"speed_mhz": None}, {"max_speed_mhz": 6400},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert result.reason_code == "RAM_SPEED_UNKNOWN"

    def test_missing_board_max_speed_is_unknown(self):
        rule = self._rule()
        result = rule(
            {"speed_mhz": 5600}, {"max_speed_mhz": None},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert result.reason_code == "RAM_SPEED_UNKNOWN"

    def test_absent_ram_not_applicable(self):
        rule = self._rule()
        result = rule(None, {"max_speed_mhz": 6400},
                      ids={"ram": None, "motherboard": 2})
        assert result.state is NOT_APPLICABLE
        assert result.reason_code == "RAM_SPEED_NOT_APPLICABLE"


class TestAggregationWithReasonCodes:
    def test_report_carries_rule_results_with_reason_codes(self):
        results = [
            rule_cpu_motherboard_socket(
                {"socket": "AM5"}, {"socket": "AM5"},
                ids={"cpu": 1, "motherboard": 2}),
            rule_ram_motherboard_generation(
                {"ddr_generation": "DDR4"}, {"ram_type": "DDR5"},
                ids={"ram": 3, "motherboard": 2}),
        ]
        report = evaluate_rules(results)
        payload = report.to_dict()
        assert payload["state"] == "INCOMPATIBLE"
        codes = {r["reason_code"] for r in payload["rule_results"]}
        assert {"SOCKET_MATCH", "DDR_GENERATION_MISMATCH"} <= codes
