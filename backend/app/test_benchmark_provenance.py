"""Tests for Batch 010 benchmark provenance support."""

import sqlite3
from datetime import date

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.migrations.add_field_provenance import (
    has_benchmark_result_id,
    upgrade_field_provenance,
)
from backend.app.models import (
    BenchmarkResult,
    FieldProvenance,
    Hardware,
)
from backend.app.services.provenance_service import (
    ProvenanceValidationError,
    get_or_create_source,
    insert_provenance_record,
)


class BenchmarkProvenanceBase:
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

    def _seed(self, benchmark_count: int = 2):
        with self.session_factory() as session:
            hardware = Hardware(
                name="Intel Core i5-2500 Processor", manufacturer="Intel",
                type="CPU",
            )
            source = get_or_create_source(
                session, "Geekbench Browser - Geekbench 7 CPU",
                "https://browser.geekbench.com/",
            )
            hardware.benchmark_results = [
                BenchmarkResult(
                    benchmark_name="Geekbench 7",
                    score=695.0,
                    unit="points",
                    test_type="single-core",
                    source_id=source.id,
                )
                for _ in range(benchmark_count)
            ]
            # different test type so scores stay distinct
            if benchmark_count > 1:
                hardware.benchmark_results[1].test_type = "multi-core"
                hardware.benchmark_results[1].score = 2005.0
            session.add(hardware)
            session.commit()
            return (
                hardware.id,
                [b.id for b in hardware.benchmark_results],
                source.id,
            )

    def _insert(self, session, hardware_id, benchmark_result_id, source_id,
                **overrides):
        defaults = {
            "table_name": "benchmark_results",
            "field_name": "score",
            "source_url": "https://browser.geekbench.com/",
            "evidence_status": "verified",
            "batch_no": 0,
            "evidenced_value": "695.0",
        }
        defaults.update(overrides)
        return insert_provenance_record(
            session,
            hardware_id=hardware_id,
            benchmark_result_id=benchmark_result_id,
            source_id=source_id,
            **defaults,
        )


class TestBenchmarkProvenancePersistence(BenchmarkProvenanceBase):
    def test_benchmark_provenance_inserts(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            record, created = self._insert(session, hw, bids[0], source_id)
            session.commit()
            assert created
            assert record.benchmark_result_id == bids[0]
            assert record.table_name == "benchmark_results"
            assert record.field_name == "score"
            assert record.hardware_id == hw

    def test_benchmark_result_requires_id(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(session, hw, None, source_id)

    def test_unknown_benchmark_result_rejected(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(session, hw, 999999, source_id)

    def test_mismatched_hardware_rejected(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            other = Hardware(name="Ryzen 5", manufacturer="AMD", type="CPU")
            session.add(other)
            session.commit()
            with pytest.raises(ProvenanceValidationError):
                self._insert(session, other.id, bids[0], source_id)

    def test_spec_tables_reject_benchmark_result_id(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session, hw, bids[0], source_id,
                    table_name="cpu_specifications", field_name="cores",
                )

    def test_benchmark_result_field_must_be_score(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session, hw, bids[0], source_id, field_name="cores",
                )

    def test_unknown_status_rejected(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session, hw, bids[0], source_id,
                    evidence_status="partial",
                )

    def test_multiple_sources_per_benchmark_record(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            second = get_or_create_source(
                session, "Secondary cross-check", "https://example.invalid/"
            )
            _, created_a = self._insert(session, hw, bids[0], source_id)
            _, created_b = self._insert(
                session, hw, bids[0], second.id,
                source_url="https://example.invalid/",
            )
            session.commit()
            assert created_a and created_b
        with self.session_factory() as session:
            count = (
                session.query(FieldProvenance)
                .filter_by(benchmark_result_id=bids[0]).count()
            )
            assert count == 2

    def test_duplicate_prevention_and_idempotent_rerun(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            _, first = self._insert(session, hw, bids[0], source_id)
            _, second = self._insert(session, hw, bids[0], source_id)
            session.commit()
            assert first is True
            assert second is False
        with self.session_factory() as session:
            count = (
                session.query(FieldProvenance)
                .filter_by(benchmark_result_id=bids[0]).count()
            )
            assert count == 1

    def test_benchmark_values_and_configuration_preserved(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            self._insert(session, hw, bids[0], source_id)
            session.commit()
        with self.session_factory() as session:
            result = session.get(BenchmarkResult, bids[0])
            assert result.score == 695.0
            assert result.test_type == "single-core"
            assert result.unit == "points"
            assert result.benchmark_name == "Geekbench 7"

    def test_unknown_incomplete_evidence_metadata_allowed(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            record, created = self._insert(
                session, hw, bids[0], source_id,
                license_name=None, attribution=None, access_date=None,
                confidence=None, source_reference=None,
                evidence_status="uncertain",
            )
            session.commit()
            assert created
            assert record.license_name is None
            assert record.attribution is None
            assert record.access_date is None

    def test_restricted_dataset_not_imported(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            self._insert(session, hw, bids[0], source_id)
            session.commit()
        with self.session_factory() as session:
            assert session.query(BenchmarkResult).count() == 2
            assert session.query(Hardware).count() == 1

    def test_referential_integrity_via_fk(self):
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            record = FieldProvenance(
                hardware_id=999999,
                source_id=source_id,
                table_name="benchmark_results",
                field_name="score",
                evidenced_value="695.0",
                source_url="https://browser.geekbench.com/",
                evidence_status="verified",
                batch_no=0,
                benchmark_result_id=bids[0],
            )
            session.add(record)
            with pytest.raises(Exception):
                session.flush()

    def test_benchmark_row_with_provenance_cannot_be_deleted(self):
        """Orphan prevention: provenance rows keep their benchmark record."""
        hw, bids, source_id = self._seed()
        with self.session_factory() as session:
            self._insert(session, hw, bids[0], source_id)
            session.commit()
        with self.session_factory() as session:
            result = session.get(BenchmarkResult, bids[0])
            session.delete(result)
            with pytest.raises(Exception):
                session.flush()
        with self.session_factory() as session:
            count = (
                session.query(FieldProvenance)
                .filter_by(benchmark_result_id=bids[0]).count()
            )
            assert count == 1
            assert session.query(BenchmarkResult).count() == 2


class TestSchemaUpgradeOnExistingDatabase:
    OLD_DDL = """
    CREATE TABLE field_provenance (
        id INTEGER PRIMARY KEY,
        hardware_id INTEGER NOT NULL,
        source_id INTEGER NOT NULL,
        table_name VARCHAR(50) NOT NULL
            CHECK (table_name IN ('hardware','cpu_specifications',
                                  'gpu_specifications')),
        field_name VARCHAR(50) NOT NULL,
        evidenced_value VARCHAR(200) NOT NULL,
        source_url VARCHAR(500) NOT NULL,
        license_name VARCHAR(100),
        license_notes TEXT,
        attribution TEXT,
        access_date DATE,
        confidence VARCHAR(20),
        evidence_status VARCHAR(20) NOT NULL
            CHECK (evidence_status IN ('verified','uncertain','excluded',
                                       'unmatched')),
        source_reference VARCHAR(200),
        match_method VARCHAR(100),
        batch_no INTEGER NOT NULL,
        notes TEXT,
        recorded_at DATETIME NOT NULL,
        UNIQUE (hardware_id, table_name, field_name, source_id,
                evidenced_value, evidence_status)
    )
    """

    def _build_old_database(self, path):
        connection = sqlite3.connect(path)
        connection.executescript(self.OLD_DDL)
        for i in range(5):
            connection.execute(
                "INSERT INTO field_provenance (hardware_id, source_id,"
                " table_name, field_name, evidenced_value, source_url,"
                " evidence_status, batch_no, recorded_at)"
                " VALUES (1, 1, 'hardware', 'architecture', ?, 'u',"
                " 'verified', 1, '2026-10-09 00:00:00')",
                (f"value-{i}",),
            )
        connection.commit()
        connection.close()

    def test_upgrade_adds_column_and_preserves_rows(self, tmp_path):
        db = tmp_path / "spectra_test.db"
        self._build_old_database(db)
        assert has_benchmark_result_id(db) is False

        assert upgrade_field_provenance(db) is True

        assert has_benchmark_result_id(db) is True
        connection = sqlite3.connect(db)
        rows = connection.execute(
            "SELECT COUNT(*) FROM field_provenance").fetchone()[0]
        assert rows == 5
        # the benchmark coherence check now exists
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'field_provenance'"
        ).fetchone()[0]
        connection.close()
        assert "benchmark_result_id" in sql
        assert "benchmark_results" in sql

    def test_upgrade_is_idempotent(self, tmp_path):
        db = tmp_path / "spectra_test.db"
        self._build_old_database(db)
        assert upgrade_field_provenance(db) is True
        assert upgrade_field_provenance(db) is False

    def test_upgraded_table_rejects_mismatched_rows(self, tmp_path):
        db = tmp_path / "spectra_test.db"
        self._build_old_database(db)
        upgrade_field_provenance(db)
        connection = sqlite3.connect(db)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO field_provenance (hardware_id, source_id,"
                " table_name, field_name, evidenced_value, source_url,"
                " evidence_status, batch_no, recorded_at, benchmark_result_id)"
                " VALUES (1, 1, 'cpu_specifications', 'cores', 'x', 'u',"
                " 'verified', 1, '2026-10-10 00:00:00', 1)"
            )
        connection.close()