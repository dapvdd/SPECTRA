import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.importers.gpu_batch_importer import import_gpu_csv
from backend.app.importers.gpu_csv import REQUIRED_COLUMNS
from backend.app.importers.gpu_importer import (
    GPU_SOURCE_NAME,
    GPU_SOURCE_URL,
    get_or_create_gpu_source,
    import_gpu,
)
from backend.app.models import (
    CPUSpecification,
    ExternalIdentifier,
    GPUSpecification,
    Hardware,
    Source,
)

VALID_RECORD = {
    "name": "GeForce RTX 5090",
    "manufacturer": "NVIDIA",
    "type": "GPU",
    "release_date": "2025-01-30",
    "architecture": "Blackwell 2.0",
    "memory_gb": 32.0,
    "memory_type": "GDDR7",
    "core_clock_mhz": None,
    "boost_clock_mhz": 2407.0,
    "vram_bandwidth_gbps": 1790.0,
    "tdp_w": 575.0,
    "interface": "PCIe 5.0 x16",
    "length_mm": 304.0,
}


def _raw_row(updates=None):
    row = {
        "Brand": "NVIDIA",
        "Name": "GeForce RTX 5090",
        "Graphics Card__Release Date": "Jan 30th, 2025",
        "Graphics Processor__Architecture": "Blackwell 2.0",
        "Memory__Memory Size": "32 GB",
        "Memory__Memory Type": "GDDR7",
        "Memory__Bandwidth": "1.79 TB/s",
        "Clock Speeds__GPU Clock": "",
        "Clock Speeds__Boost Clock": "2407 MHz",
        "Board Design__TDP": "575 W",
        "Graphics Card__Bus Interface": "PCIe 5.0 x16",
        "Board Design__Length": "304 mm 12 inches",
    }
    if updates:
        row.update(updates)
    return row


def _write_csv(rows) -> Path:
    file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".csv",
        delete=False,
    )
    writer = csv.DictWriter(file, fieldnames=list(REQUIRED_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    file.close()
    return Path(file.name)


class GpuImporterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.paths = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for path in self.paths:
            path.unlink(missing_ok=True)
        self.engine.dispose()

    def _track(self, path: Path) -> Path:
        self.paths.append(path)
        return path

    def _source_id(self) -> int:
        with self.session_factory() as session:
            source = get_or_create_gpu_source(session)
            session.commit()
            return source.id

    def _add_cpu(self, name="Ryzen 5 5600", manufacturer="AMD"):
        hardware = Hardware(
            name=name,
            manufacturer=manufacturer,
            type="CPU",
        )
        hardware.cpu_specification = CPUSpecification(
            cores=6,
            threads=12,
            base_clock_ghz=3.5,
            boost_clock_ghz=4.4,
        )
        with self.session_factory() as session:
            session.add(hardware)
            session.commit()

    def _count(self, model) -> int:
        with self.session_factory() as session:
            return session.scalar(select(func.count()).select_from(model))

    def test_single_valid_gpu_import(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            inserted = import_gpu(
                VALID_RECORD,
                source_id=source_id,
                session=session,
            )
            session.commit()

        self.assertTrue(inserted)

        with self.session_factory() as session:
            hardware = session.scalar(
                select(Hardware).where(
                    Hardware.name == "GeForce RTX 5090"
                )
            )
            self.assertIsNotNone(hardware)
            self.assertEqual(hardware.type, "GPU")
            self.assertEqual(hardware.manufacturer, "NVIDIA")
            self.assertEqual(hardware.release_date, date(2025, 1, 30))
            self.assertEqual(hardware.architecture, "Blackwell 2.0")

    def test_gpu_and_specification_creation(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            inserted = import_gpu(
                VALID_RECORD,
                source_id=source_id,
                session=session,
            )
            session.commit()

        self.assertTrue(inserted)

        with self.session_factory() as session:
            specification = session.scalar(select(GPUSpecification))
            self.assertIsNotNone(specification)
            self.assertEqual(specification.memory_gb, 32.0)
            self.assertEqual(specification.memory_type, "GDDR7")
            self.assertEqual(specification.boost_clock_mhz, 2407.0)
            self.assertEqual(specification.vram_bandwidth_gbps, 1790.0)
            self.assertEqual(specification.tdp_w, 575.0)
            self.assertEqual(specification.interface, "PCIe 5.0 x16")
            self.assertEqual(specification.length_mm, 304.0)
            self.assertIsNone(specification.core_clock_mhz)
            hardware = specification.hardware
            self.assertEqual(hardware.type, "GPU")
            self.assertIs(hardware.gpu_specification, specification)

    def test_source_registration_and_provenance(self):
        with self.session_factory() as session:
            first = get_or_create_gpu_source(session)
            session.commit()
            first_id = first.id

        with self.session_factory() as session:
            second = get_or_create_gpu_source(session)
            session.commit()
            second_id = second.id

        self.assertEqual(first_id, second_id)
        with self.session_factory() as session:
            sources = session.scalars(select(Source)).all()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].name, GPU_SOURCE_NAME)
            self.assertEqual(sources[0].url, GPU_SOURCE_URL)

    def test_no_external_identifiers_are_fabricated(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            import_gpu(VALID_RECORD, source_id=source_id, session=session)
            session.commit()

        self.assertEqual(self._count(ExternalIdentifier), 0)

    def test_duplicate_gpu_prevention(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            first = import_gpu(
                VALID_RECORD, source_id=source_id, session=session
            )
            session.commit()

        with self.session_factory() as session:
            second = import_gpu(
                VALID_RECORD, source_id=source_id, session=session
            )
            session.commit()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(self._count(Hardware), 1)
        self.assertEqual(self._count(GPUSpecification), 1)

    def test_idempotent_batch_reimport(self):
        source_id = self._source_id()
        path = self._track(_write_csv([
            _raw_row(),
            _raw_row({"Name": "GeForce RTX 5080", "Memory__Memory Size": "16 GB", "Memory__Bandwidth": "960.0 GB/s", "Clock Speeds__Boost Clock": "2617 MHz", "Board Design__TDP": "360 W"}),
        ]))

        first = import_gpu_csv(path, source_id=source_id,
                               session=self.session_factory())
        second = import_gpu_csv(path, source_id=source_id,
                                session=self.session_factory())

        self.assertEqual(first["inserted"], 2)
        self.assertEqual(first["skipped_existing"], 0)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["skipped_existing"], 2)
        self.assertEqual(self._count(Hardware), 2)
        self.assertEqual(self._count(GPUSpecification), 2)

    def test_cpu_gpu_identity_separation(self):
        self._add_cpu(name="Radeon X300", manufacturer="AMD")
        source_id = self._source_id()

        with self.session_factory() as session:
            inserted = import_gpu(
                {**VALID_RECORD, "name": "Radeon X300",
                 "manufacturer": "AMD", "architecture": "R300"},
                source_id=source_id,
                session=session,
            )
            session.commit()

        self.assertTrue(inserted)

        with self.session_factory() as session:
            hardware = session.scalars(
                select(Hardware).where(Hardware.name == "Radeon X300")
            ).all()
            self.assertEqual(len(hardware), 2)
            by_type = {item.type: item for item in hardware}
            self.assertIsNotNone(by_type["CPU"].cpu_specification)
            self.assertIsNone(by_type["CPU"].gpu_specification)
            self.assertIsNotNone(by_type["GPU"].gpu_specification)
            self.assertIsNone(by_type["GPU"].cpu_specification)

    def test_invalid_gpu_exclusion(self):
        path = self._track(_write_csv([
            _raw_row(),
            _raw_row({"Brand": "Matrox", "Name": "Mystique"}),
            _raw_row({"Name": "Broken Memory", "Memory__Memory Size": "0 GB"}),
        ]))

        result = import_gpu_csv(
            path,
            source_id=self._source_id(),
            session=self.session_factory(),
        )

        self.assertEqual(result["input"], 3)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["invalid"], 2)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(self._count(Hardware), 1)
        self.assertEqual(self._count(GPUSpecification), 1)

    def test_batch_import_counts(self):
        source_id = self._source_id()
        path = self._track(_write_csv([
            _raw_row(),
            _raw_row({"Name": "GeForce RTX 5080", "Memory__Memory Size": "16 GB", "Memory__Bandwidth": "960.0 GB/s"}),
            _raw_row({"Name": "GeForce RTX 5070 Ti", "Memory__Memory Size": "16 GB", "Memory__Bandwidth": "896.0 GB/s", "Board Design__TDP": "300 W", "Board Design__Length": "304 mm 12 inches"}),
            _raw_row({"Brand": "3dfx", "Name": "Voodoo 3"}),
        ]))

        result = import_gpu_csv(path, source_id=source_id,
                                session=self.session_factory())

        self.assertEqual(result["input"], 4)
        self.assertEqual(result["valid"], 3)
        self.assertEqual(result["invalid"], 1)
        self.assertEqual(result["inserted"], 3)
        self.assertEqual(result["skipped_existing"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(self._count(Hardware), 3)

    def test_transaction_rollback_on_import_failure(self):
        source_id = self._source_id()
        path = self._track(_write_csv([
            _raw_row(),
            _raw_row({"Name": "GeForce RTX 5080", "Memory__Memory Size": "16 GB"}),
        ]))

        def fail_before_flush(session, flush_context, instances):
            raise RuntimeError("forced database failure")

        event.listen(
            self.session_factory.class_, "before_flush", fail_before_flush
        )
        self.addCleanup(
            lambda: event.remove(
                self.session_factory.class_,
                "before_flush",
                fail_before_flush,
            )
        )

        with pytest.raises(RuntimeError):
            import_gpu_csv(
                path,
                source_id=source_id,
                session=self.session_factory(),
            )

        self.assertEqual(self._count(Hardware), 0)
        self.assertEqual(self._count(GPUSpecification), 0)

    def test_no_cpu_data_mutation(self):
        self._add_cpu()
        source_id = self._source_id()
        path = self._track(_write_csv([
            _raw_row(),
            _raw_row({"Name": "Radeon RX 7900 XTX", "Brand": "AMD", "Memory__Memory Size": "24 GB", "Memory__Memory Type": "GDDR6", "Memory__Bandwidth": "960.0 GB/s", "Clock Speeds__Boost Clock": "2498 MHz", "Board Design__TDP": "355 W"}),
        ]))

        import_gpu_csv(path, source_id=source_id,
                       session=self.session_factory())

        with self.session_factory() as session:
            cpus = session.scalars(
                select(Hardware).where(Hardware.type == "CPU")
            ).all()
            self.assertEqual(len(cpus), 1)
            self.assertEqual(cpus[0].cpu_specification.cores, 6)
            self.assertIsNone(cpus[0].gpu_specification)

        self.assertEqual(self._count(CPUSpecification), 1)
        self.assertEqual(self._count(Hardware), 3)

    def test_year_only_release_date_is_not_fabricated(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            import_gpu(
                {**VALID_RECORD, "release_date": "2022"},
                source_id=source_id,
                session=session,
            )
            session.commit()

        with self.session_factory() as session:
            hardware = session.scalar(select(Hardware))
            self.assertIsNone(hardware.release_date)

    def test_import_gpu_requires_name_and_manufacturer(self):
        source_id = self._source_id()

        with self.session_factory() as session:
            with pytest.raises(ValueError):
                import_gpu(
                    {**VALID_RECORD, "name": "", "manufacturer": ""},
                    source_id=source_id,
                    session=session,
                )


if __name__ == "__main__":
    unittest.main()