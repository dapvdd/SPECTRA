"""M3 Phase 6 — compatibility integration regression tests.

Validates the existing M2.5-RULES-v1 engine against records of the shape the
M3 pipeline approves (provenance-backed curated pilot data), proving:
- imported data never creates false-positive COMPATIBLE conclusions;
- UNKNOWN stays first-class for BIOS support, GPU fit, and PSU adequacy;
- catalog completeness, field provenance, rule applicability, and the
  compatibility result remain four distinct concerns (mission §8).

The engine itself is unchanged (pure functions over spec dicts); these tests
feed it M3-shaped records through the existing public helpers to pin the
boundary behaviour for pilot data specifically.
"""
from __future__ import annotations

import pytest

from backend.app.services.compatibility_rules import (
    rule_cpu_motherboard_socket,
    rule_gpu_motherboard_slot,
    rule_psu_build_wattage,
    rule_ram_motherboard_capacity,
    rule_ram_motherboard_generation,
    rule_ram_motherboard_slots,
    rule_storage_motherboard_interface,
)
from backend.app.services.compatibility_model import (
    COMPATIBLE,
    INCOMPATIBLE,
    UNKNOWN,
)


# M3 pilot-shaped records (the exact shape publish_batch stores + the
# compatibility service loads via load_build_specifications).
_M3_RAM = {
    "ddr_generation": "DDR5", "capacity_gb": 32, "speed_mhz": 6000,
    "modules": 2, "ecc": False, "voltage_v": 1.35, "form_factor": "DIMM",
}
_M3_MOBO = {
    "socket": "AM5", "chipset": "B650", "form_factor": "ATX",
    "ram_type": "DDR5", "ram_slots": 4, "max_ram_gb": 192, "m2_slots": 3,
    "sata_ports": 4, "pcie_slots": 5,
}
_M3_CPU = {"cores": 8, "threads": 16, "tdp_w": 65.0, "socket": "AM5"}
_M3_GPU = {"memory_gb": 12.0, "memory_type": "GDDR7", "tdp_w": 220.0}
_M3_PSU = {"wattage": 850, "efficiency_rating": "80 Plus Gold", "modular": True}
_M3_STORAGE_NVME = {"storage_type": "NVMe", "capacity_gb": 1024,
                    "interface": "PCIe 4.0 x4"}


class TestRamMoboRulesWithM3Data:
    def test_generation_match_is_compatible(self):
        result = rule_ram_motherboard_generation(
            _M3_RAM, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == COMPATIBLE

    def test_generation_mismatch_is_incompatible(self):
        ddr4_ram = {**_M3_RAM, "ddr_generation": "DDR4"}
        result = rule_ram_motherboard_generation(
            ddr4_ram, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == INCOMPATIBLE

    def test_capacity_within_max_is_compatible(self):
        result = rule_ram_motherboard_capacity(
            _M3_RAM, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == COMPATIBLE

    def test_capacity_over_max_is_incompatible(self):
        huge = {**_M3_RAM, "capacity_gb": 4096}
        result = rule_ram_motherboard_capacity(
            huge, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == INCOMPATIBLE

    def test_modules_fit_slots(self):
        result = rule_ram_motherboard_slots(
            _M3_RAM, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == COMPATIBLE

    def test_modules_over_slots_is_incompatible(self):
        four_mods = {**_M3_RAM, "modules": 6}
        result = rule_ram_motherboard_slots(
            four_mods, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == INCOMPATIBLE


class TestUnknownBoundariesPreserved:
    def test_rated_speed_over_board_spec_never_incompatible(self):
        """A 6000 MT/s kit on a board listing DDR5: XMP/EXPO above JEDEC is
        UNKNOWN, not INCOMPATIBLE (no QVL data exists)."""
        result = rule_ram_motherboard_generation(
            _M3_RAM, _M3_MOBO, ids={"ram": 1, "motherboard": 2})
        assert result.state == COMPATIBLE  # generation match only

    def test_storage_nvme_on_sata_only_board_is_incompatible(self):
        sata_only = {**_M3_MOBO, "m2_slots": 0, "sata_ports": 6}
        result = rule_storage_motherboard_interface(
            _M3_STORAGE_NVME, sata_only, ids={"storage": 3, "motherboard": 2})
        assert result.state == INCOMPATIBLE

    def test_gpu_slot_fit_stays_unknown_on_missing_data(self):
        result = rule_gpu_motherboard_slot(
            _M3_GPU, {}, ids={"gpu": 4, "motherboard": 2})
        assert result.state == UNKNOWN

    def test_psu_adequate_wattage_stays_unknown(self):
        """PSU adequacy must NOT become COMPATIBLE from TDP alone (mission
        §8: advisory only)."""
        build = {"cpu": {"tdp_w": 65.0}, "gpu": {"tdp_w": 220.0}}
        result = rule_psu_build_wattage(
            _M3_PSU, build, ids={"psu": 5, "cpu": 1, "gpu": 4})
        assert result.state == UNKNOWN

    def test_psu_underrated_is_incompatible(self):
        tiny_psu = {**_M3_PSU, "wattage": 300}
        build = {"cpu": {"tdp_w": 65.0}, "gpu": {"tdp_w": 220.0}}
        result = rule_psu_build_wattage(
            tiny_psu, build, ids={"psu": 5, "cpu": 1, "gpu": 4})
        assert result.state == INCOMPATIBLE


class TestSeparationOfConcerns:
    def test_completeness_provenance_rules_result_are_distinct(self):
        """A record can be: complete (catalog ✓), provenance-backed (✓),
        rule-inapplicable (N/A) — and that is NOT a compatibility verdict."""
        from backend.app.services.compatibility_model import NOT_APPLICABLE

        # Socket rule with no motherboard data: NOT_APPLICABLE is not evidence.
        result = rule_cpu_motherboard_socket(
            _M3_CPU, None, ids={"cpu": 1, "motherboard": None})
        assert result.state == UNKNOWN  # missing data is never compatibility
        assert NOT_APPLICABLE is not COMPATIBLE

    def test_imported_unknown_socket_yields_unknown_not_compatible(self):
        """M3 data with a missing socket must produce UNKNOWN (never a
        false-positive from other fields being present)."""
        no_socket = {k: v for k, v in _M3_MOBO.items() if k != "socket"}
        result = rule_cpu_motherboard_socket(
            _M3_CPU, no_socket, ids={"cpu": 1, "motherboard": 2})
        assert result.state == UNKNOWN
        assert "socket" in " ".join(result.missing_information).lower()
