"""API-level tests for the optional benchmark query filters (Batch 011).

Covers: no-filter backward compatibility, each filter independently, combined
(AND) filters, invalid query values, empty results, unknown source ids, and
duplicate-free responses.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import BenchmarkResult, Hardware, Source
from backend.app.services import benchmark_service


class TestBenchmarkAPIFilters:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.original_session_local = benchmark_service.SessionLocal
        benchmark_service.SessionLocal = self.session_factory
        self.client = TestClient(main.app)

        with self.session_factory() as session:
            self.source_a = Source(
                name="Suite A", url="https://example.com/a"
            )
            self.source_b = Source(
                name="Suite B", url="https://example.com/b"
            )
            session.add_all([self.source_a, self.source_b])
            session.flush()
            source_a_id = self.source_a.id
            source_b_id = self.source_b.id

            self.hardware = Hardware(
                name="Filter Test CPU", manufacturer="Test", type="CPU"
            )
            session.add(self.hardware)
            session.flush()
            hardware_id = self.hardware.id

            session.add_all([
                BenchmarkResult(
                    hardware_id=hardware_id,
                    benchmark_name="Suite A",
                    score=1000.0,
                    unit="points",
                    test_type="single-core",
                    source_id=source_a_id,
                ),
                BenchmarkResult(
                    hardware_id=hardware_id,
                    benchmark_name="Suite A",
                    score=5000.0,
                    unit="points",
                    test_type="multi-core",
                    source_id=source_a_id,
                ),
                BenchmarkResult(
                    hardware_id=hardware_id,
                    benchmark_name="Suite B",
                    score=2000.0,
                    unit="points",
                    test_type="single-core",
                    source_id=source_b_id,
                ),
                BenchmarkResult(
                    hardware_id=hardware_id,
                    benchmark_name="Unattributed",
                    score=42.0,
                    unit="points",
                    test_type="single-core",
                    source_id=None,
                ),
            ])
            session.commit()
            self.hardware_id = hardware_id
            self.source_a_id = source_a_id
            self.source_b_id = source_b_id

    def teardown_method(self):
        benchmark_service.SessionLocal = self.original_session_local
        self.engine.dispose()

    def _get(self, query=""):
        return self.client.get(
            f"/hardware/{self.hardware_id}/benchmarks{query}"
        )

    # ---- backward compatibility ----

    def test_no_filters_returns_all_ordered_by_id(self):
        response = self._get()
        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [1, 2, 3, 4]
        assert [row["benchmark_name"] for row in body] == [
            "Suite A", "Suite A", "Suite B", "Unattributed",
        ]

    # ---- individual filters ----

    def test_filter_by_source_id(self):
        response = self._get(f"?source_id={self.source_a_id}")
        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [1, 2]
        assert all(
            row["source"]["id"] == self.source_a_id for row in body
        )

    def test_filter_by_benchmark_name(self):
        response = self._get("?benchmark_name=Suite B")
        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [3]

    def test_filter_by_test_type(self):
        response = self._get("?test_type=multi-core")
        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [2]

    def test_filter_by_benchmark_name_exact_match_only(self):
        # A partial/substring name must not match.
        response = self._get("?benchmark_name=Suite")
        assert response.status_code == 200
        assert response.json() == []

    # ---- combined filters (AND semantics) ----

    def test_combined_filters_use_and_semantics(self):
        response = self._get(
            f"?source_id={self.source_a_id}"
            "&benchmark_name=Suite A&test_type=single-core"
        )
        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [1]

    def test_combined_filters_with_contradiction_return_empty(self):
        response = self._get(
            f"?source_id={self.source_a_id}&test_type=multi-core"
            "&benchmark_name=Suite B"
        )
        assert response.status_code == 200
        assert response.json() == []

    # ---- empty / unknown results ----

    def test_unknown_source_id_returns_empty_list(self):
        # Consistent with the existing /hardware?type= filter convention:
        # an unknown filter value yields an empty result, not a 404.
        response = self._get("?source_id=999999")
        assert response.status_code == 200
        assert response.json() == []

    def test_unknown_benchmark_name_returns_empty_list(self):
        response = self._get("?benchmark_name=Does Not Exist")
        assert response.status_code == 200
        assert response.json() == []

    def test_unattributed_source_filter_excludes_null_source_rows(self):
        # source_id filter must not match rows whose source_id is NULL.
        response = self._get(f"?source_id={self.source_b_id}")
        body = response.json()
        assert [row["id"] for row in body] == [3]

    # ---- invalid input ----

    def test_non_integer_source_id_is_rejected(self):
        response = self._get("?source_id=abc")
        assert response.status_code == 422

    def test_hardware_not_found_with_filters(self):
        response = self.client.get(
            "/hardware/999999/benchmarks?test_type=single-core"
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Hardware not found: 999999"}

    # ---- integrity ----

    def test_filters_do_not_duplicate_rows(self):
        response = self._get(f"?source_id={self.source_a_id}")
        ids = [row["id"] for row in response.json()]
        assert len(ids) == len(set(ids))

    def test_filter_result_shape_is_unchanged(self):
        response = self._get(f"?source_id={self.source_a_id}")
        row = response.json()[0]
        assert set(row) == {
            "id", "hardware_id", "benchmark_name", "score", "unit",
            "test_type", "source", "recorded_at",
        }