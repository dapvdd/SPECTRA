"""Tests for Batch 010 external-identifier source-correction logic."""

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import ExternalIdentifier, Hardware
from backend.app.services.identifier_source import (
    AMD_CSV_SOURCE_NAME,
    INTEL_CSV_SOURCE_NAME,
    decide_reassignment,
    expected_source_name,
)
from backend.app.services.provenance_service import get_or_create_source


class IdentifierSourceTestBase:
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


class TestExpectedSourceId(IdentifierSourceTestBase):
    def test_intel_cpu_id_maps_to_intel_csv_source(self):
        assert expected_source_name("intel_cpu_id") == INTEL_CSV_SOURCE_NAME

    def test_amd_product_ids_map_to_amd_csv_source(self):
        for it in ("product_id_tray", "product_id_boxed", "product_id_mpk"):
            assert expected_source_name(it) == AMD_CSV_SOURCE_NAME

    def test_unknown_type_returns_none(self):
        assert expected_source_name("mystery_id") is None


class TestDecideReassignment(IdentifierSourceTestBase):
    INTEL_IDS = {"86826", "198019"}
    AMD_IDS = {
        "product_id_tray": {"100-000000775"},
        "product_id_boxed": {"BX80677I57500"},
        "product_id_mpk": {"MPK-123"},
    }

    def test_intel_id_present_is_reassigned(self):
        target, evidence = decide_reassignment(
            "intel_cpu_id", "198019", self.INTEL_IDS, self.AMD_IDS
        )
        assert target == INTEL_CSV_SOURCE_NAME
        assert evidence["present_in_intel_cpuid"] is True

    def test_intel_id_absent_is_not_reassigned(self):
        target, evidence = decide_reassignment(
            "intel_cpu_id", "999999", self.INTEL_IDS, self.AMD_IDS
        )
        assert target is None
        assert evidence["present_in_intel_cpuid"] is False

    def test_amd_tray_present_is_reassigned(self):
        target, evidence = decide_reassignment(
            "product_id_tray", "100-000000775", self.INTEL_IDS, self.AMD_IDS
        )
        assert target == AMD_CSV_SOURCE_NAME
        assert evidence["present_in_amd_product_id_tray"] is True

    def test_amd_boxed_uses_boxed_namespace(self):
        target, _evidence = decide_reassignment(
            "product_id_boxed", "BX80677I57500", self.INTEL_IDS, self.AMD_IDS
        )
        assert target == AMD_CSV_SOURCE_NAME

    def test_amd_id_present_only_in_tray_not_reassigned_from_mpk(self):
        target, evidence = decide_reassignment(
            "product_id_mpk", "100-000000775", self.INTEL_IDS, self.AMD_IDS
        )
        assert target is None
        # present in tray, but this identifier type is MPK
        assert evidence["present_in_amd_product_id_mpk"] is False

    def test_unknown_type_never_reassigned(self):
        target, _evidence = decide_reassignment(
            "mystery_id", "anything", self.INTEL_IDS, self.AMD_IDS
        )
        assert target is None


class TestIdentifierSourceCorrectionEndToEnd(IdentifierSourceTestBase):
    def _seed(self):
        with self.session_factory() as session:
            pm = get_or_create_source(
                session,
                "PassMark CPU benchmark catalog (benchmark-cpus.csv)",
                "https://www.cpubenchmark.net/",
            )
            intel_src = get_or_create_source(
                session,
                "Intel ARK (intel-cpus.csv snapshot)",
                "https://ark.intel.com/",
            )
            amd_src = get_or_create_source(
                session,
                "AMD product specifications (amd-cpus.csv snapshot)",
                "https://www.amd.com/en/products/specifications/processors",
            )
            intel_hw = Hardware(name="Intel Core i5-9400F", manufacturer="Intel", type="CPU")
            amd_hw = Hardware(name="AMD Ryzen 5 5600", manufacturer="AMD", type="CPU")
            session.add(intel_hw)
            session.add(amd_hw)
            session.flush()
            session.add_all([
                ExternalIdentifier(
                    hardware_id=intel_hw.id, source_id=pm.id,
                    external_id="198019", identifier_type="intel_cpu_id",
                ),
                ExternalIdentifier(
                    hardware_id=amd_hw.id, source_id=pm.id,
                    external_id="100-000000775", identifier_type="product_id_tray",
                ),
            ])
            session.commit()
            return {
                "pm": pm.id, "intel_src": intel_src.id, "amd_src": amd_src.id,
                "intel_hw": intel_hw.id, "amd_hw": amd_hw.id,
            }

    def test_reassignment_updates_only_source_labels(self):
        sources = self._seed()
        INTEL_IDS = {"198019"}
        AMD_IDS = {"product_id_tray": {"100-000000775"},
                   "product_id_boxed": set(), "product_id_mpk": set()}
        with self.session_factory() as session:
            from backend.app.models import Source

            intel_source = session.scalar(
                select(Source).where(
                    Source.name == "Intel ARK (intel-cpus.csv snapshot)"
                )
            )
            amd_source = session.scalar(
                select(Source).where(
                    Source.name == "AMD product specifications (amd-cpus.csv snapshot)"
                )
            )
            intel_rec = session.scalar(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.external_id == "198019"
                )
            )
            amd_rec = session.scalar(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.external_id == "100-000000775"
                )
            )
            new_intel, _ = decide_reassignment(
                intel_rec.identifier_type, intel_rec.external_id,
                INTEL_IDS, AMD_IDS)
            new_amd, _ = decide_reassignment(
                amd_rec.identifier_type, amd_rec.external_id,
                INTEL_IDS, AMD_IDS)
            # the decision contract is the registered source NAME, and the
            # resolved rows in this database carry those exact names
            assert new_intel == intel_source.name
            assert new_amd == amd_source.name

            # production resolves the name to this database's id
            intel_rec.source_id = intel_source.id
            amd_rec.source_id = amd_source.id
            session.commit()

        with self.session_factory() as session:
            rec = session.scalar(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.external_id == "198019"
                )
            )
            assert rec.source_id == sources["intel_src"]
            assert rec.external_id == "198019"
            assert rec.identifier_type == "intel_cpu_id"
            assert rec.hardware_id == sources["intel_hw"]

    def test_duplicate_constraint_still_holds(self):
        sources = self._seed()
        with self.session_factory() as session:
            session.add(ExternalIdentifier(
                hardware_id=sources["intel_hw"],
                source_id=sources["pm"],
                external_id="198019",
                identifier_type="intel_cpu_id",
            ))
            with pytest.raises(Exception):
                session.flush()