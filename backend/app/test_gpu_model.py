import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    CPUSpecification,
    GPUSpecification,
    Hardware,
)


class TestGPUSpecificationModel:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def teardown_method(self):
        self.engine.dispose()

    def _add_hardware(
        self,
        name: str = "GeForce RTX 5070 Ti",
        manufacturer: str = "NVIDIA",
        hardware_type: str = "GPU",
    ) -> Hardware:
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer=manufacturer,
                type=hardware_type,
            )
            session.add(hardware)
            session.commit()
            session.refresh(hardware)
            return hardware

    def test_gpu_specification_can_be_created_with_all_fields(self):
        hardware = self._add_hardware()

        with self.session_factory() as session:
            specification = GPUSpecification(
                hardware_id=hardware.id,
                memory_gb=16,
                memory_type="GDDR7",
                core_clock_mhz=2235,
                boost_clock_mhz=2520,
                vram_bandwidth_gbps=896,
                tdp_w=300,
                interface="PCIe 5.0 x16",
                length_mm=304,
            )
            session.add(specification)
            session.commit()
            session.refresh(specification)

            assert specification.id is not None
            assert specification.hardware_id == hardware.id
            assert specification.memory_gb == 16
            assert specification.memory_type == "GDDR7"
            assert specification.core_clock_mhz == 2235
            assert specification.boost_clock_mhz == 2520
            assert specification.vram_bandwidth_gbps == 896
            assert specification.tdp_w == 300
            assert specification.interface == "PCIe 5.0 x16"
            assert specification.length_mm == 304

    def test_hardware_id_foreign_key_rejects_unknown_hardware(self):
        with self.session_factory() as session:
            specification = GPUSpecification(hardware_id=999999)
            session.add(specification)

            with pytest.raises(IntegrityError):
                session.commit()

    def test_hardware_id_foreign_key_references_valid_hardware(self):
        hardware = self._add_hardware()

        with self.session_factory() as session:
            specification = GPUSpecification(hardware_id=hardware.id)
            session.add(specification)
            session.commit()
            session.refresh(specification)

            assert specification.hardware_id == hardware.id

    def test_hardware_id_must_be_unique(self):
        hardware = self._add_hardware()

        with self.session_factory() as session:
            session.add(GPUSpecification(hardware_id=hardware.id))
            session.add(GPUSpecification(hardware_id=hardware.id))

            with pytest.raises(IntegrityError):
                session.commit()

    def test_distinct_hardware_ids_can_each_have_a_specification(self):
        first = self._add_hardware(name="GeForce RTX 4080")
        second = self._add_hardware(name="Radeon RX 7900 XTX", manufacturer="AMD")

        with self.session_factory() as session:
            session.add(GPUSpecification(hardware_id=first.id, memory_gb=16))
            session.add(GPUSpecification(hardware_id=second.id, memory_gb=24))
            session.commit()

            assert (
                session.query(GPUSpecification)
                .filter(GPUSpecification.hardware_id.in_([first.id, second.id]))
                .count()
                == 2
            )

    def test_all_gpu_fields_are_nullable(self):
        hardware = self._add_hardware()

        with self.session_factory() as session:
            specification = GPUSpecification(hardware_id=hardware.id)
            session.add(specification)
            session.commit()
            session.refresh(specification)

            assert specification.memory_gb is None
            assert specification.memory_type is None
            assert specification.core_clock_mhz is None
            assert specification.boost_clock_mhz is None
            assert specification.vram_bandwidth_gbps is None
            assert specification.tdp_w is None
            assert specification.interface is None
            assert specification.length_mm is None

    def test_hardware_id_is_nullable_by_convention(self):
        with self.session_factory() as session:
            specification = GPUSpecification()
            session.add(specification)
            session.commit()
            session.refresh(specification)

            assert specification.id is not None
            assert specification.hardware_id is None

    def test_hardware_gpu_relationship_is_bidirectional(self):
        with self.session_factory() as session:
            hardware = Hardware(
                name="GeForce RTX 5070 Ti",
                manufacturer="NVIDIA",
                type="GPU",
            )
            session.add(hardware)
            session.flush()

            specification = GPUSpecification(
                hardware_id=hardware.id,
                memory_gb=16,
                tdp_w=300,
            )
            session.add(specification)
            session.commit()

            assert hardware.gpu_specification is not None
            assert hardware.gpu_specification.memory_gb == 16
            assert specification.hardware is hardware

        with self.session_factory() as session:
            loaded = session.get(Hardware, hardware.id)
            assert loaded.gpu_specification is not None
            assert loaded.gpu_specification.tdp_w == 300
            assert loaded.gpu_specification.hardware.name == "GeForce RTX 5070 Ti"

    def test_gpu_specifications_table_is_created(self):
        tables = set(inspect(self.engine).get_table_names())

        assert "gpu_specifications" in tables
        assert "hardware" in tables
        assert "cpu_specifications" in tables

    def test_gpu_specifications_columns_match_contract(self):
        columns = {
            column["name"]
            for column in inspect(self.engine).get_columns("gpu_specifications")
        }

        assert columns == {
            "id",
            "hardware_id",
            "memory_gb",
            "memory_type",
            "core_clock_mhz",
            "boost_clock_mhz",
            "vram_bandwidth_gbps",
            "tdp_w",
            "interface",
            "length_mm",
        }

    def test_existing_cpu_model_behavior_remains_unchanged(self):
        with self.session_factory() as session:
            hardware = Hardware(
                name="Ryzen 5 5600",
                manufacturer="AMD",
                type="CPU",
            )
            hardware.cpu_specification = CPUSpecification(
                cores=6,
                threads=12,
                base_clock_ghz=3.5,
                boost_clock_ghz=4.4,
                tdp_w=65,
                process_node_nm=7,
                socket="AM4",
            )
            session.add(hardware)
            session.commit()

            assert hardware.gpu_specification is None

        with self.session_factory() as session:
            loaded = session.get(Hardware, hardware.id)

            assert loaded.type == "CPU"
            assert loaded.gpu_specification is None
            assert loaded.cpu_specification.cores == 6
            assert loaded.cpu_specification.threads == 12
            assert loaded.cpu_specification.base_clock_ghz == 3.5
            assert loaded.cpu_specification.boost_clock_ghz == 4.4
            assert loaded.cpu_specification.tdp_w == 65
            assert loaded.cpu_specification.process_node_nm == 7
            assert loaded.cpu_specification.socket == "AM4"

    def test_creating_gpu_specification_does_not_affect_cpu_data(self):
        with self.session_factory() as session:
            cpu = Hardware(name="Core i5-12400F", manufacturer="Intel", type="CPU")
            cpu.cpu_specification = CPUSpecification(
                cores=6,
                threads=12,
                base_clock_ghz=2.5,
                boost_clock_ghz=4.4,
            )
            session.add(cpu)
            session.flush()

            gpu = Hardware(name="Radeon RX 7800 XT", manufacturer="AMD", type="GPU")
            gpu.gpu_specification = GPUSpecification(memory_gb=16)
            session.add(gpu)
            session.commit()

            assert session.query(GPUSpecification).count() == 1
            assert session.query(CPUSpecification).count() == 1
            assert cpu.cpu_specification.cores == 6
            assert gpu.gpu_specification.memory_gb == 16