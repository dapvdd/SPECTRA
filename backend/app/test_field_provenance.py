import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    FieldProvenance,
    GPUSpecification,
    Hardware,
    Source,
)
from backend.app.services.provenance_service import (
    ProvenanceValidationError,
    get_or_create_source,
    insert_provenance_record,
    validate_field_reference,
)


class ProvenanceTestBase:
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

    def _add_hardware(self, name="GeForce RTX 5070", hardware_type="GPU",
                      manufacturer="NVIDIA") -> int:
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer=manufacturer,
                type=hardware_type,
            )
            session.add(hardware)
            session.commit()
            return hardware.id

    def _add_source(self, name="GPU Ark",
                    url="https://gpuark.com/datasets/") -> int:
        with self.session_factory() as session:
            source = get_or_create_source(session, name, url)
            session.commit()
            return source.id

    def _insert(self, session, hardware_id, source_id, **kwargs):
        defaults = {
            "table_name": "gpu_specifications",
            "field_name": "core_clock_mhz",
            "source_url": "https://gpuark.com/datasets/",
            "evidence_status": "verified",
            "batch_no": 2,
            "evidenced_value": "1500",
        }
        defaults.update(kwargs)
        return insert_provenance_record(
            session, hardware_id=hardware_id, source_id=source_id, **defaults
        )


class TestFieldProvenanceModel(ProvenanceTestBase):
    def test_table_is_created(self):
        tables = set(inspect(self.engine).get_table_names())
        assert "field_provenance" in tables

    def test_provenance_to_hardware_referential_integrity(self):
        """An unknown hardware_id must be rejected."""
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(session, hardware_id=999999, source_id=source_id)

    def test_provenance_to_source_referential_integrity(self):
        """A foreign source_id must raise an IntegrityError."""
        hardware_id = self._add_hardware()
        with self.session_factory() as session:
            with pytest.raises(IntegrityError):
                self._insert(session, hardware_id, source_id=4242)

    def test_multiple_sources_can_support_one_field(self):
        hardware_id = self._add_hardware()
        ark_id = self._add_source(name="GPU Ark")
        wiki_id = self._add_source(name="Wikipedia",
                                   url="https://en.wikipedia.org/")
        with self.session_factory() as session:
            self._insert(session, hardware_id, ark_id)
            self._insert(
                session,
                hardware_id,
                wiki_id,
                source_url="https://en.wikipedia.org/wiki/Radeon_RX_7000",
            )
            session.commit()
            records = session.scalars(
                select(FieldProvenance).where(
                    FieldProvenance.hardware_id == hardware_id
                )
            ).all()
            assert len(records) == 2
            assert {r.source_id for r in records} == {ark_id, wiki_id}

    def test_permitted_statuses_only(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session,
                    hardware_id,
                    source_id,
                    evidence_status="wibble",
                )

    def test_unknown_field_reference_rejected(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session,
                    hardware_id,
                    source_id,
                    table_name="gpu_specifications",
                    field_name="not_a_column",
                )
            with pytest.raises(ProvenanceValidationError):
                self._insert(
                    session,
                    hardware_id,
                    source_id,
                    table_name="not_a_table",
                    field_name="cores",
                )

    def test_unknown_or_missing_source_metadata_allowed(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            record, inserted = self._insert(
                session,
                hardware_id,
                source_id,
                license_name=None,
                attribution=None,
                access_date=None,
                confidence=None,
                match_method=None,
                source_reference=None,
                notes=None,
            )
            session.commit()
            assert inserted is True
            loaded = session.get(FieldProvenance, record.id)
            assert loaded.license_name is None
            assert loaded.attribution is None
            assert loaded.access_date is None
            assert loaded.confidence is None

    def test_idempotent_replay(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            _, inserted_a = self._insert(session, hardware_id, source_id)
            _, inserted_b = self._insert(session, hardware_id, source_id)
            session.commit()
            assert inserted_a is True
            assert inserted_b is False
            assert len(session.scalars(select(FieldProvenance)).all()) == 1

    def test_license_and_attribution_round_trip(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            record, inserted = self._insert(
                session,
                hardware_id,
                source_id,
                license_name="CC BY 4.0",
                attribution="GPU Ark (2026). GPU specifications dataset.",
                license_notes="Attribution required per licence.",
            )
            session.commit()
            assert inserted is True
            loaded = session.get(FieldProvenance, record.id)
            assert loaded.license_name == "CC BY 4.0"
            assert loaded.attribution == (
                "GPU Ark (2026). GPU specifications dataset."
            )
            assert loaded.license_notes == (
                "Attribution required per licence."
            )

    def test_schema_initialization_on_existing_database(self):
        """Creating a fresh schema must include the new table and retain the
        existing tables intact."""
        tables = set(inspect(self.engine).get_table_names())
        assert {"hardware", "gpu_specifications", "cpu_specifications"} \
            <= tables
        assert "field_provenance" in tables

    def test_existing_application_queries_remain_compatible(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            gpu = GPUSpecification(
                hardware_id=hardware_id,
                core_clock_mhz=1500,
                memory_gb=8,
            )
            session.add(gpu)
            self._insert(session, hardware_id, source_id)
            session.commit()
            loaded = session.get(Hardware, hardware_id)
            assert loaded.type == "GPU"
            assert loaded.gpu_specification.core_clock_mhz == 1500
            assert loaded.gpu_specification.memory_gb == 8
            assert len(loaded.field_provenance) == 1
            assert loaded.field_provenance[0].field_name == "core_clock_mhz"

    def test_all_four_evidence_statuses_supported(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            for status in ("verified", "uncertain", "excluded", "unmatched"):
                _, inserted = self._insert(
                    session, hardware_id, source_id,
                    evidence_status=status,
                    evidenced_value=f"v-{status}",
                )
                assert inserted is True
            session.commit()
            statuses = {
                r.evidence_status for r in session.scalars(
                    select(FieldProvenance)
                ).all()
            }
            assert statuses == {
                "verified", "uncertain", "excluded", "unmatched"
            }

    def test_duplicate_identity_enforced_at_database_level(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            self._insert(session, hardware_id, source_id)
            session.commit()
        with self.session_factory() as session:
            _, inserted = self._insert(session, hardware_id, source_id)
            assert inserted is False
            session.commit()

    def test_loader_does_not_change_specification_values(self):
        """Running provenance insertions must not mutate stored specs."""
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            session.add(GPUSpecification(
                hardware_id=hardware_id,
                core_clock_mhz=1500,
                memory_gb=8,
            ))
            session.commit()
            self._insert(session, hardware_id, source_id)
            session.commit()
            spec = session.scalars(
                select(GPUSpecification).where(
                    GPUSpecification.hardware_id == hardware_id
                )
            ).one()
            assert spec.core_clock_mhz == 1500
            assert spec.memory_gb == 8


class TestProvenanceService(ProvenanceTestBase):
    def test_validate_field_reference(self):
        validate_field_reference("hardware", "architecture")
        validate_field_reference("cpu_specifications", "boost_clock_ghz")
        validate_field_reference("gpu_specifications", "memory_bus_width_bits")
        with pytest.raises(ProvenanceValidationError):
            validate_field_reference("hardware", "boost_clock_ghz")
        with pytest.raises(ProvenanceValidationError):
            validate_field_reference("gpu_specifications", "cores")

    def test_get_or_create_source_reuses_existing(self):
        self._add_source(name="GPU Ark")
        with self.session_factory() as session:
            again = get_or_create_source(session, "GPU Ark",
                                         "https://gpuark.com/datasets/")
            session.commit()
            assert again.name == "GPU Ark"
            assert len(session.scalars(select(Source)).all()) == 1

    def test_unknown_source_url_is_preserved_as_empty(self):
        """When the artifact records no source URL we store an empty value
        rather than inventing one."""
        hardware_id = self._add_hardware()
        source_id = self._add_source(name="Unknown")
        with self.session_factory() as session:
            record, inserted = self._insert(
                session, hardware_id, source_id, source_url=""
            )
            session.commit()
            assert inserted is True
            loaded = session.get(FieldProvenance, record.id)
            assert loaded.source_url == ""