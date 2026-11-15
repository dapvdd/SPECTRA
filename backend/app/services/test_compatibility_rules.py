"""Tests for the M2 hardware compatibility rules (Task 2).

Fixtures are plain dicts shaped like the ORM spec rows — the rules are pure
functions over spec values, so these tests need no database.

Rule IDs are stable strings (M2-RULES-v1):
- cpu-motherboard-socket   CPU socket vs motherboard socket
- ram-motherboard-generation
- ram-motherboard-capacity
- ram-motherboard-slots
- storage-motherboard-interface
- psu-build-wattage        PSU capacity vs CPU+GPU TDP with explicit headroom
- gpu-motherboard-slot     GPU interface needs at least one PCIe slot

Honest boundaries encoded here:
- Missing socket / ddr_generation / ram_type / wattage / tdp -> UNKNOWN with
  the missing field named, never COMPATIBLE.
- Matching socket alone does NOT claim BIOS compatibility: the explanation
  and provenance never assert it.
- Nominal RAM speed never decides incompatibility (no XMP/QVL data).
- M.2 SATA vs NVMe keying is not modeled: only slot availability is checked.
- PSU connector requirements are UNKNOWN (GPU spec lacks connector fields).
"""

import pytest

from backend.app.services.compatibility_service import (
    COMPATIBLE,
    INCOMPATIBLE,
    NOT_APPLICABLE,
    UNKNOWN,
    RuleResult,
)
from backend.app.services.compatibility_rules import (
    RULES,
    rule_cpu_motherboard_socket,
    rule_gpu_motherboard_slot,
    rule_ram_motherboard_capacity,
    rule_ram_motherboard_generation,
    rule_ram_motherboard_slots,
    rule_storage_motherboard_interface,
    rule_psu_build_wattage,
)


class TestCpuMotherboardSocket:
    def test_matching_socket_is_compatible(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "LGA1700"}, {"socket": "LGA1700"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is COMPATIBLE
        assert "LGA1700" in result.explanation

    def test_mismatched_socket_is_incompatible(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "LGA1700"}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE
        assert "LGA1700" in result.explanation
        assert "AM5" in result.explanation

    def test_missing_cpu_socket_is_unknown(self):
        result = rule_cpu_motherboard_socket(
            {"socket": None}, {"socket": "AM5"},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert "cpu_specifications.socket" in result.missing_information

    def test_missing_motherboard_socket_is_unknown(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "AM4"}, {"socket": None},
            ids={"cpu": 1, "motherboard": 2},
        )
        assert result.state is UNKNOWN
        assert "motherboard_specifications.socket" in result.missing_information

    def test_socket_match_does_not_claim_bios_support(self):
        result = rule_cpu_motherboard_socket(
            {"socket": "LGA1700"}, {"socket": "LGA1700"},
            ids={"cpu": 1, "motherboard": 2},
        )
        text = (result.explanation + " " + " ".join(result.spec_fields)).lower()
        # The limitation must be disclosed explicitly, never silently
        # implied away, and no positive BIOS claim may be made.
        assert "bios support is not evaluated" in result.explanation.lower()
        assert "bios compatible" not in text
        assert "bios supports" not in text


class TestRamMotherboardGeneration:
    def test_matching_generation_is_compatible(self):
        result = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR5"}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_mismatched_generation_is_incompatible(self):
        result = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR4"}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_missing_ram_generation_is_unknown(self):
        result = rule_ram_motherboard_generation(
            {"ddr_generation": None}, {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN

    def test_missing_mobo_ram_type_is_unknown(self):
        result = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR5"}, {"ram_type": None},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN

    def test_nominal_speed_never_decides(self):
        # 8000 MHz RAM on a DDR5 board: speed alone proves nothing either way.
        result = rule_ram_motherboard_generation(
            {"ddr_generation": "DDR5", "speed_mhz": 8000},
            {"ram_type": "DDR5"},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE


class TestRamMotherboardCapacity:
    def test_within_max_is_compatible(self):
        result = rule_ram_motherboard_capacity(
            {"capacity_gb": 64}, {"max_ram_gb": 128},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_over_max_is_incompatible(self):
        result = rule_ram_motherboard_capacity(
            {"capacity_gb": 256}, {"max_ram_gb": 128},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_boundary_equal_max_is_compatible(self):
        result = rule_ram_motherboard_capacity(
            {"capacity_gb": 128}, {"max_ram_gb": 128},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_missing_max_is_unknown(self):
        result = rule_ram_motherboard_capacity(
            {"capacity_gb": 64}, {"max_ram_gb": None},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN


class TestRamMotherboardSlots:
    def test_modules_fit_is_compatible(self):
        result = rule_ram_motherboard_slots(
            {"modules": 2}, {"ram_slots": 4},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_more_modules_than_slots_is_incompatible(self):
        result = rule_ram_motherboard_slots(
            {"modules": 4}, {"ram_slots": 2},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_missing_modules_is_unknown(self):
        result = rule_ram_motherboard_slots(
            {"modules": None}, {"ram_slots": 4},
            ids={"ram": 3, "motherboard": 2},
        )
        assert result.state is UNKNOWN


class TestStorageMotherboardInterface:
    def test_nvme_with_m2_slots_is_compatible(self):
        result = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": 2, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_nvme_without_m2_slots_is_incompatible(self):
        result = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": 0, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_sata_ssd_with_sata_ports_is_compatible(self):
        result = rule_storage_motherboard_interface(
            {"storage_type": "SATA SSD"}, {"m2_slots": 1, "sata_ports": 4},
            ids={"storage": 4, "motherboard": 2},
        )
        assert result.state is COMPATIBLE

    def test_hdd_without_sata_ports_is_incompatible(self):
        result = rule_storage_motherboard_interface(
            {"storage_type": "HDD"}, {"m2_slots": 3, "sata_ports": 0},
            ids={"storage": 4, "motherboard": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_missing_slot_counts_is_unknown(self):
        result = rule_storage_motherboard_interface(
            {"storage_type": "NVMe"}, {"m2_slots": None, "sata_ports": None},
            ids={"storage": 4, "motherboard": 2},
        )
        assert result.state is UNKNOWN

    def test_m2_keying_is_not_claimed(self):
        # An M.2 connector count does not prove NVMe protocol support.
        result = rule_storage_motherboard_interface(
            {"storage_type": "SATA SSD", "interface": "M.2 SATA"},
            {"m2_slots": 2, "sata_ports": 0},
            ids={"storage": 4, "motherboard": 2},
        )
        # SATA SSD falls back to sata_ports (0) -> incompatible is honest for
        # SATA ports; but the explanation must not claim M.2 keying detail.
        assert "keying" not in result.explanation.lower()


class TestPsuBuildWattage:
    """M2.5 power semantics: TDP sums are not measured draw.

    Two-tier policy (M2.5-RULES-v1):
    - A PSU at/above the TDP-derived reference can never read COMPATIBLE
      from TDP arithmetic alone -> UNKNOWN (advisory estimate labeled).
    - A PSU below the TDP-derived reference violates a documented hard
      constraint (the 30% reference headroom floor) -> INCOMPATIBLE.
    - Missing wattage or missing TDP -> UNKNOWN, fields named.
    - No CPU/GPU selected -> NOT_APPLICABLE.
    Wording must never claim a measured "draw" or "covers" statement.
    """

    def test_wattage_at_tdp_reference_is_unknown_not_compatible(self):
        result = rule_psu_build_wattage(
            {"wattage": 750},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        assert result.state is UNKNOWN

    def test_grossly_insufficient_wattage_is_incompatible(self):
        # 125 W + 250 W = 375 W TDP; required reference = 488 W. A 450 W PSU
        # fails the documented headroom-floor constraint.
        result = rule_psu_build_wattage(
            {"wattage": 450},
            {"cpu": {"tdp_w": 125}, "gpu": {"tdp_w": 250}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        assert result.state is INCOMPATIBLE

    def test_missing_psu_wattage_is_unknown(self):
        result = rule_psu_build_wattage(
            {"wattage": None},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        assert result.state is UNKNOWN

    def test_missing_gpu_tdp_is_unknown(self):
        result = rule_psu_build_wattage(
            {"wattage": 750},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": None}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        assert result.state is UNKNOWN

    def test_unknown_explanation_is_non_authoritative_and_tdp_labeled(self):
        result = rule_psu_build_wattage(
            {"wattage": 750},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        text = result.explanation.lower()
        assert "non-authoritative" in text
        assert "listed tdp" in text
        assert "draw" not in text
        assert "covers" not in text

    def test_incompatible_explanation_labels_tdp_reference(self):
        result = rule_psu_build_wattage(
            {"wattage": 450},
            {"cpu": {"tdp_w": 125}, "gpu": {"tdp_w": 250}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        text = result.explanation.lower()
        # Names the hard constraint honestly, without measured-draw claims.
        assert "450 w" in text
        assert "488 w" in text
        assert "draw" not in text
        assert "covers" not in text

    def test_missing_connector_info_is_declared(self):
        # PSU connector fields exist in the schema; GPU connector needs do
        # not. The rule must not pretend connectors were evaluated.
        result = rule_psu_build_wattage(
            {"wattage": 750, "pcie_8pin_count": 2, "pcie_12vhpwr": 0},
            {"cpu": {"tdp_w": 65}, "gpu": {"tdp_w": 220}},
            ids={"psu": 5, "cpu": 1, "gpu": 2},
        )
        assert result.state is UNKNOWN
        assert "psu_specifications.pcie_8pin_count" in result.missing_information
        assert "gpu connector" in " ".join(result.missing_information).lower()

    def test_no_gpus_still_evaluates_cpu(self):
        result = rule_psu_build_wattage(
            {"wattage": 300},
            {"cpu": {"tdp_w": 65}, "gpu": None},
            ids={"psu": 5, "cpu": 1, "gpu": None},
        )
        assert result.state is UNKNOWN

    def test_no_cpu_or_gpu_is_not_applicable(self):
        result = rule_psu_build_wattage(
            {"wattage": 750},
            {"cpu": None, "gpu": None},
            ids={"psu": 5, "cpu": None, "gpu": None},
        )
        assert result.state is NOT_APPLICABLE


class TestGpuMotherboardSlot:
    def test_pcie_gpu_with_pcie_slots_is_unknown_slot_agnostic(self):
        # The motherboard schema records only the NUMBER of PCIe slots, not
        # their generation. Slot presence is compatible-ish but generation
        # matching is unknowable, so the honest outcome is UNKNOWN with an
        # explanation.
        result = rule_gpu_motherboard_slot(
            {"interface": "PCIe 4.0 x16"}, {"pcie_slots": 1},
            ids={"gpu": 2, "motherboard": 3},
        )
        assert result.state is UNKNOWN

    def test_gpu_with_zero_pcie_slots_is_incompatible(self):
        result = rule_gpu_motherboard_slot(
            {"interface": "PCIe 4.0 x16"}, {"pcie_slots": 0},
            ids={"gpu": 2, "motherboard": 3},
        )
        assert result.state is INCOMPATIBLE

    def test_missing_gpu_interface_is_unknown(self):
        result = rule_gpu_motherboard_slot(
            {"interface": None}, {"pcie_slots": 1},
            ids={"gpu": 2, "motherboard": 3},
        )
        assert result.state is UNKNOWN


class TestRuleRegistry:
    def test_rules_are_registered_with_stable_ids(self):
        ids = [rule.rule_id for rule in RULES]
        assert ids == [
            "cpu-motherboard-socket",
            "ram-motherboard-generation",
            "ram-motherboard-capacity",
            "ram-motherboard-slots",
            "storage-motherboard-interface",
            "psu-build-wattage",
            "gpu-motherboard-slot",
        ]

    def test_all_rule_ids_unique(self):
        ids = [rule.rule_id for rule in RULES]
        assert len(ids) == len(set(ids))

    def test_registry_descriptions_avoid_measured_power_language(self):
        """The M2.5 power invariant holds for the registry metadata too.

        A listed-TDP sum is not measured draw and a PSU is never described as
        covering it, so no rule description may use that vocabulary either —
        not only the user-facing explanation strings.
        """
        for rule in RULES:
            text = rule.description.lower()
            assert "draw" not in text, rule.rule_id
            assert "covers" not in text, rule.rule_id

    def test_rule_result_requires_ids_and_specs(self):
        # Rules receive ids; results echo them for explainability.
        result: RuleResult = rule_cpu_motherboard_socket(
            {"socket": None}, {"socket": None},
            ids={"cpu": 7, "motherboard": 9},
        )
        assert result.component_hardware_ids == {"cpu": 7, "motherboard": 9}
        assert result.state is UNKNOWN
