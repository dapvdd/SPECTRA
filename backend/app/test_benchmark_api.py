from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import BenchmarkResult, Hardware, Source
from backend.app.services import benchmark_service


class TestBenchmarkAPI:
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

    def teardown_method(self):
        benchmark_service.SessionLocal = self.original_session_local
        self.engine.dispose()

    def _add_hardware(self, name: str = "Test CPU") -> Hardware:
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer="Test",
                type="CPU",
            )
            session.add(hardware)
            session.commit()
            session.refresh(hardware)
            return hardware

    def test_returns_multiple_benchmark_results_with_source_metadata(self):
        hardware = self._add_hardware()
        recorded_at = datetime(2026, 9, 16, 12, 30)

        with self.session_factory() as session:
            source = Source(
                name="Example benchmark dataset",
                url="https://example.com/benchmarks",
            )
            session.add(source)
            session.flush()
            session.add_all(
                [
                    BenchmarkResult(
                        hardware_id=hardware.id,
                        benchmark_name="Example Single Core",
                        score=1234.5,
                        unit="points",
                        test_type="single-core",
                        source_id=source.id,
                        recorded_at=recorded_at,
                    ),
                    BenchmarkResult(
                        hardware_id=hardware.id,
                        benchmark_name="Example Multi Core",
                        score=4567,
                        unit="points",
                        test_type="multi-core",
                        source_id=None,
                        recorded_at=None,
                    ),
                ]
            )
            session.commit()

        response = self.client.get(
            f"/hardware/{hardware.id}/benchmarks"
        )

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 1,
                "hardware_id": hardware.id,
                "benchmark_name": "Example Single Core",
                "score": 1234.5,
                "unit": "points",
                "test_type": "single-core",
                "source": {
                    "id": 1,
                    "name": "Example benchmark dataset",
                    "url": "https://example.com/benchmarks",
                },
                "recorded_at": "2026-09-16T12:30:00",
            },
            {
                "id": 2,
                "hardware_id": hardware.id,
                "benchmark_name": "Example Multi Core",
                "score": 4567.0,
                "unit": "points",
                "test_type": "multi-core",
                "source": None,
                "recorded_at": None,
            },
        ]

    def test_returns_empty_list_for_hardware_without_benchmarks(self):
        hardware = self._add_hardware()

        response = self.client.get(
            f"/hardware/{hardware.id}/benchmarks"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_not_found_for_nonexistent_hardware(self):
        response = self.client.get("/hardware/999/benchmarks")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Hardware not found: 999"
        }
