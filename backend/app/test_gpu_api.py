from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    GPUSpecification,
    Hardware,
)
from backend.app.services import benchmark_service
from backend.app import main


class TestGpuApi:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.original_main_session_local = main.SessionLocal
        self.original_benchmark_session_local = benchmark_service.SessionLocal
        main.SessionLocal = self.session_factory
        benchmark_service.SessionLocal = self.session_factory

        self.client = TestClient(main.app)

        self._seed()

    def teardown_method(self):
        main.SessionLocal = self.original_main_session_local
        benchmark_service.SessionLocal = self.original_benchmark_session_local
        self.engine.dispose()

    def _add_cpu(self):
        hardware = Hardware(
            name="AMD Ryzen 5 5600",
            manufacturer="AMD",
            type="CPU",
            architecture="Zen 3",
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
        return hardware

    def _add_gpu(self, name="GeForce RTX 5090", null_specs=False):
        hardware = Hardware(
            name=name,
            manufacturer="NVIDIA",
            type="GPU",
            release_date=None if null_specs else date(2025, 1, 30),
            architecture="Blackwell 2.0",
        )
        if null_specs:
            hardware.gpu_specification = GPUSpecification()
        else:
            hardware.gpu_specification = GPUSpecification(
                memory_gb=32.0,
                memory_type="GDDR7",
                core_clock_mhz=None,
                boost_clock_mhz=2407.0,
                vram_bandwidth_gbps=1790.0,
                tdp_w=575.0,
                interface="PCIe 5.0 x16",
                length_mm=304.0,
            )
        return hardware

    def _seed(self):
        with self.session_factory() as session:
            cpu = self._add_cpu()
            gpu_full = self._add_gpu()
            gpu_null = self._add_gpu(
                name="Arc A310",
                null_specs=True,
            )
            session.add_all([cpu, gpu_full, gpu_null])
            session.commit()
            self.cpu_id = cpu.id
            self.gpu_full_id = gpu_full.id
            self.gpu_null_id = gpu_null.id

            session.add(
                BenchmarkResult(
                    hardware_id=cpu.id,
                    benchmark_name="Geekbench 7",
                    score=2100,
                    unit="points",
                    test_type="single-core",
                    recorded_at=None,
                )
            )
            session.commit()

    def test_catalog_returns_all_hardware(self):
        response = self.client.get("/hardware")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 3
        types = {item["type"] for item in items}
        assert types == {"CPU", "GPU"}
        for item in items:
            assert set(item.keys()) == {
                "id", "name", "manufacturer", "type",
            }

    def test_catalog_gpu_filter(self):
        response = self.client.get("/hardware?type=GPU")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert all(item["type"] == "GPU" for item in items)

    def test_catalog_cpu_filter(self):
        response = self.client.get("/hardware?type=CPU")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["type"] == "CPU"
        assert items[0]["name"] == "AMD Ryzen 5 5600"

    def test_catalog_unknown_type_returns_empty(self):
        response = self.client.get("/hardware?type=SSD")

        assert response.status_code == 200
        assert response.json() == []

    def test_cpu_detail_regression(self):
        response = self.client.get(f"/hardware/{self.cpu_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == self.cpu_id
        assert payload["type"] == "CPU"
        assert payload["name"] == "AMD Ryzen 5 5600"
        assert payload["architecture"] == "Zen 3"
        assert payload["specifications"]["cores"] == 6
        assert payload["specifications"]["threads"] == 12
        assert payload["specifications"]["base_clock_ghz"] == 3.5
        assert payload["specifications"]["boost_clock_ghz"] == 4.4
        assert payload["specifications"]["tdp_w"] == 65
        assert payload["specifications"]["process_node_nm"] == 7
        assert payload["specifications"]["socket"] == "AM4"

    def test_gpu_detail_success(self):
        response = self.client.get(f"/hardware/{self.gpu_full_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == self.gpu_full_id
        assert payload["type"] == "GPU"
        assert payload["name"] == "GeForce RTX 5090"
        assert payload["manufacturer"] == "NVIDIA"
        assert payload["release_date"] == "2025-01-30"
        assert payload["architecture"] == "Blackwell 2.0"
        assert payload["specifications"] == {
            "memory_gb": 32.0,
            "memory_type": "GDDR7",
            "core_clock_mhz": None,
            "boost_clock_mhz": 2407.0,
            "vram_bandwidth_gbps": 1790.0,
            "tdp_w": 575.0,
            "interface": "PCIe 5.0 x16",
            "length_mm": 304.0,
        }

    def test_gpu_detail_nullable_specification_fields(self):
        response = self.client.get(f"/hardware/{self.gpu_null_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "GPU"
        assert payload["name"] == "Arc A310"
        assert payload["specifications"] == {
            "memory_gb": None,
            "memory_type": None,
            "core_clock_mhz": None,
            "boost_clock_mhz": None,
            "vram_bandwidth_gbps": None,
            "tdp_w": None,
            "interface": None,
            "length_mm": None,
        }

    def test_hardware_detail_not_found(self):
        response = self.client.get("/hardware/999999")

        assert response.json() == {"error": "Hardware not found"}

    def test_hardware_detail_malformed_id(self):
        response = self.client.get("/hardware/not-an-int")

        assert response.status_code == 422

    def test_gpu_with_no_benchmarks_returns_empty_contract(self):
        response = self.client.get(
            f"/hardware/{self.gpu_full_id}/benchmarks"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_cpu_benchmark_behavior_unchanged(self):
        response = self.client.get(
            f"/hardware/{self.cpu_id}/benchmarks"
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["benchmark_name"] == "Geekbench 7"
        assert payload[0]["hardware_id"] == self.cpu_id
        assert payload[0]["score"] == 2100
        assert payload[0]["test_type"] == "single-core"
        assert payload[0]["recorded_at"] is None
        assert payload[0]["source"] is None