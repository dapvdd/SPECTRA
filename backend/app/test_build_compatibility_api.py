"""Task 3 API tests: POST /build/compatibility/check.

Contract:
- Body: optional IDs for the six build slots (cpu, gpu, ram, storage,
  motherboard, psu). Partial builds are valid input.
- Partial builds are never declared COMPATIBLE: missing components yield
  UNKNOWN (or NOT_APPLICABLE per rule) with an explanation.
- Unknown hardware IDs -> 404 with the offending slot named.
- Wrong category (e.g. a GPU id in the ram slot) -> 422.
- No database writes during evaluation (row counts unchanged).
- Response carries aggregate state, rules_version, per-rule results with
  explanation, spec_fields, missing_information.
- Deterministic: identical request -> identical serialized response.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    CPUSpecification,
    FieldProvenance,
    GPUSpecification,
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    Source,
    StorageSpecification,
)
from backend.app import main
from backend.app.services import compatibility_service


class TestCompatibilityCheckApi:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.original_main_session_local = main.SessionLocal
        self.original_service_session_local = compatibility_service.SessionLocal
        main.SessionLocal = self.session_factory
        compatibility_service.SessionLocal = self.session_factory

        self.client = TestClient(main.app)
        self._seed()

    def teardown_method(self):
        main.SessionLocal = self.original_main_session_local
        compatibility_service.SessionLocal = self.original_service_session_local
        self.engine.dispose()

    # ------------------------------------------------------------------
    def _seed(self):
        with self.session_factory() as session:
            source = Source(
                name="M2 Test Fixture Source",
                url="https://example.com/cpu",
            )
            session.add(source)
            session.flush()

            cpu = Hardware(name="Core i5-12600K", manufacturer="Intel", type="CPU")
            cpu.cpu_specification = CPUSpecification(
                cores=6, threads=12, tdp_w=125, socket="LGA1700"
            )
            gpu = Hardware(name="RTX 4070", manufacturer="NVIDIA", type="GPU")
            gpu.gpu_specification = GPUSpecification(
                memory_gb=12, tdp_w=200, interface="PCIe 4.0 x16"
            )
            ram = Hardware(name="Vengeance 32GB", manufacturer="Corsair", type="RAM")
            ram.ram_specification = RAMSpecification(
                ddr_generation="DDR5", capacity_gb=32, speed_mhz=5600, modules=2
            )
            storage = Hardware(name="980 Pro 1TB", manufacturer="Samsung", type="STORAGE")
            storage.storage_specification = StorageSpecification(
                storage_type="NVMe", capacity_gb=1024, interface="PCIe 4.0 x4"
            )
            mobo = Hardware(name="Z690-A", manufacturer="ASUS", type="MOTHERBOARD")
            mobo.motherboard_specification = MotherboardSpecification(
                socket="LGA1700", chipset="Z690", ram_type="DDR5",
                ram_slots=4, max_ram_gb=128, m2_slots=3, sata_ports=4,
                pcie_slots=2,
            )
            psu = Hardware(name="RM750x", manufacturer="Corsair", type="PSU")
            psu.psu_specification = PSUSpecification(
                wattage=750, efficiency_rating="80 Plus Gold", modular=True,
                pcie_8pin_count=4, pcie_12vhpwr=0,
            )
            session.add_all([cpu, gpu, ram, storage, mobo, psu])
            session.flush()
            self.ids = {item.type: item.id for item in (cpu, gpu, ram, storage, mobo, psu)}

            session.add(FieldProvenance(
                hardware_id=cpu.id, source_id=source.id, table_name="cpu_specifications",
                field_name="socket", evidenced_value="LGA1700",
                source_url="https://example.com/cpu", evidence_status="verified",
                batch_no=1,
            ))
            session.commit()

    def _body(self, **overrides):
        """Request body with lowercase slot keys (API contract)."""
        body = {slot_type.lower(): hardware_id for slot_type, hardware_id in self.ids.items()}
        body.update(overrides)
        return body

    # -- happy paths ---------------------------------------------------

    def test_full_compatible_build(self):
        response = self.client.post("/build/compatibility/check", json=self._body())
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "UNKNOWN"  # GPU slot rule stays unknown
        assert payload["rules_version"] == "M2-RULES-v1"
        results = {r["rule_id"]: r for r in payload["rule_results"]}
        assert results["cpu-motherboard-socket"]["state"] == "COMPATIBLE"
        assert results["ram-motherboard-generation"]["state"] == "COMPATIBLE"
        assert results["ram-motherboard-capacity"]["state"] == "COMPATIBLE"
        assert results["ram-motherboard-slots"]["state"] == "COMPATIBLE"
        assert results["storage-motherboard-interface"]["state"] == "COMPATIBLE"
        assert results["psu-build-wattage"]["state"] == "COMPATIBLE"
        # GPU rule: slot count known, generation unknown.
        assert results["gpu-motherboard-slot"]["state"] == "UNKNOWN"

    def test_incompatible_socket_build(self):
        with self.session_factory() as session:
            amd = Hardware(name="Ryzen 7 5800X", manufacturer="AMD", type="CPU")
            amd.cpu_specification = CPUSpecification(cores=8, threads=16, tdp_w=105, socket="AM4")
            session.add(amd)
            session.commit()
            amd_id = amd.id

        response = self.client.post(
            "/build/compatibility/check",
            json=self._body(cpu=amd_id),
        )
        payload = response.json()
        assert payload["state"] == "INCOMPATIBLE"
        results = {r["rule_id"]: r for r in payload["rule_results"]}
        assert results["cpu-motherboard-socket"]["state"] == "INCOMPATIBLE"
        assert "AM4" in results["cpu-motherboard-socket"]["explanation"]
        assert "LGA1700" in results["cpu-motherboard-socket"]["explanation"]

    # -- partial builds --------------------------------------------------

    def test_partial_build_is_not_compatible(self):
        response = self.client.post(
            "/build/compatibility/check", json=self._body(gpu=None, ram=None, storage=None, motherboard=None, psu=None)
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "UNKNOWN"

    def test_empty_build_is_unknown(self):
        response = self.client.post("/build/compatibility/check", json={})
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "UNKNOWN"

    def test_cpu_plus_mobo_partial_evaluates_applicable_rules(self):
        response = self.client.post(
            "/build/compatibility/check",
            json=self._body(gpu=None, ram=None, storage=None, psu=None),
        )
        payload = response.json()
        rule_ids = {r["rule_id"] for r in payload["rule_results"]}
        assert "cpu-motherboard-socket" in rule_ids
        # RAM/GPU rules need those components; they must not silently claim.
        for rule_id in rule_ids:
            assert rule_id in {
                "cpu-motherboard-socket", "psu-build-wattage", "gpu-motherboard-slot",
            } or payload["state"] == "UNKNOWN"

    # -- error handling ---------------------------------------------------

    def test_unknown_component_id_is_404(self):
        response = self.client.post(
            "/build/compatibility/check", json={"cpu": 99999}
        )
        assert response.status_code == 404
        assert "cpu" in response.json()["detail"].lower()

    def test_wrong_category_id_is_422(self):
        response = self.client.post(
            "/build/compatibility/check", json={"ram": self.ids["GPU"]}
        )
        assert response.status_code == 422
        assert "ram" in response.json()["detail"].lower()

    def test_invalid_payload_shape_is_422(self):
        response = self.client.post(
            "/build/compatibility/check", json={"cpu": "not-an-int"}
        )
        assert response.status_code == 422

    # -- safety -----------------------------------------------------------

    def test_no_database_writes(self):
        with self.session_factory() as session:
            before = session.scalar(select(func.count()).select_from(Hardware))
            prov_before = session.scalar(select(func.count()).select_from(FieldProvenance))
        self.client.post("/build/compatibility/check", json=self._body())
        with self.session_factory() as session:
            after = session.scalar(select(func.count()).select_from(Hardware))
            prov_after = session.scalar(select(func.count()).select_from(FieldProvenance))
        assert before == after
        assert prov_before == prov_after

    def test_deterministic_repeated_evaluation(self):
        first = self.client.post("/build/compatibility/check", json=self._body()).json()
        second = self.client.post("/build/compatibility/check", json=self._body()).json()
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_provenance_reference_surfaced(self):
        payload = self.client.post("/build/compatibility/check", json=self._body()).json()
        socket_rule = next(
            r for r in payload["rule_results"] if r["rule_id"] == "cpu-motherboard-socket"
        )
        provenance_tables = {p["table_name"] for p in socket_rule["provenance"]}
        assert "cpu_specifications" in provenance_tables

    def test_existing_hardware_endpoint_unchanged(self):
        response = self.client.get(f"/hardware/{self.ids['CPU']}")
        assert response.status_code == 200
        assert response.json()["name"] == "Core i5-12600K"
