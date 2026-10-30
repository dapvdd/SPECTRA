"""API tests for POST /comparison/gpu (Phase 1.1 GPU comparison parity).

Verifies the wire contract:
- 200 with a comparison result for two GPUs with specifications.
- Semantics match the deterministic service (unavailable / tie / winner).
- 404 when either hardware id does not exist.
- 422 when either record lacks a GPU specification.
- 422 validation when request body is malformed.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    GPUSpecification,
    Hardware,
)
from backend.app import main


class TestGpuComparisonApi:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.original_main_session_local = main.SessionLocal
        main.SessionLocal = self.session_factory

        self.client = TestClient(main.app)

        self._seed()

    def teardown_method(self):
        main.SessionLocal = self.original_main_session_local
        self.engine.dispose()

    def _add_gpu(self, name, **spec):
        hardware = Hardware(
            name=name,
            manufacturer="Vendor",
            type="GPU",
            release_date=date(2024, 1, 1),
            architecture="Arch",
        )
        hardware.gpu_specification = GPUSpecification(**spec)
        return hardware

    def _seed(self):
        with self.session_factory() as session:
            gpu_a = self._add_gpu(
                "GPU A",
                memory_gb=24.0,
                vram_bandwidth_gbps=960.0,
                core_clock_mhz=1400.0,
                boost_clock_mhz=2700.0,
                tdp_w=200.0,
                length_mm=280.0,
                memory_bus_width_bits=384,
            )
            gpu_b = self._add_gpu(
                "GPU B",
                memory_gb=16.0,
                vram_bandwidth_gbps=640.0,
                core_clock_mhz=1300.0,
                boost_clock_mhz=2600.0,
                tdp_w=300.0,
                length_mm=320.0,
                memory_bus_width_bits=256,
            )
            gpu_nospec = Hardware(
                name="GPU No Spec",
                manufacturer="Vendor",
                type="GPU",
            )
            session.add_all([gpu_a, gpu_b, gpu_nospec])
            session.commit()
            self.gpu_a_id = gpu_a.id
            self.gpu_b_id = gpu_b.id
            self.gpu_nospec_id = gpu_nospec.id

    def _post(self, hardware_id_a, hardware_id_b):
        return self.client.post(
            "/comparison/gpu",
            json={
                "hardware_id_a": hardware_id_a,
                "hardware_id_b": hardware_id_b,
            },
        )

    def test_comparison_returns_winner_semantics(self):
        response = self._post(self.gpu_a_id, self.gpu_b_id)

        assert response.status_code == 200
        payload = response.json()
        assert payload["hardware_a"] == "GPU A"
        assert payload["hardware_b"] == "GPU B"

        winners = {m["name"]: m["winner"] for m in payload["metrics"]}
        # Higher-is-better -> a; lower-is-better (tdp_w, length_mm) -> a.
        assert winners["memory_gb"] == "a"
        assert winners["vram_bandwidth_gbps"] == "a"
        assert winners["core_clock_mhz"] == "a"
        assert winners["boost_clock_mhz"] == "a"
        assert winners["tdp_w"] == "a"
        assert winners["length_mm"] == "a"
        assert winners["memory_bus_width_bits"] == "a"

    def test_comparison_reports_tie_for_equal_metrics(self):
        # Same GPU twice -> every metric ties.
        response = self._post(self.gpu_a_id, self.gpu_a_id)

        assert response.status_code == 200
        payload = response.json()
        assert all(
            metric["winner"] == "tie"
            for metric in payload["metrics"]
        )

    def test_comparison_reports_unavailable_for_missing_value(self):
        # Add a GPU with only its memory declared; every other metric is missing.
        gpu_partial = self._add_gpu(
            "GPU Partial",
            memory_gb=12.0,
            vram_bandwidth_gbps=None,
            core_clock_mhz=None,
            boost_clock_mhz=None,
            tdp_w=None,
            length_mm=None,
            memory_bus_width_bits=None,
        )
        with self.session_factory() as session:
            session.add(gpu_partial)
            session.commit()
            self.gpu_partial_id = gpu_partial.id

        response = self._post(self.gpu_a_id, self.gpu_partial_id)

        assert response.status_code == 200
        payload = response.json()
        for metric in payload["metrics"]:
            if metric["name"] in ("vram_bandwidth_gbps", "core_clock_mhz",
                                  "boost_clock_mhz", "tdp_w", "length_mm",
                                  "memory_bus_width_bits"):
                assert metric["winner"] == "unavailable"
                assert metric["difference"] is None
        # Memory_gb is present on both -> a wins.
        memory = next(m for m in payload["metrics"] if m["name"] == "memory_gb")
        assert memory["winner"] == "a"

    def test_missing_hardware_a_returns_404(self):
        response = self._post(999999, self.gpu_b_id)

        assert response.status_code == 404
        assert response.json() == {"detail": "Hardware not found: 999999"}

    def test_missing_hardware_b_returns_404(self):
        response = self._post(self.gpu_a_id, 999999)

        assert response.status_code == 404
        assert response.json() == {"detail": "Hardware not found: 999999"}

    def test_hardware_without_gpu_spec_returns_422(self):
        response = self._post(self.gpu_a_id, self.gpu_nospec_id)

        assert response.status_code == 422
        assert "GPU specifications" in response.json()["detail"]

    def test_malformed_body_returns_422(self):
        response = self.client.post(
            "/comparison/gpu",
            json={"hardware_id_a": "not-an-int"},
        )

        assert response.status_code == 422
