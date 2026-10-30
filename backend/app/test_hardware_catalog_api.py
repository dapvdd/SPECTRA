"""Phase 1.3 API tests: server-side hardware catalog search, pagination, and
facets.

Verifies the additive contract on GET /hardware:
- Default behavior (no params) is byte-identical to the pre-1.3 response.
- q filters by case-insensitive name substring.
- type/manufacturer/segment filter exactly.
- limit/offset paginate; X-Total-Count reflects the full filtered set.
- GET /hardware/facets returns accurate counts under active filters.
- GET /hardware/{hardware_id} still resolves (facets route not shadowing).
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Hardware
from backend.app import main
from backend.app.services import hardware_catalog_service


class TestHardwareCatalogApi:
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

    @staticmethod
    def _hardware(name, manufacturer, hardware_type, segment=None,
                  release_date=None, architecture=None):
        return Hardware(
            name=name,
            manufacturer=manufacturer,
            type=hardware_type,
            segment=segment,
            release_date=release_date,
            architecture=architecture,
        )

    def _seed(self):
        with self.session_factory() as session:
            session.add_all([
                self._hardware(
                    "AMD Ryzen 5 5600", "AMD", "CPU", segment="desktop",
                    release_date=date(2022, 4, 1), architecture="Zen 3",
                ),
                self._hardware(
                    "AMD Ryzen 7 5800X", "AMD", "CPU", segment="desktop",
                    release_date=date(2020, 11, 1), architecture="Zen 3",
                ),
                self._hardware(
                    "Intel Core i5-12400", "Intel", "CPU", segment="desktop",
                    release_date=date(2022, 1, 1), architecture="Alder Lake",
                ),
                self._hardware(
                    "Intel Xeon Platinum 8380", "Intel", "CPU",
                    segment="server", architecture="Ice Lake",
                ),
                self._hardware(
                    "NVIDIA RTX 4090", "NVIDIA", "GPU", segment="desktop",
                    release_date=date(2022, 10, 1), architecture="Ada Lovelace",
                ),
                self._hardware(
                    "AMD Radeon RX 7900 XTX", "AMD", "GPU", segment="desktop",
                    architecture="RDNA 3",
                ),
                self._hardware(
                    "Apple M1", "Apple", "CPU", segment=None,
                ),
            ])
            session.commit()

    def _all_names(self, response):
        return [item["name"] for item in response.json()]


class TestDefaultBehavior(TestHardwareCatalogApi):
    def test_default_returns_full_catalog_unchanged(self):
        response = self.client.get("/hardware")

        assert response.status_code == 200
        assert len(response.json()) == 7
        assert response.headers["X-Total-Count"] == "7"

    def test_default_order_matches_id_order(self):
        response = self.client.get("/hardware")
        names = self._all_names(response)
        assert names == [
            "AMD Ryzen 5 5600",
            "AMD Ryzen 7 5800X",
            "Intel Core i5-12400",
            "Intel Xeon Platinum 8380",
            "NVIDIA RTX 4090",
            "AMD Radeon RX 7900 XTX",
            "Apple M1",
        ]

    def test_type_filter_preserved(self):
        response = self.client.get("/hardware", params={"type": "GPU"})

        assert response.status_code == 200
        assert self._all_names(response) == [
            "NVIDIA RTX 4090",
            "AMD Radeon RX 7900 XTX",
        ]
        assert response.headers["X-Total-Count"] == "2"


class TestSearch(TestHardwareCatalogApi):
    def test_search_is_case_insensitive_substring(self):
        response = self.client.get("/hardware", params={"q": "ryzen"})

        assert response.status_code == 200
        assert self._all_names(response) == [
            "AMD Ryzen 5 5600",
            "AMD Ryzen 7 5800X",
        ]
        assert response.headers["X-Total-Count"] == "2"

    def test_search_matches_middle_of_name(self):
        response = self.client.get("/hardware", params={"q": "4090"})

        assert response.status_code == 200
        assert self._all_names(response) == ["NVIDIA RTX 4090"]

    def test_search_no_matches_returns_empty_list(self):
        response = self.client.get("/hardware", params={"q": "zzzz"})

        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["X-Total-Count"] == "0"

    def test_search_combined_with_type(self):
        response = self.client.get(
            "/hardware", params={"q": "amd", "type": "GPU"}
        )

        assert self._all_names(response) == ["AMD Radeon RX 7900 XTX"]

    def test_search_shorter_ids(self):
        resp = self.client.get("/hardware", params={"q": "intel core"})
        assert self._all_names(resp) == ["Intel Core i5-12400"]


class TestFilters(TestHardwareCatalogApi):
    def test_manufacturer_filter(self):
        response = self.client.get("/hardware", params={"manufacturer": "AMD"})

        assert response.status_code == 200
        assert self._all_names(response) == [
            "AMD Ryzen 5 5600",
            "AMD Ryzen 7 5800X",
            "AMD Radeon RX 7900 XTX",
        ]

    def test_manufacturer_exact_match(self):
        # "amd" must not fuzzy-match "AMD" descendants; exact match required.
        response = self.client.get("/hardware", params={"manufacturer": "amd"})

        assert response.status_code == 200
        assert response.json() == []

    def test_segment_filter(self):
        response = self.client.get("/hardware", params={"segment": "server"})

        assert response.status_code == 200
        assert self._all_names(response) == ["Intel Xeon Platinum 8380"]

    def test_segment_desktop(self):
        response = self.client.get("/hardware", params={"segment": "desktop"})

        assert response.status_code == 200
        assert len(response.json()) == 5

    def test_combined_filters(self):
        response = self.client.get(
            "/hardware",
            params={"manufacturer": "AMD", "segment": "desktop"},
        )

        assert self._all_names(response) == [
            "AMD Ryzen 5 5600",
            "AMD Ryzen 7 5800X",
            "AMD Radeon RX 7900 XTX",
        ]


class TestPagination(TestHardwareCatalogApi):
    def test_limit_returns_only_page_size(self):
        response = self.client.get("/hardware", params={"limit": 2})

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.headers["X-Total-Count"] == "7"

    def test_offset_skips_rows(self):
        response = self.client.get("/hardware", params={"offset": 2, "limit": 2})

        assert self._all_names(response) == [
            "Intel Core i5-12400",
            "Intel Xeon Platinum 8380",
        ]
        assert response.headers["X-Total-Count"] == "7"

    def test_offset_beyond_end_returns_empty(self):
        response = self.client.get("/hardware", params={"offset": 100})

        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["X-Total-Count"] == "7"

    def test_pagination_respects_filters(self):
        # 5 CPUs total: Ryzen 5, Ryzen 7, Core i5, Xeon, Apple M1.
        response = self.client.get(
            "/hardware", params={"type": "CPU", "limit": 2, "offset": 1}
        )

        names = self._all_names(response)
        assert names == [
            "AMD Ryzen 7 5800X",
            "Intel Core i5-12400",
        ]
        assert response.headers["X-Total-Count"] == "5"

    def test_invalid_limit_rejected(self):
        response = self.client.get("/hardware", params={"limit": 0})

        assert response.status_code == 422

    def test_negative_offset_rejected(self):
        response = self.client.get("/hardware", params={"offset": -1})

        assert response.status_code == 422


class TestFacets(TestHardwareCatalogApi):
    def test_facets_global_counts(self):
        response = self.client.get("/hardware/facets")

        assert response.status_code == 200
        payload = response.json()

        types = {f["value"]: f["count"] for f in payload["types"]}
        assert types == {"CPU": 5, "GPU": 2}

        manufacturers = {
            f["value"]: f["count"] for f in payload["manufacturers"]
        }
        assert manufacturers == {
            "AMD": 3,
            "Intel": 2,
            "NVIDIA": 1,
            "Apple": 1,
        }

        segments = {f["value"]: f["count"] for f in payload["segments"]}
        assert segments == {"desktop": 5, "server": 1}

    def test_facets_respect_active_filters(self):
        response = self.client.get(
            "/hardware/facets", params={"manufacturer": "AMD"}
        )

        payload = response.json()
        types = {f["value"]: f["count"] for f in payload["types"]}
        assert types == {"CPU": 2, "GPU": 1}

        # Under manufacturer=AMD the desktop segment has all three AMD rows.
        segments = {f["value"]: f["count"] for f in payload["segments"]}
        assert segments == {"desktop": 3}

    def test_facets_respect_type_filter(self):
        response = self.client.get("/hardware/facets", params={"type": "GPU"})

        payload = response.json()
        manufacturers = {
            f["value"]: f["count"] for f in payload["manufacturers"]
        }
        assert manufacturers == {"NVIDIA": 1, "AMD": 1}

    def test_facets_combine_search_and_filters(self):
        response = self.client.get(
            "/hardware/facets", params={"q": "ryzen", "segment": "desktop"}
        )

        payload = response.json()
        manufacturers = {
            f["value"]: f["count"] for f in payload["manufacturers"]
        }
        assert manufacturers == {"AMD": 2}

    def test_facets_null_segment_excluded(self):
        # Apple M1 has segment NULL -> must not appear as a bucket or inflate
        # the desktop count.
        response = self.client.get("/hardware/facets")

        payload = response.json()
        segments = {f["value"]: f["count"] for f in payload["segments"]}
        assert "null" not in segments
        assert segments["desktop"] == 5


class TestDetailRouteNotShadowed(TestHardwareCatalogApi):
    def test_facets_route_does_not_shadow_detail(self):
        # First hardware id is 1 (seed row 0).
        response = self.client.get("/hardware/1")

        assert response.status_code == 200
        assert response.json()["name"] == "AMD Ryzen 5 5600"

    def test_detail_missing_returns_404(self):
        response = self.client.get("/hardware/999999")

        assert response.status_code == 404
