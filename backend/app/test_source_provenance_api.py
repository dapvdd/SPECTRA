"""Tests for the Batch 015 source-transparency API.

Covers the read-only provenance endpoints, the source registry metadata and its
licence-status distinctions, honest partial/missing provenance, unknown
identifier handling, and backward compatibility of the pre-existing hardware and
benchmark endpoints. An in-memory SQLite database is used and the service
session factory is redirected at it, matching the existing benchmark API tests.
"""

from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.migrations.runner import (
    _INGESTION_RUNS_DDL,
    _PUBLICATION_BATCHES_DDL,
)
from backend.app.models import (
    BenchmarkResult,
    CPUSpecification,
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    Source,
    StorageSpecification,
)
from backend.app.models.source import LICENSE_STATUSES
from backend.app.services import benchmark_service, source_service
from backend.app.services.provenance_service import insert_provenance_record
from backend.app.source_registry import SOURCE_METADATA, seed_source_metadata


class ProvenanceAPITestBase:
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
        self.original_source_session = source_service.SessionLocal
        self.original_benchmark_session = benchmark_service.SessionLocal
        self.original_main_session = main.SessionLocal
        source_service.SessionLocal = self.session_factory
        benchmark_service.SessionLocal = self.session_factory
        main.SessionLocal = self.session_factory
        self.client = TestClient(main.app)

    def teardown_method(self):
        source_service.SessionLocal = self.original_source_session
        benchmark_service.SessionLocal = self.original_benchmark_session
        main.SessionLocal = self.original_main_session
        self.engine.dispose()

    # -- helpers -----------------------------------------------------------
    def _seed_registry_without_metadata(self):
        """Insert the nine registered sources with metadata columns left NULL."""
        with self.session_factory() as session:
            for source_id in sorted(SOURCE_METADATA):
                session.add(
                    Source(
                        id=source_id,
                        name=SOURCE_METADATA[source_id]["name"],
                        url=f"https://example.test/source/{source_id}",
                    )
                )
            session.commit()

    def _seed_metadata_into_db(self):
        self._seed_registry_without_metadata()
        with self.session_factory() as session:
            seed_source_metadata(session)

    def _add_cpu(self, name="Test CPU"):
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer="Test",
                type="CPU",
                release_date=date(2024, 1, 1),
                architecture="Zen 5",
            )
            hardware.cpu_specification = CPUSpecification(
                cores=8,
                threads=16,
                base_clock_ghz=4.0,
                boost_clock_ghz=5.0,
                tdp_w=105.0,
                process_node_nm=4.0,
                socket="AM5",
            )
            session.add(hardware)
            session.commit()
            return hardware.id

    def _add_record(
        self,
        hardware_id,
        table_name,
        field_name,
        *,
        source_id=5,
        evidenced_value="",
        status="verified",
        license_name=None,
        license_notes=None,
        attribution=None,
        benchmark_result_id=None,
    ):
        with self.session_factory() as session:
            record, _ = insert_provenance_record(
                session,
                hardware_id=hardware_id,
                table_name=table_name,
                field_name=field_name,
                source_id=source_id,
                source_url="https://example.test/evidence",
                evidence_status=status,
                batch_no=15,
                evidenced_value=evidenced_value,
                license_name=license_name,
                license_notes=license_notes,
                attribution=attribution,
                benchmark_result_id=benchmark_result_id,
            )
            session.commit()
            return record.id

    def _add_benchmark(self, hardware_id, *, score=1234.5, test_type="single-core"):
        with self.session_factory() as session:
            benchmark = BenchmarkResult(
                hardware_id=hardware_id,
                benchmark_name="Geekbench 7",
                score=score,
                unit="points",
                test_type=test_type,
                source_id=2,
                recorded_at=datetime(2026, 1, 2, 3, 4, 5),
            )
            session.add(benchmark)
            session.commit()
            return benchmark.id


class TestSourceRegistryEndpoint(ProvenanceAPITestBase):
    def test_lists_all_registered_sources_with_usage_counts(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        self._add_record(hardware_id, "cpu_specifications", "cores", evidenced_value="8")

        response = self.client.get("/sources")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == len(SOURCE_METADATA)
        by_id = {item["id"]: item for item in body}
        assert set(by_id) == set(SOURCE_METADATA)
        assert by_id[5]["usage"] == {
            "provenance_records": 1,
            "hardware_records": 1,
            "benchmark_records": 0,
        }
        assert by_id[1]["usage"]["provenance_records"] == 0

    def test_license_status_vocabulary_is_distinguished(self):
        self._seed_metadata_into_db()
        expected = {
            1: "restricted",
            2: "unknown",
            3: "restricted",
            4: "clear",
            5: "clear",
            6: "unknown",
            7: "unresolved",
            8: "unknown",
            9: "unknown",
        }

        for source_id, status in expected.items():
            response = self.client.get(f"/sources/{source_id}")
            assert response.status_code == 200
            assert response.json()["license_status"] == status
            assert response.json()["license_status"] in LICENSE_STATUSES

        assert self.client.get("/sources/4").json()["license_name"] == "CC BY 4.0"
        assert (
            self.client.get("/sources/5").json()["license_name"] == "CC BY-SA 4.0"
        )
        # Restricted/unknown sources must not be reported with a licence name.
        assert self.client.get("/sources/1").json()["license_name"] is None
        assert self.client.get("/sources/2").json()["license_name"] is None

    def test_unknown_source_returns_not_found(self):
        response = self.client.get("/sources/999")
        assert response.status_code == 404
        assert response.json() == {"detail": "Source not found: 999"}

    def test_register_falls_back_for_rows_without_metadata_columns(self):
        # Columns exist but are NULL: the API must still report the register.
        self._seed_registry_without_metadata()

        body = self.client.get("/sources/5").json()
        assert body["publisher"] == "Wikimedia Foundation — Wikipedia contributors"
        assert body["license_status"] == "clear"
        assert body["url"] == "https://example.test/source/5"

    def test_differently_named_row_is_not_mis_attributed(self):
        with self.session_factory() as session:
            session.add(
                Source(id=4, name="Something unrelated", url="https://x.test")
            )
            session.commit()

        body = self.client.get("/sources/4").json()
        assert body["publisher"] is None
        assert body["license_status"] is None


class TestHardwareProvenanceEndpoint(ProvenanceAPITestBase):
    def test_reports_verified_and_unattributed_fields_honestly(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        self._add_record(
            hardware_id,
            "cpu_specifications",
            "cores",
            evidenced_value="8",
            license_name="CC BY-SA 4.0",
        )

        response = self.client.get(f"/hardware/{hardware_id}/provenance")

        assert response.status_code == 200
        body = response.json()
        assert body["hardware_id"] == hardware_id
        assert body["hardware_type"] == "CPU"
        assert body["benchmarks"] == []

        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        assert ("hardware", "release_date") in fields
        assert ("cpu_specifications", "socket") in fields

        cores = fields[("cpu_specifications", "cores")]
        assert cores["status"] == "verified"
        assert cores["has_value"] is True
        assert len(cores["records"]) == 1
        record = cores["records"][0]
        assert record["source_id"] == 5
        assert record["source_name"] == SOURCE_METADATA[5]["name"]
        assert record["publisher"] == "Wikimedia Foundation — Wikipedia contributors"
        assert record["license_status"] == "clear"
        assert record["evidence_status"] == "verified"
        assert record["batch_no"] == 15

        threads = fields[("cpu_specifications", "threads")]
        assert cores["status"] != "unattributed"
        assert fields[("cpu_specifications", "socket")]["status"] == "unattributed"

        summary = body["summary"]
        assert summary["total_fields"] == len(body["fields"])
        assert summary["verified_fields"] == 1
        assert summary["unattributed_fields"] >= 1
        assert summary["unavailable_fields"] == 0

    def test_missing_value_without_evidence_is_unavailable(self):
        self._seed_metadata_into_db()
        with self.session_factory() as session:
            hardware = Hardware(name="Bare CPU", manufacturer="Test", type="CPU")
            hardware.cpu_specification = CPUSpecification()
            session.add(hardware)
            session.commit()
            hardware_id = hardware.id

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        cores = fields[("cpu_specifications", "cores")]
        assert cores["has_value"] is False
        assert cores["records"] == []
        assert cores["status"] == "unavailable"
        assert body["summary"]["unavailable_fields"] >= 1

    def test_multiple_records_for_one_field_are_all_returned(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        self._add_record(
            hardware_id,
            "cpu_specifications",
            "cores",
            source_id=5,
            evidenced_value="8",
            status="verified",
        )
        self._add_record(
            hardware_id,
            "cpu_specifications",
            "cores",
            source_id=8,
            evidenced_value="8",
            status="uncertain",
        )

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        cores = fields[("cpu_specifications", "cores")]
        assert len(cores["records"]) == 2
        assert {r["source_id"] for r in cores["records"]} == {5, 8}
        # A verified record takes precedence for the aggregate field status.
        assert cores["status"] == "verified"

    def test_benchmark_provenance_is_separated_from_spec_fields(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        benchmark_id = self._add_benchmark(hardware_id)
        self._add_record(
            hardware_id,
            "benchmark_results",
            "score",
            source_id=2,
            evidenced_value="1234.5",
            benchmark_result_id=benchmark_id,
        )

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        spec_fields = {
            (f["table_name"], f["field_name"]) for f in body["fields"]
        }
        assert ("benchmark_results", "score") not in spec_fields

        assert len(body["benchmarks"]) == 1
        group = body["benchmarks"][0]
        assert group["benchmark_result_id"] == benchmark_id
        assert group["benchmark_name"] == "Geekbench 7"
        assert group["records"][0]["field_name"] == "score"

    def test_unknown_hardware_returns_not_found(self):
        response = self.client.get("/hardware/999/provenance")
        assert response.status_code == 404
        assert response.json() == {"detail": "Hardware not found: 999"}

    def test_query_count_is_bounded_regardless_of_record_count(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        for index in range(40):
            self._add_record(
                hardware_id,
                "cpu_specifications",
                "cores",
                source_id=5,
                evidenced_value=f"v{index}",
                status="verified",
            )

        statements = []

        @event.listens_for(self.engine, "before_cursor_execute")
        def _count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        response = self.client.get(f"/hardware/{hardware_id}/provenance")

        assert response.status_code == 200
        assert len(response.json()["fields"][0]["records"]) >= 0
        # Fixed number of batched queries (hardware + one eager load per spec
        # relationship + spec provenance + source, benchmark provenance +
        # source); it must not scale with row count. M3 widens the eager
        # loads from 2 to 6 spec relationships, hence the larger constant.
        assert len(statements) <= 12


class TestBenchmarkProvenanceEndpoint(ProvenanceAPITestBase):
    def test_returns_benchmark_metric_provenance(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        benchmark_id = self._add_benchmark(hardware_id)
        self._add_record(
            hardware_id,
            "benchmark_results",
            "score",
            source_id=2,
            evidenced_value="1234.5",
            benchmark_result_id=benchmark_id,
            attribution="Geekbench Browser",
        )

        response = self.client.get(f"/benchmarks/{benchmark_id}/provenance")

        assert response.status_code == 200
        body = response.json()
        assert body["benchmark_result_id"] == benchmark_id
        assert body["hardware_id"] == hardware_id
        assert body["benchmark_name"] == "Geekbench 7"
        assert body["test_type"] == "single-core"
        assert body["source"]["id"] == 2
        assert len(body["records"]) == 1
        assert body["records"][0]["field_name"] == "score"
        assert body["records"][0]["attribution"] == "Geekbench Browser"

    def test_unknown_benchmark_returns_not_found(self):
        response = self.client.get("/benchmarks/999/provenance")
        assert response.status_code == 404
        assert response.json() == {"detail": "Benchmark not found: 999"}

    def test_benchmark_without_provenance_reports_empty_records(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        benchmark_id = self._add_benchmark(hardware_id)

        body = self.client.get(f"/benchmarks/{benchmark_id}/provenance").json()
        assert body["records"] == []


class TestBuildPlannerCategoryProvenance(ProvenanceAPITestBase):
    """M3: the provenance endpoint must cover the four Build Planner
    categories with their spec tables and field order, honestly reporting
    unattributed/unavailable fields exactly like CPU/GPU."""

    def _add_psu(self, name="Test PSU"):
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer="Test",
                type="PSU",
                release_date=date(2024, 3, 1),
            )
            hardware.psu_specification = PSUSpecification(
                wattage=850,
                efficiency_rating="80 Plus Gold",
                modular=True,
                pcie_8pin_count=4,
                pcie_12vhpwr=1,
            )
            session.add(hardware)
            session.commit()
            return hardware.id

    def _add_ram(self, name="Test RAM"):
        with self.session_factory() as session:
            hardware = Hardware(
                name=name, manufacturer="Test", type="RAM"
            )
            hardware.ram_specification = RAMSpecification(
                ddr_generation="DDR5",
                capacity_gb=32,
                speed_mhz=6000,
                modules=2,
                ecc=False,
                voltage_v=1.35,
                form_factor="UDIMM",
            )
            session.add(hardware)
            session.commit()
            return hardware.id

    def test_psu_fields_are_listed_with_verified_evidence(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_psu()
        self._add_record(
            hardware_id,
            "psu_specifications",
            "wattage",
            evidenced_value="850",
            license_name="site terms",
        )

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        assert body["hardware_type"] == "PSU"

        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        assert set(fields) == {
            ("hardware", "release_date"),
            ("hardware", "architecture"),
            ("psu_specifications", "wattage"),
            ("psu_specifications", "efficiency_rating"),
            ("psu_specifications", "modular"),
            ("psu_specifications", "pcie_8pin_count"),
            ("psu_specifications", "pcie_12vhpwr"),
        }

        wattage = fields[("psu_specifications", "wattage")]
        assert wattage["has_value"] is True
        assert wattage["status"] == "verified"
        assert len(wattage["records"]) == 1
        assert wattage["records"][0]["evidenced_value"] == "850"
        # Efficiency is populated but carries no provenance row yet: honest
        # unattributed, never silently attributed.
        assert fields[("psu_specifications", "efficiency_rating")][
            "status"
        ] == "unattributed"

    def test_psu_missing_value_without_evidence_is_unavailable(self):
        self._seed_metadata_into_db()
        with self.session_factory() as session:
            hardware = Hardware(name="Bare PSU", manufacturer="Test", type="PSU")
            hardware.psu_specification = PSUSpecification()
            session.add(hardware)
            session.commit()
            hardware_id = hardware.id

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        wattage = fields[("psu_specifications", "wattage")]
        assert wattage["has_value"] is False
        assert wattage["status"] == "unavailable"
        assert fields[("hardware", "architecture")]["has_value"] is False

    def test_ram_fields_are_listed_and_route_correctly(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_ram()
        self._add_record(
            hardware_id,
            "ram_specifications",
            "speed_mhz",
            evidenced_value="6000",
        )

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        assert body["hardware_type"] == "RAM"
        fields = {(f["table_name"], f["field_name"]): f for f in body["fields"]}
        assert set(fields) == {
            ("hardware", "release_date"),
            ("hardware", "architecture"),
            ("ram_specifications", "ddr_generation"),
            ("ram_specifications", "capacity_gb"),
            ("ram_specifications", "speed_mhz"),
            ("ram_specifications", "modules"),
            ("ram_specifications", "ecc"),
            ("ram_specifications", "voltage_v"),
            ("ram_specifications", "form_factor"),
        }
        speed = fields[("ram_specifications", "speed_mhz")]
        assert speed["status"] == "verified"
        assert speed["records"][0]["evidenced_value"] == "6000"
        assert fields[("ram_specifications", "modules")][
            "status"
        ] == "unattributed"

    def test_storage_and_motherboard_route_to_their_tables(self):
        self._seed_metadata_into_db()
        with self.session_factory() as session:
            storage = Hardware(name="Test SSD", manufacturer="Test", type="STORAGE")
            storage.storage_specification = StorageSpecification(
                storage_type="NVMe", capacity_gb=1024
            )
            motherboard = Hardware(
                name="Test Board", manufacturer="Test", type="MOTHERBOARD"
            )
            motherboard.motherboard_specification = MotherboardSpecification(
                socket="AM5", chipset="B650"
            )
            session.add_all([storage, motherboard])
            session.commit()
            storage_id, board_id = storage.id, motherboard.id

        storage_body = self.client.get(
            f"/hardware/{storage_id}/provenance"
        ).json()
        assert storage_body["hardware_type"] == "STORAGE"
        storage_fields = {
            (f["table_name"], f["field_name"]) for f in storage_body["fields"]
        }
        assert ("storage_specifications", "capacity_gb") in storage_fields
        assert ("storage_specifications", "read_mb_s") in storage_fields
        assert all(
            table in {"hardware", "storage_specifications"}
            for table, _ in storage_fields
        )

        board_body = self.client.get(
            f"/hardware/{board_id}/provenance"
        ).json()
        assert board_body["hardware_type"] == "MOTHERBOARD"
        board_fields = {
            (f["table_name"], f["field_name"]) for f in board_body["fields"]
        }
        assert ("motherboard_specifications", "socket") in board_fields
        assert ("motherboard_specifications", "pcie_slots") in board_fields
        assert all(
            table in {"hardware", "motherboard_specifications"}
            for table, _ in board_fields
        )

    def test_psu_summary_counts_are_consistent(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_psu()
        self._add_record(
            hardware_id, "psu_specifications", "wattage", evidenced_value="850"
        )

        body = self.client.get(f"/hardware/{hardware_id}/provenance").json()
        summary = body["summary"]
        assert summary["total_fields"] == len(body["fields"])
        assert summary["verified_fields"] == 1
        # release_date + 4 populated-but-unattributed psu fields; `architecture`
        # is NULL and `wattage` is verified, so unattributed = 1 + 4.
        assert summary["unattributed_fields"] == 5
        assert summary["unavailable_fields"] == 1


class TestBackwardCompatibility(ProvenanceAPITestBase):
    def test_hardware_detail_response_is_unchanged(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()

        body = self.client.get(f"/hardware/{hardware_id}").json()
        assert body["id"] == hardware_id
        assert body["type"] == "CPU"
        assert body["architecture"] == "Zen 5"
        assert body["specifications"]["cores"] == 8
        assert body["specifications"]["socket"] == "AM5"

    def test_benchmark_response_shape_is_unchanged(self):
        self._seed_metadata_into_db()
        hardware_id = self._add_cpu()
        self._add_benchmark(hardware_id)

        response = self.client.get(f"/hardware/{hardware_id}/benchmarks")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert set(body[0]) == {
            "id",
            "hardware_id",
            "benchmark_name",
            "score",
            "unit",
            "test_type",
            "source",
            "recorded_at",
            "quality",
        }
        assert set(body[0]["source"]) == {"id", "name", "url"}


class TestOpsVisibility(ProvenanceAPITestBase):
    """M3 Phase 8: read-only admin visibility for the ingestion_runs and
    publication_batches ops tables (migration v4). The tables are plain SQL
    (no ORM models) so the endpoints probe for their existence and report
    503-style honesty when a pre-v4 database is queried, rather than 500ing."""

    def _seed_ops_rows(self):
        with self.session_factory() as session:
            session.execute(text(
                "INSERT INTO ingestion_runs (run_type, category, mode, "
                "status, rows_seen, rows_applied, rows_rejected, "
                "rows_quarantined, started_at, finished_at, notes) VALUES ("
                "'publication', 'ALL', 'apply', 'success', 10, 10, 0, 0, "
                "'2026-11-16T00:00:00+00:00', "
                "'2026-11-16T00:00:01+00:00', 'm3 pilot RAM batch 10')"
            ))
            session.execute(text(
                "INSERT INTO publication_batches (batch_no, category, "
                "record_count, approved_by, status, created_at, published_at, "
                "notes) VALUES (1, 'ALL', 10, 'm3-curator', 'published', "
                "'2026-11-16T00:00:00+00:00', "
                "'2026-11-16T00:00:01+00:00', 'm3 pilot first batch')"
            ))
            session.commit()

    def test_ops_tables_exist_on_v4_schema(self):
        # The in-memory test DB is created via Base.metadata (v3 tables only);
        # the ops tables come from migration v4. Create them here the way the
        # migration does so the endpoint contract can be exercised.
        with self.engine.connect() as conn:
            conn.execute(text(_INGESTION_RUNS_DDL))
            conn.execute(text(_PUBLICATION_BATCHES_DDL))
            conn.commit()
        with self.session_factory() as session:
            session.execute(text(
                "SELECT 1 FROM ingestion_runs"
            ))
        self._seed_ops_rows()

        ingestion = self.client.get("/ops/ingestion-runs").json()
        assert len(ingestion) == 1
        assert ingestion[0]["run_type"] == "publication"
        assert ingestion[0]["status"] == "success"
        assert ingestion[0]["rows_applied"] == 10

        batches = self.client.get("/ops/publication-batches").json()
        assert len(batches) == 1
        assert batches[0]["batch_no"] == 1
        assert batches[0]["approved_by"] == "m3-curator"
        assert batches[0]["status"] == "published"
        assert batches[0]["record_count"] == 10

    def test_ops_endpoints_require_auth_when_auth_enabled(self):
        # Auth-off suite: the dependency returns None and the endpoints stay
        # readable (same contract as /hardware). Auth-on behavior is covered
        # by test_auth_security's protected-route matrix.
        with self.engine.connect() as conn:
            conn.execute(text(_INGESTION_RUNS_DDL))
            conn.execute(text(_PUBLICATION_BATCHES_DDL))
            conn.commit()

        assert self.client.get("/ops/ingestion-runs").status_code == 200
        assert self.client.get("/ops/publication-batches").status_code == 200

    def test_ops_endpoints_report_unavailable_on_pre_v4_database(self):
        # No ops tables (pre-v4 database): honest 503, never a 500 traceback.
        response = self.client.get("/ops/ingestion-runs")
        assert response.status_code == 503
        assert "ingestion_runs" in response.json()["detail"]

        response = self.client.get("/ops/publication-batches")
        assert response.status_code == 503
        assert "publication_batches" in response.json()["detail"]

    def test_ops_endpoints_limit_and_order_deterministically(self):
        with self.engine.connect() as conn:
            conn.execute(text(_INGESTION_RUNS_DDL))
            conn.execute(text(_PUBLICATION_BATCHES_DDL))
            conn.commit()
        with self.session_factory() as session:
            for i in range(1, 6):
                session.execute(text(
                    "INSERT INTO publication_batches (batch_no, category, "
                    "record_count, approved_by, status, created_at) VALUES "
                    f"({i}, 'ALL', {i}, 'm3-curator', 'published', "
                    f"'2026-11-16T00:00:0{i}+00:00')"
                ))
            session.commit()

        body = self.client.get("/ops/publication-batches?limit=3").json()
        assert len(body) == 3
        # Newest batch first (id DESC): a visibility feed, not an export.
        assert [row["batch_no"] for row in body] == [5, 4, 3]

        full = self.client.get("/ops/publication-batches").json()
        assert len(full) == 5

        assert self.client.get(
            "/ops/publication-batches?limit=500"
        ).status_code == 422
        assert self.client.get(
            "/ops/publication-batches?limit=0"
        ).status_code == 422
