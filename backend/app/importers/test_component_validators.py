"""Tests for Build Planner component validators (M1 Task 2).

Contracts:
- ``validate_component_row(category, row) -> dict``: coerces types, strips
  strings, normalizes empty optional fields to None (never ""), and raises
  ``ValueError`` naming the offending field on invalid input.
- ``CATEGORY_TYPES`` maps category -> required ``Hardware.type`` value.
- Identity fields (name, manufacturer) are required for all categories.
- Unknown category or unknown type value is rejected (fail-closed).
- Missing optional spec values are simply absent from the validated dict —
  no fabricated values (anti-goal: jangan mengarang nilai spec).
"""

import pytest

from backend.app.importers.component_validators import (
    CATEGORY_TYPES,
    validate_component_row,
)


class TestCategoryTypes:
    def test_four_categories_mapped(self):
        assert CATEGORY_TYPES == {
            "ram": "RAM",
            "storage": "STORAGE",
            "motherboard": "MOTHERBOARD",
            "psu": "PSU",
        }


class TestRAMValidation:
    def test_valid_row_passes_with_coercion(self):
        row = {
            "name": "Corsair Vengeance 32GB",
            "manufacturer": "Corsair",
            "type": "RAM",
            "ddr_generation": "DDR5",
            "capacity_gb": "32",
            "speed_mhz": "6000",
            "modules": "2",
            "ecc": "false",
            "voltage_v": "1.35",
            "form_factor": "UDIMM",
        }
        out = validate_component_row("ram", row)

        assert out["capacity_gb"] == 32
        assert out["speed_mhz"] == 6000
        assert out["modules"] == 2
        assert out["voltage_v"] == pytest.approx(1.35)
        assert out["ecc"] is False

    def test_empty_optional_fields_normalize_to_none(self):
        out = validate_component_row("ram", {
            "name": "Test RAM",
            "manufacturer": "TestCo",
            "type": "RAM",
            "ddr_generation": "",
            "capacity_gb": " ",
            "speed_mhz": None,
            "modules": "",
            "ecc": "",
            "voltage_v": "",
            "form_factor": "",
        })

        for field in (
            "ddr_generation", "capacity_gb", "speed_mhz", "modules",
            "ecc", "voltage_v", "form_factor",
        ):
            assert field not in out, field

    def test_wrong_typed_value_rejected(self):
        with pytest.raises(ValueError, match="speed_mhz"):
            validate_component_row("ram", {
                "name": "Test RAM",
                "manufacturer": "TestCo",
                "type": "RAM",
                "speed_mhz": "fast",
            })


class TestStorageValidation:
    def test_minimal_good_row_passes(self):
        out = validate_component_row("storage", {
            "name": "Samsung 990 Pro",
            "manufacturer": "Samsung",
            "type": "STORAGE",
            "storage_type": "NVMe",
            "capacity_gb": "1000",
            "interface": "PCIe 4.0 x4",
        })

        assert out["capacity_gb"] == 1000
        assert out["storage_type"] == "NVMe"

    def test_wrong_typed_value_rejected(self):
        with pytest.raises(ValueError, match="read_mb_s"):
            validate_component_row("storage", {
                "name": "Slow disk",
                "manufacturer": "TestCo",
                "type": "STORAGE",
                "read_mb_s": "very fast",
            })

    def test_unknown_storage_type_rejected(self):
        with pytest.raises(ValueError, match="storage_type"):
            validate_component_row("storage", {
                "name": "Mystery drive",
                "manufacturer": "TestCo",
                "type": "STORAGE",
                "storage_type": "TAPE",
            })


class TestMotherboardValidation:
    def test_minimal_good_row_passes(self):
        out = validate_component_row("motherboard", {
            "name": "ASUS ROG Strix Z790",
            "manufacturer": "ASUS",
            "type": "MOTHERBOARD",
            "socket": "LGA1700",
            "chipset": "Z790",
            "ram_type": "DDR5",
            "ram_slots": "4",
        })

        assert out["ram_slots"] == 4
        assert out["socket"] == "LGA1700"

    def test_wrong_typed_value_rejected(self):
        with pytest.raises(ValueError, match="ram_slots"):
            validate_component_row("motherboard", {
                "name": "Board",
                "manufacturer": "ASUS",
                "type": "MOTHERBOARD",
                "ram_slots": "lots",
            })


class TestPSUValidation:
    def test_minimal_good_row_passes(self):
        out = validate_component_row("psu", {
            "name": "Corsair RM850x",
            "manufacturer": "Corsair",
            "type": "PSU",
            "wattage": "850",
            "efficiency_rating": "80 Plus Gold",
            "modular": "true",
        })

        assert out["wattage"] == 850
        assert out["efficiency_rating"] == "80 Plus Gold"
        assert out["modular"] is True

    def test_wrong_typed_value_rejected(self):
        with pytest.raises(ValueError, match="wattage"):
            validate_component_row("psu", {
                "name": "Weak PSU",
                "manufacturer": "Corsair",
                "type": "PSU",
                "wattage": "-5",
            })

    def test_unknown_efficiency_rating_rejected(self):
        with pytest.raises(ValueError, match="efficiency_rating"):
            validate_component_row("psu", {
                "name": "Cheap PSU",
                "manufacturer": "TestCo",
                "type": "PSU",
                "efficiency_rating": "80 Plus Legendary",
            })


class TestFailClosed:
    def test_validator_rejects_unknown_type(self):
        with pytest.raises(ValueError, match="type"):
            validate_component_row("ram", {
                "name": "X",
                "manufacturer": "Y",
                "type": "RAMXX",
            })

    def test_type_must_match_category(self):
        with pytest.raises(ValueError, match="type"):
            validate_component_row("psu", {
                "name": "X",
                "manufacturer": "Y",
                "type": "RAM",
            })

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="category"):
            validate_component_row("mouse", {"name": "M", "manufacturer": "T"})

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            validate_component_row("ram", {
                "manufacturer": "TestCo",
                "type": "RAM",
            })

    def test_missing_manufacturer_raises(self):
        with pytest.raises(ValueError, match="manufacturer"):
            validate_component_row("ram", {
                "name": "Test RAM",
                "type": "RAM",
            })

    def test_blank_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            validate_component_row("ram", {
                "name": "   ",
                "manufacturer": "TestCo",
                "type": "RAM",
            })
