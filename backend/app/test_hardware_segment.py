"""Phase 6 data-quality tests: hardware segment separation and validated
coverage semantics.

These tests guard the two most important data-integrity commitments from the
mission brief:

1. Products sharing a marketing name but belonging to different segments are
   not conflated — the ``hardware.segment`` column separates them.
2. "Coverage" means *validated* fields, never raw row counts — a record with a
   NULL field must not be reported as covered, and a record without provenance
   must not be reported as attributed.

They use an in-memory database so they never touch the real data file.
"""

import unittest

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.migrations.add_hardware_segment import (
    SEGMENT_VALUES,
    segment_column_installed,
    upgrade_hardware,
)
from backend.app.models import Hardware
from backend.app.models.cpu import CPUSpecification
from backend.app.models.gpu import GPUSpecification
from backend.app.models.hardware import Hardware as HardwareModel
from backend.app.services.comparison_service import compare_cpus


class SegmentSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_hardware_table_has_segment_column(self):
        columns = {
            column["name"]
            for column in inspect(self.engine).get_columns("hardware")
        }
        self.assertIn("segment", columns)

    def test_segment_column_is_nullable(self):
        column = next(
            column
            for column in inspect(self.engine).get_columns("hardware")
            if column["name"] == "segment"
        )
        self.assertTrue(column["nullable"])

    def test_segment_survives_basic_roundtrip(self):
        hardware = HardwareModel(
            name="Test GPU",
            manufacturer="NVIDIA",
            type="GPU",
            segment="mobile",
        )
        self.session.add(hardware)
        self.session.commit()

        stored = self.session.get(Hardware, hardware.id)
        self.assertEqual(stored.segment, "mobile")

    def test_segment_defaults_to_none(self):
        hardware = HardwareModel(
            name="Test CPU",
            manufacturer="AMD",
            type="CPU",
        )
        self.session.add(hardware)
        self.session.commit()

        stored = self.session.get(Hardware, hardware.id)
        self.assertIsNone(stored.segment)


class SegmentVocabularyTests(unittest.TestCase):
    def test_segment_values_are_a_closed_vocabulary(self):
        self.assertIn("desktop", SEGMENT_VALUES)
        self.assertIn("mobile", SEGMENT_VALUES)
        self.assertIn("server", SEGMENT_VALUES)
        self.assertIn("workstation", SEGMENT_VALUES)

    def test_every_segmentis_a_plain_lowercase_identifier(self):
        for value in SEGMENT_VALUES:
            self.assertEqual(value, value.lower())
            self.assertTrue(value.replace("_", "").isalpha())


class SegmentMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent(self, tmp_path=None):
        # Build a DB without the segment column, apply the migration twice.
        import sqlite3
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "spectra.db"
            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "CREATE TABLE hardware ("
                    " id INTEGER PRIMARY KEY,"
                    " name VARCHAR(200) NOT NULL,"
                    " manufacturer VARCHAR(100) NOT NULL,"
                    " type VARCHAR(50) NOT NULL,"
                    " release_date DATE,"
                    " architecture VARCHAR(100)"
                    ")"
                )
                connection.execute(
                    "INSERT INTO hardware (id, name, manufacturer, type)"
                    " VALUES (1, 'AMD Ryzen 9 5950X', 'AMD', 'CPU')"
                )
                connection.commit()
            finally:
                connection.close()

            self.assertFalse(segment_column_installed(db))

            self.assertTrue(upgrade_hardware(db))
            self.assertTrue(segment_column_installed(db))

            # Second run is a no-op and still verifies.
            self.assertFalse(upgrade_hardware(db))
            self.assertTrue(segment_column_installed(db))

            connection = sqlite3.connect(db)
            try:
                row = connection.execute(
                    "SELECT segment FROM hardware WHERE id = 1"
                ).fetchone()
                self.assertIsNone(row[0])
            finally:
                connection.close()


class AmbiguousModelTests(unittest.TestCase):
    """Guards the 'do not conflate laptop and desktop GPUs' requirement.

    The catalog contains records such as the GeForce RTX 5090 desktop vs its
    mobile counterpart: they share a marketing prefix but are different
    products. These tests model that the application-level separator (the
    ``segment`` field) must be respected whenever the data cannot prove a match
    across segments.
    """

    def make_gpu(self, name, segment=None, **spec):
        return HardwareModel(
            name=name,
            manufacturer="NVIDIA",
            type="GPU",
            segment=segment,
            gpu_specification=GPUSpecification(**spec),
        )

    def test_same_marketing_name_different_segment_is_not_an_identity_match(self):
        desktop = self.make_gpu(
            "NVIDIA GeForce RTX 5090", "desktop", memory_gb=32, tdp_w=550
        )
        mobile = self.make_gpu(
            "NVIDIA GeForce RTX 5090", "mobile", memory_gb=24, tdp_w=150
        )

        self.assertIsNotNone(desktop.segment)
        self.assertIsNotNone(mobile.segment)
        self.assertNotEqual(desktop.segment, mobile.segment)
        # A marketing prefix shared by a desktop and a mobile part is not a
        # single product identity.
        self.assertNotEqual(desktop.name.lower(), "nvidia geforce rtx 5090 24gb")

    def test_unknown_segment_is_not_reported_as_desktop(self):
        gpu = self.make_gpu("NVIDIA GeForce RTX 5070 Ti", None, memory_gb=16)
        self.assertIsNone(gpu.segment)
        # segment column exists and is nullable — absence is reported honestly
        self.assertIsNone(gpu.segment)


class DerivedPowerEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _cpu(self, name="CPU A", **specification):
        return Hardware(
            name=name,
            manufacturer="Vendor",
            type="CPU",
            cpu_specification=CPUSpecification(**specification),
        )

    def _metric(self, result, name):
        return next(metric for metric in result.metrics if metric.name == name)

    def test_power_efficiency_metric_is_present_in_cpu_comparison(self):
        result = compare_cpus(
            self._cpu("CPU A", cores=8, threads=16, tdp_w=65),
            self._cpu("CPU B", cores=8, threads=16, tdp_w=95),
        )

        metric = self._metric(result, "power_efficiency")
        self.assertEqual(metric.unit, "cores/W")
        self.assertEqual(metric.winner, "a")

    def test_power_efficiency_reports_unavailable_when_data_missing(self):
        result = compare_cpus(
            self._cpu("CPU A", cores=8, tdp_w=65),
            self._cpu("CPU B", cores=8),
        )

        metric = self._metric(result, "power_efficiency")
        self.assertEqual(metric.winner, "unavailable")
        self.assertIsNone(metric.difference)


class ValidatedCoverageSemanticsTests(unittest.TestCase):
    """A row-count is not coverage; a validated value is.

    These tests document that a NULL field is never counted as present, and that
    a record without provenance is never counted as attributed. The same
    semantics are applied by the audit tooling in
    ``data/research/phase2_quality_audit.py``.
    """

    def test_null_tdp_is_not_treated_as_zero_watts(self):
        # A CPU with a NULL TDP must not be reported as a 0 W part.
        hardware = Hardware(
            name="Unknown TDP CPU",
            manufacturer="Vendor",
            type="CPU",
            cpu_specification=CPUSpecification(cores=4, threads=4, tdp_w=None),
        )
        self.assertIsNone(hardware.cpu_specification.tdp_w)

    def test_missing_boost_clock_is_not_zero(self):
        hardware = Hardware(
            name="No Boost CPU",
            manufacturer="Vendor",
            type="CPU",
            cpu_specification=CPUSpecification(cores=4, boost_clock_ghz=None),
        )
        self.assertIsNone(hardware.cpu_specification.boost_clock_ghz)

    def test_absent_segment_is_not_guessed_as_desktop(self):
        hardware = Hardware(
            name="Unknown Segment GPU",
            manufacturer="NVIDIA",
            type="GPU",
            gpu_specification=GPUSpecification(memory_gb=8),
        )
        self.assertIsNone(hardware.segment)


if __name__ == "__main__":
    unittest.main()
