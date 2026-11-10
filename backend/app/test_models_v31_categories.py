"""Model tests for the Build Planner M1 categories (RAM/Storage/Mobo/PSU).

Contracts:
- One spec table per category, mirroring cpu_specifications/gpu_specifications:
  FK to hardware.id, nullable + unique (one spec row per hardware max).
- Columns per the design (docs/superpowers/specs/2026-11-10-build-planner-design.md §5 M1).
- Hardware relationships: ram_specification, storage_specification,
  motherboard_specification, psu_specification (uselist=False).
- VALID_TABLES (provenance vocabulary) includes the four new table names.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.database import Base
from backend.app.models import (
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    StorageSpecification,
)
from backend.app.models.provenance import VALID_TABLES


class TestTableNames:
    @pytest.mark.parametrize("model,tablename", [
        (RAMSpecification, "ram_specifications"),
        (StorageSpecification, "storage_specifications"),
        (MotherboardSpecification, "motherboard_specifications"),
        (PSUSpecification, "psu_specifications"),
    ])
    def test_tablename(self, model, tablename):
        assert model.__tablename__ == tablename


class TestRAMColumns:
    def test_design_fields_exist(self):
        for column in (
            "id", "hardware_id", "ddr_generation", "capacity_gb",
            "speed_mhz", "modules", "ecc", "voltage_v", "form_factor",
        ):
            assert column in RAMSpecification.__table__.columns, column

    def test_hardware_id_nullable_unique(self):
        column = RAMSpecification.__table__.columns["hardware_id"]
        assert column.nullable is True
        assert column.unique is True

    def test_validates_ddr_generation(self):
        constraint_names = {
            c.name for c in RAMSpecification.__table__.constraints
        }
        assert any("ddr" in (name or "") for name in constraint_names)


class TestStorageColumns:
    def test_design_fields_exist(self):
        for column in (
            "id", "hardware_id", "storage_type", "capacity_gb",
            "interface", "read_mb_s", "write_mb_s", "dram_cache",
            "form_factor",
        ):
            assert column in StorageSpecification.__table__.columns, column

    def test_hardware_id_nullable_unique(self):
        column = StorageSpecification.__table__.columns["hardware_id"]
        assert column.nullable is True
        assert column.unique is True

    def test_validates_storage_type(self):
        constraint_names = {
            c.name for c in StorageSpecification.__table__.constraints
        }
        assert any("storage_type" in (name or "") for name in constraint_names)


class TestMotherboardColumns:
    def test_design_fields_exist(self):
        for column in (
            "id", "hardware_id", "socket", "chipset", "form_factor",
            "ram_type", "ram_slots", "max_ram_gb", "m2_slots",
            "sata_ports", "pcie_slots",
        ):
            assert column in MotherboardSpecification.__table__.columns, column

    def test_hardware_id_nullable_unique(self):
        column = MotherboardSpecification.__table__.columns["hardware_id"]
        assert column.nullable is True
        assert column.unique is True


class TestPSUColumns:
    def test_design_fields_exist(self):
        for column in (
            "id", "hardware_id", "wattage", "efficiency_rating",
            "modular", "pcie_8pin_count", "pcie_12vhpwr",
        ):
            assert column in PSUSpecification.__table__.columns, column

    def test_hardware_id_nullable_unique(self):
        column = PSUSpecification.__table__.columns["hardware_id"]
        assert column.nullable is True
        assert column.unique is True


class TestHardwareRelationships:
    def test_all_four_relationships_exist(self):
        for name in (
            "ram_specification",
            "storage_specification",
            "motherboard_specification",
            "psu_specification",
        ):
            assert name in Hardware.__mapper__.relationships, name

    @pytest.mark.parametrize("name", [
        "ram_specification",
        "storage_specification",
        "motherboard_specification",
        "psu_specification",
    ])
    def test_relationships_are_uselist_false(self, name):
        assert Hardware.__mapper__.relationships[name].uselist is False


class TestValidTablesExtended:
    @pytest.mark.parametrize("tablename", [
        "ram_specifications",
        "storage_specifications",
        "motherboard_specifications",
        "psu_specifications",
    ])
    def test_new_tables_in_valid_tables(self, tablename):
        assert tablename in VALID_TABLES

    def test_existing_tables_unchanged(self):
        for tablename in (
            "hardware", "cpu_specifications", "gpu_specifications",
            "benchmark_results",
        ):
            assert tablename in VALID_TABLES


class TestModelsRegisteredOnBase:
    def test_all_models_are_on_base_metadata(self):
        for model in (
            RAMSpecification, StorageSpecification,
            MotherboardSpecification, PSUSpecification,
        ):
            assert model.__name__ in Base.metadata.tables or (
                model.__tablename__ in Base.metadata.tables
            )
