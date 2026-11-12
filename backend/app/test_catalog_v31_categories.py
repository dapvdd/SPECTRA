"""Build Planner M1 Task 4 API tests: catalog + facets for the new categories.

Contracts:
- GET /hardware?type=RAM|STORAGE|MOTHERBOARD|PSU filters the list and the
  X-Total-Count header reflects the filtered set.
- GET /hardware/{id} returns the type-specific ``specifications`` block for
  the new categories (None when no spec row exists — honest unknown).
- GET /hardware/facets counts the new types; an empty catalog for a type
  yields 0 counts, not an error.
- Unknown type values are rejected with 422.
- CPU/GPU behavior is unchanged (regression tests).
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    StorageSpecification,
)
from backend.app import main
from backend.app.services import hardware_catalog_service


class TestCatalogCategoriesApi:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.original_main_session_local = main.SessionLocal
        self.original_service_session_local = hardware_catalog_service.SessionLocal
        main.SessionLocal = self.session_factory
        hardware_catalog_service.SessionLocal = self.session_factory

        self.client = TestClient(main.app)

        self._seed()

    def teardown_method(self):
        main.SessionLocal = self.original_main_session_local
        hardware_catalog_service.SessionLocal = self.original_service_session_local
        self.engine.dispose()

    def _seed(self):
        with self.session_factory() as session:
            ram = Hardware(
                name="Corsair Vengeance 32GB", manufacturer="Corsair",
                type="RAM",
            )
            ram.ram_specification = RAMSpecification(
                ddr_generation="DDR5", capacity_gb=32, speed_mhz=6000,
            )
            storage = Hardware(
                name="Samsung 990 Pro", manufacturer="Samsung",
                type="STORAGE",
            )
            storage.storage_specification = StorageSpecification(
                storage_type="NVMe", capacity_gb=1000, read_mb_s=7450.0,
            )
            mobo = Hardware(
                name="ASUS ROG Strix Z790", manufacturer="ASUS",
                type="MOTHERBOARD",
            )
            mobo.motherboard_specification = MotherboardSpecification(
                socket="LGA1700", chipset="Z790", ram_type="DDR5", ram_slots=4,
            )
            psu = Hardware(
                name="Corsair RM850x", manufacturer="Corsair", type="PSU",
            )
            psu.psu_specification = PSUSpecification(
                wattage=850, efficiency_rating="80 Plus Gold",
            )
            cpu = Hardware(name="Test CPU", manufacturer="TestCo", type="CPU")
            cpu.cpu_specification = None
            gpu = Hardware(name="Test GPU", manufacturer="TestCo", type="GPU")
            gpu.gpu_specification = None
            session.add_all([ram, storage, mobo, psu, cpu, gpu])
            session.commit()

    def test_list_filters_ram_with_total_count(self):
        response = self.client.get("/hardware", params={"type": "RAM"})

        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "1"
        items = response.json()
        assert len(items) == 1
        assert items[0]["name"] == "Corsair Vengeance 32GB"

    def test_list_filters_storage_motherboard_psu(self):
        for hardware_type, name in (
            ("STORAGE", "Samsung 990 Pro"),
            ("MOTHERBOARD", "ASUS ROG Strix Z790"),
            ("PSU", "Corsair RM850x"),
        ):
            response = self.client.get(
                "/hardware", params={"type": hardware_type}
            )

            assert response.status_code == 200, hardware_type
            assert response.headers["X-Total-Count"] == "1", hardware_type
            assert response.json()[0]["name"] == name

    def test_detail_ram_spec_block(self):
        response = self.client.get("/hardware/1")

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "RAM"
        specs = body["specifications"]
        assert specs["ddr_generation"] == "DDR5"
        assert specs["capacity_gb"] == 32
        assert specs["speed_mhz"] == 6000

    def test_detail_psu_spec_block(self):
        response = self.client.get("/hardware/4")

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "PSU"
        specs = body["specifications"]
        assert specs["wattage"] == 850
        assert specs["efficiency_rating"] == "80 Plus Gold"

    def test_detail_without_spec_row_is_all_none_dict(self):
        # Existing contract: CPU/GPU detail returns an all-None dict when no
        # spec row exists (honest unknown, never fabricated). The new
        # categories follow the same shape.
        response = self.client.get("/hardware/5")

        assert response.status_code == 200
        specs = response.json()["specifications"]
        assert isinstance(specs, dict)
        assert all(value is None for value in specs.values())

    def test_facets_include_new_types(self):
        response = self.client.get("/hardware/facets")

        assert response.status_code == 200
        types = {
            item["value"]: item["count"]
            for item in response.json()["types"]
        }
        assert types["RAM"] == 1
        assert types["STORAGE"] == 1
        assert types["MOTHERBOARD"] == 1
        assert types["PSU"] == 1

    def test_facets_filter_to_type_returns_counts(self):
        response = self.client.get(
            "/hardware/facets", params={"type": "RAM"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["manufacturers"] == [
            {"value": "Corsair", "count": 1}
        ]

    def test_manufacturer_facet_excludes_its_own_filter(self):
        # M2.5 Task 2: with a manufacturer filter active, the manufacturer
        # facet must still list every vendor visible under the OTHER filters
        # (type/q/segment) — otherwise the option list collapses to the
        # active vendor and the user can never switch back.
        with self.session_factory() as session:
            seasonic = Hardware(
                name="Seasonic Focus GX-750", manufacturer="Seasonic",
                type="PSU",
            )
            seasonic.psu_specification = PSUSpecification(
                wattage=750, efficiency_rating="80 Plus Gold",
            )
            session.add(seasonic)
            session.commit()

        response = self.client.get(
            "/hardware/facets",
            params={"type": "PSU", "manufacturer": "Corsair"},
        )

        assert response.status_code == 200
        body = response.json()
        # The types facet keeps the type filter OUT but the manufacturer
        # filter IN: both Corsair rows (RAM + PSU) count.
        assert body["types"] == [
            {"value": "PSU", "count": 1},
            {"value": "RAM", "count": 1},
        ]
        # ...but the manufacturer facet keeps every PSU vendor with its
        # count under the remaining (non-manufacturer) filters.
        assert body["manufacturers"] == [
            {"value": "Corsair", "count": 1},
            {"value": "Seasonic", "count": 1},
        ]

    def test_type_facet_excludes_its_own_filter(self):
        # Same rule for the types facet: while a type is active, the type
        # buttons keep their full counts (the type filter does not apply to
        # its own facet), so switching categories never loses counts.
        response = self.client.get(
            "/hardware/facets", params={"type": "RAM"}
        )

        assert response.status_code == 200
        types = {
            item["value"]: item["count"]
            for item in response.json()["types"]
        }
        assert types == {
            "CPU": 1, "GPU": 1, "RAM": 1,
            "STORAGE": 1, "MOTHERBOARD": 1, "PSU": 1,
        }

    def test_facets_empty_result_is_zero_not_error(self):
        response = self.client.get(
            "/hardware/facets", params={"type": "MOTHERBOARD", "q": "zzz"}
        )

        assert response.status_code == 200
        assert response.json()["types"] == []

    def test_unknown_type_rejected_422(self):
        response = self.client.get("/hardware", params={"type": "RAMXX"})

        assert response.status_code == 422

    def test_cpu_list_regression_unchanged(self):
        response = self.client.get("/hardware", params={"type": "CPU"})

        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "1"
        assert response.json()[0]["name"] == "Test CPU"

    def test_gpu_detail_regression_unchanged(self):
        # GPU id 6 has no spec row; the existing all-None GPU dict shape
        # (GPU-specific keys) is unchanged.
        response = self.client.get("/hardware/6")

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "GPU"
        specs = body["specifications"]
        assert "memory_gb" in specs
        assert "boost_clock_mhz" in specs
        assert "ddr_generation" not in specs
