"""Tests for the generic component CSV importer (M1 Task 3).

Contracts:
- ``import_component_csv(session_factory, category, csv_path, source_name)``
  returns an ``ImportReport`` dataclass (imported/failed/errors).
- 3 good RAM rows -> imported==3, rows exist with specs, and every populated
  spec field carries a ``field_provenance`` row (table_name=ram_specifications,
  owner source, evidence_status verified).
- Header-only CSV -> imported==0, failed==0, no crash.
- Duplicate hardware (same name+manufacturer+type) -> first imports, second
  lands in errors (unique spec row per hardware).
- One bad row does not kill the batch (per-row isolation).
- Category is a single argument: a mixed-category CSV is rejected per-row.
"""

import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    FieldProvenance,
    Hardware,
    RAMSpecification,
    Source,
)
from backend.app.importers.generic_csv_importer import (
    ImportReport,
    import_component_csv,
)


RAM_HEADER = [
    "name", "manufacturer", "type", "ddr_generation", "capacity_gb",
    "speed_mhz", "modules", "ecc", "voltage_v", "form_factor",
]


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    yield factory
    engine.dispose()


@pytest.fixture()
def owner_source(session_factory):
    from backend.app.seed_sources import ensure_owner_manual_source

    ensure_owner_manual_source(session_factory)
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == "owner-manual"))
    return source


class TestImportReport:
    def test_report_dataclass_shape(self):
        report = ImportReport(imported=1, failed=0, errors=[])
        assert report.imported == 1
        assert report.failed == 0
        assert report.errors == []


class TestImportComponentCSV:
    def test_three_good_ram_rows_import_with_provenance(
        self, session_factory, owner_source, tmp_path
    ):
        csv_path = tmp_path / "ram.csv"
        _write_csv(csv_path, RAM_HEADER, [
            {
                "name": "Corsair Vengeance 32GB", "manufacturer": "Corsair",
                "type": "RAM", "ddr_generation": "DDR5", "capacity_gb": "32",
                "speed_mhz": "6000", "modules": "2", "ecc": "false",
                "voltage_v": "1.35", "form_factor": "UDIMM",
            },
            {
                "name": "G.Skill Trident 16GB", "manufacturer": "G.Skill",
                "type": "RAM", "ddr_generation": "DDR5", "capacity_gb": "16",
                "speed_mhz": "6400", "modules": "2", "ecc": "false",
                "voltage_v": "1.4", "form_factor": "UDIMM",
            },
            {
                "name": "Kingston Fury 8GB", "manufacturer": "Kingston",
                "type": "RAM", "ddr_generation": "DDR4", "capacity_gb": "8",
                "speed_mhz": "3200", "modules": "1", "ecc": "false",
                "voltage_v": "1.2", "form_factor": "UDIMM",
            },
        ])

        report = import_component_csv(session_factory, "ram", csv_path)

        assert report.imported == 3
        assert report.failed == 0
        assert report.errors == []

        with session_factory() as session:
            hardware_rows = session.scalars(
                select(Hardware).where(Hardware.type == "RAM")
            ).all()
            assert len(hardware_rows) == 3

            specs = session.scalars(select(RAMSpecification)).all()
            assert len(specs) == 3

            # Every populated spec field has a provenance row.
            prov = session.scalars(select(FieldProvenance)).all()
            populated_fields = {
                "ddr_generation", "capacity_gb", "speed_mhz", "modules",
                "ecc", "voltage_v", "form_factor",
            }  # all 7 spec fields populated in all 3 rows
            assert len(prov) == 3 * len(populated_fields)
            for row in prov:
                assert row.table_name == "ram_specifications"
                assert row.source_id == owner_source.id
                assert row.evidence_status == "verified"
                assert row.hardware_id is not None

    def test_import_empty_csv_yields_zero_rows(
        self, session_factory, owner_source, tmp_path
    ):
        csv_path = tmp_path / "empty.csv"
        _write_csv(csv_path, RAM_HEADER, [])

        report = import_component_csv(session_factory, "ram", csv_path)

        assert report.imported == 0
        assert report.failed == 0
        assert report.errors == []

        with session_factory() as session:
            assert session.scalar(select(Hardware).where(Hardware.type == "RAM")) is None

    def test_duplicate_hardware_spec_rejected(
        self, session_factory, owner_source, tmp_path
    ):
        csv_path = tmp_path / "dup.csv"
        duplicate = {
            "name": "Corsair Vengeance 32GB", "manufacturer": "Corsair",
            "type": "RAM", "ddr_generation": "DDR5", "capacity_gb": "32",
            "speed_mhz": "6000",
        }
        _write_csv(csv_path, RAM_HEADER, [duplicate, {**duplicate, "speed_mhz": "6400"}])

        report = import_component_csv(session_factory, "ram", csv_path)

        assert report.imported == 1
        assert report.failed == 1
        assert len(report.errors) == 1
        assert "duplicate" in report.errors[0].lower()

    def test_bad_row_does_not_kill_batch(
        self, session_factory, owner_source, tmp_path
    ):
        csv_path = tmp_path / "mixed.csv"
        _write_csv(csv_path, RAM_HEADER, [
            {
                "name": "Good RAM", "manufacturer": "TestCo", "type": "RAM",
                "capacity_gb": "16",
            },
            {
                "name": "Bad RAM", "manufacturer": "TestCo",
                "type": "RAMXX",  # wrong type value
                "capacity_gb": "16",
            },
            {
                "name": "Good RAM 2", "manufacturer": "TestCo", "type": "RAM",
                "capacity_gb": "32",
            },
        ])

        report = import_component_csv(session_factory, "ram", csv_path)

        assert report.imported == 2
        assert report.failed == 1
        assert len(report.errors) == 1
        assert "type" in report.errors[0]

        with session_factory() as session:
            names = session.scalars(
                select(Hardware.name).where(Hardware.type == "RAM")
            ).all()
        assert sorted(names) == ["Good RAM", "Good RAM 2"]

    def test_mixed_category_csv_rejected_per_row(
        self, session_factory, owner_source, tmp_path
    ):
        csv_path = tmp_path / "mixedcat.csv"
        _write_csv(csv_path, RAM_HEADER, [
            {
                "name": "PSU in RAM file", "manufacturer": "Corsair",
                "type": "PSU",  # wrong category for this import
            },
        ])

        report = import_component_csv(session_factory, "ram", csv_path)

        assert report.imported == 0
        assert report.failed == 1
        assert "type" in report.errors[0]

    def test_missing_csv_file_raises(self, session_factory, owner_source, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_component_csv(session_factory, "ram", tmp_path / "nope.csv")

    def test_unknown_category_rejected(self, session_factory, owner_source, tmp_path):
        csv_path = tmp_path / "x.csv"
        _write_csv(csv_path, RAM_HEADER, [])

        with pytest.raises(ValueError, match="category"):
            import_component_csv(session_factory, "ram_x", csv_path)
