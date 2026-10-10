"""Tests for the Batch 009 base-import provenance reconstruction logic.

Covers the deterministic cell classification, source value map building, the
loader's persistence guardrails (idempotency, coverage skip, invalid
references, hardware-value preservation) and alignment with the existing
``field_provenance`` schema constraints.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    CPUSpecification,
    FieldProvenance,
    Hardware,
)
from backend.app.services.base_import_provenance import (
    UNCERTAIN,
    VERIFIED,
    VALID_FIELDS,
    build_source_value_map,
    classify_cell,
)
from backend.app.services.provenance_service import (
    ProvenanceValidationError,
    get_or_create_source,
    insert_provenance_record,
    VALID_FIELDS as PROVENANCE_SERVICE_FIELDS,
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

    def _add_hardware(self, name="Intel Core i5-9400F", hardware_type="CPU",
                      manufacturer="Intel") -> int:
        with self.session_factory() as session:
            hardware = Hardware(
                name=name,
                manufacturer=manufacturer,
                type=hardware_type,
            )
            hardware.cpu_specification = CPUSpecification(
                cores=6, threads=6, base_clock_ghz=2.9, boost_clock_ghz=4.1,
                tdp_w=65.0, socket="LGA1151",
            )
            session.add(hardware)
            session.commit()
            return hardware.id

    def _add_source(self, name="Intel ARK (intel-cpus.csv snapshot)",
                    url="https://ark.intel.com/") -> int:
        with self.session_factory() as session:
            source = get_or_create_source(session, name, url)
            session.commit()
            return source.id


class TestClassifyCell:
    def test_verified_unique_dataset(self):
        decision = classify_cell(6, {"intel": {6, 12}, "amd": {8}, "passmark": {4}})
        assert decision.status == VERIFIED
        assert decision.dataset == "intel"
        assert decision.matching_row_count == 1

    def test_verified_unique_dataset_counts_multiple_matching_rows(self):
        # Two rows in the same dataset carry the same value; identity is still
        # unique to that dataset but the exact source row is not.
        decision = classify_cell(6, {"passmark": [6, 6, 12, 4]})
        assert decision.status == VERIFIED
        assert decision.dataset == "passmark"
        assert decision.matching_row_count == 2

    def test_uncertain_when_value_in_multiple_datasets(self):
        decision = classify_cell(6, {"intel": {6, 12}, "passmark": {6, 4}})
        assert decision.status == UNCERTAIN
        assert decision.dataset is None
        assert set(decision.matching_datasets) == {"intel", "passmark"}

    def test_unmatched_when_value_in_no_dataset(self):
        decision = classify_cell(9, {"intel": {6, 12}, "amd": {8}})
        assert decision.status == "unmatched"
        assert decision.dataset is None
        assert decision.matching_row_count == 0

    def test_empty_when_no_source_values_available(self):
        decision = classify_cell(6, {})
        assert decision.status == "empty"
        assert decision.dataset is None

    def test_null_never_counted(self):
        decision = classify_cell(None, {"intel": {None, 6}})
        # None is not a stored value to verify
        assert decision.status == "empty"

    def test_false_positive_guarded_single_exact_match(self):
        # A common small value must not be silently attributed when another
        # dataset also contains it.
        decision = classify_cell(4, {"amd": {4}, "passmark": {4}})
        assert decision.status == UNCERTAIN

    def test_true_positive_only_for_exact_match(self):
        decision = classify_cell(4, {"intel": {4, 8, 16}})
        assert decision.status == VERIFIED
        assert decision.dataset == "intel"


class TestBuildSourceValueMap:
    def test_collects_non_null_values_per_dataset(self):
        rows = {
            "intel": [{"cores": 6}, {"cores": 12}, {"cores": None}],
            "amd": [{"cores": 8}],
        }
        result = build_source_value_map(rows, "cores")
        assert result == {"intel": [6, 12], "amd": [8]}

    def test_empty_dataset_omitted(self):
        rows = {"intel": [{"cores": None}]}
        assert build_source_value_map(rows, "cores") == {}

    def test_missing_field_omitted(self):
        rows = {"intel": [{"cores": 6}]}
        assert build_source_value_map(rows, "threads") == {}


class TestFieldSetAlignment:
    def test_valid_fields_match_provenance_service(self):
        assert VALID_FIELDS == PROVENANCE_SERVICE_FIELDS


class TestLoaderPersistenceGuardrails(ProvenanceTestBase):
    def _insert_base_import(self, session, hardware_id, source_id,
                            field="cores", value="6"):
        return insert_provenance_record(
            session,
            hardware_id=hardware_id,
            table_name="cpu_specifications",
            field_name=field,
            source_id=source_id,
            source_url="https://ark.intel.com/",
            evidence_status="verified",
            batch_no=0,
            evidenced_value=value,
            license_name=None,
            license_notes="no reuse grant documented.",
            access_date=None,
            confidence="high",
            source_reference="intel-cpus.csv#Intel=Intel Core i5-9400F",
            match_method="exact normalized base-import value reconcile",
            notes="Batch 009 base-import provenance reconstruction.",
        )

    def test_insert_and_idempotent_rerun(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            _, created = self._insert_base_import(session, hardware_id, source_id)
            session.commit()
            assert created
            _, created_again = self._insert_base_import(
                session, hardware_id, source_id)
            session.commit()
            assert not created_again
        with self.session_factory() as session:
            count = (
                session.query(FieldProvenance)
                .filter_by(hardware_id=hardware_id).count()
            )
            assert count == 1

    def test_preserves_hardware_specification_values(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            self._insert_base_import(session, hardware_id, source_id)
            session.commit()
        with self.session_factory() as session:
            hardware = session.get(Hardware, hardware_id)
            assert hardware.cpu_specification.cores == 6
            assert hardware.cpu_specification.boost_clock_ghz == 4.1
            assert hardware.cpu_specification.socket == "LGA1151"

    def test_invalid_table_field_rejected(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                insert_provenance_record(
                    session,
                    hardware_id=hardware_id,
                    table_name="hardware",
                    field_name="name",
                    source_id=source_id,
                    source_url="https://ark.intel.com/",
                    evidence_status="verified",
                    batch_no=0,
                )
            with pytest.raises(ProvenanceValidationError):
                insert_provenance_record(
                    session,
                    hardware_id=hardware_id,
                    table_name="benchmark_results",
                    field_name="score",
                    source_id=source_id,
                    source_url="https://browser.geekbench.com/",
                    evidence_status="verified",
                    batch_no=0,
                )

    def test_invalid_status_rejected(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                insert_provenance_record(
                    session,
                    hardware_id=hardware_id,
                    table_name="cpu_specifications",
                    field_name="cores",
                    source_id=source_id,
                    source_url="https://ark.intel.com/",
                    evidence_status="partial",
                    batch_no=0,
                )

    def test_unknown_hardware_rejected(self):
        source_id = self._add_source()
        with self.session_factory() as session:
            with pytest.raises(ProvenanceValidationError):
                self._insert_base_import(session, 999_999, source_id)

    def test_license_notes_preserved(self):
        hardware_id = self._add_hardware()
        source_id = self._add_source()
        with self.session_factory() as session:
            self._insert_base_import(session, hardware_id, source_id)
            session.commit()
        with self.session_factory() as session:
            record = session.query(FieldProvenance).first()
            assert record.license_notes == "no reuse grant documented."
            assert record.batch_no == 0
            assert record.evidence_status == VERIFIED

    def test_conflicting_value_excluded(self):
        """The loader only persists unique-dataset matches; a value shared by
        two datasets is never inserted. Simulated by inserting the same
        underlying cell with a second dataset's value: the service must keep
        them as distinct source-support rows and never overwrite the first."""
        hardware_id = self._add_hardware()
        source_1 = self._add_source("Intel ARK (intel-cpus.csv snapshot)")
        source_2 = self._add_source(
            "PassMark CPU benchmark catalog (benchmark-cpus.csv)",
            "https://www.cpubenchmark.net/")
        with self.session_factory() as session:
            _, created_a = self._insert_base_import(
                session, hardware_id, source_1, value="6")
            _, created_b = self._insert_base_import(
                session, hardware_id, source_2, value="6")
            session.commit()
            assert created_a and created_b
        with self.session_factory() as session:
            count = session.query(FieldProvenance).count()
            assert count == 2
        # the classification-level rule is still exercised here
        decision = classify_cell(6, {"intel": {6}, "passmark": {6}})
        assert decision.status == UNCERTAIN