"""Tests for the Stage 3 enrichment pipeline (consumes Stage 2 acquisitions).

Encodes the pipeline contract:

- ``EnrichmentPlan`` turns one ``AcquiredValue`` into one ``EnrichmentAction``
  (table/field/hardware match + status) without writing anything.
- Status vocabulary: ``apply`` (clear + known field + unique hardware match),
  ``reject`` (unknown field / null value / no hardware match), ``quarantine``
  (non-clear license), ``conflict`` (ambiguous hardware identity).
- ``audit_dev_db`` returns read-only coverage/gap counts for a dev DB path.
- ``validate_acquisitions`` reports publishable vs rejected/quarantined.
- ``import_dev`` writes ONLY to an allowed dev DB (never ``data/spectra.db``),
  is transactional + idempotent, records provenance, and returns a diff.
- ``rollback_dev`` restores a dev DB from a baseline snapshot (dev-only).

All DB work uses isolated in-memory/on-disk engines — never production.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    FieldProvenance,
    GPUSpecification,
    Hardware,
)
from backend.app.scripts import enrichment_pipeline as ep
from backend.app.scripts.source_acquisition import AcquiredValue


def make_value(hardware_name="NVIDIA RTX 4090", field="tdp_w",
               normalized="450 W", raw="450 W", unit="W",
               license_status="clear", hardware_kind="GPU", **overrides) -> AcquiredValue:
    return ep.make_value(
        source_name="GPU Ark",
        source_url="https://www.gpuark.com",
        license_status=license_status,
        license_name="CC BY 4.0",
        source_reference="gpuark-gpu-specs.csv",
        hardware_name=hardware_name,
        field=field,
        raw_value=raw,
        normalized_value=normalized,
        unit=unit,
        hardware_kind=hardware_kind,
        **overrides,
    )


class BaseEngine:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def teardown_method(self):
        self.engine.dispose()

    def _seed_gpu(self, name="NVIDIA RTX 4090", manufacturer="NVIDIA",
                  segment="desktop") -> int:
        with self.session_factory() as session:
            hw = Hardware(name=name, manufacturer=manufacturer,
                          type="GPU", segment=segment)
            session.add(hw)
            session.commit()
            return hw.id


# ---------------------------------------------------------------------------
# EnrichmentPlan (no DB touches)
# ---------------------------------------------------------------------------


class TestEnrichmentPlan:
    def test_plan_produces_one_action_per_value(self):
        values = [make_value(hardware_name="GPU A"), make_value(hardware_name="GPU B")]
        plan = ep.EnrichmentPlan(values, source_reference="gpuark.csv", batch_no=19)
        assert len(plan.actions) == len(values)
        assert plan.batch_no == 19

    def test_clear_gpu_field_maps_to_gpu_specifications(self):
        value = make_value(hardware_name="GPU A", field="tdp_w")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.actions[0]
        assert action.table_name == "gpu_specifications"
        assert action.field_name == "tdp_w"
        assert action.status == "apply"
        assert action.normalized_value == "450 W"

    def test_unknown_field_has_explicit_reject(self):
        value = make_value(hardware_name="GPU A", field="not_a_column")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "reject"
        assert "unknown field" in action.reason.lower()

    def test_restricted_value_is_quarantined(self):
        value = make_value(hardware_name="GPU A", field="tdp_w",
                           license_status="restricted")
        plan = ep.EnrichmentPlan([value], source_reference="x.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "quarantine"
        assert "license" in action.reason.lower()

    def test_null_normalized_value_is_rejected(self):
        value = make_value(hardware_name="GPU A", normalized=None)
        plan = ep.EnrichmentPlan([value], source_reference="x.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "reject"
        assert "null" in action.reason.lower()

    @pytest.mark.parametrize("sentinel", [
        "unknown", "Unknown", "UNKNOWN",
        "n/a", "N/A", "na", "NA",
        "none", "None", "NONE",
        "-", "—", "–",
        "null", "Null", "NULL",
    ], ids=lambda s: repr(s))
    def test_sentinel_string_normalized_value_is_rejected(self, sentinel):
        """Sentinel strings must be rejected as fabricated data, not persisted.

        Defense-in-depth: even if normalize_field_value somehow returns a sentinel
        string (e.g. due to a bug in an adapter), _classify must catch it.
        """
        value = make_value(hardware_name="GPU A", normalized=sentinel)
        plan = ep.EnrichmentPlan([value], source_reference="x.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "reject", (
            f"sentinel {sentinel!r} passed _classify as status={action.status}; "
            "expected 'reject' — fabricated values must never be imported"
        )

    def test_empty_string_normalized_value_is_rejected(self):
        value = make_value(hardware_name="GPU A", normalized="   ")
        plan = ep.EnrichmentPlan([value], source_reference="x.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "reject"

    def test_valid_numeric_value_is_not_rejected(self):
        """Sanity check: real numeric values must still be accepted."""
        value = make_value(hardware_name="GPU A", field="tdp_w",
                           normalized="450 W", raw="450 W")
        plan = ep.EnrichmentPlan([value], source_reference="x.csv", batch_no=19)
        action = plan.actions[0]
        assert action.status == "apply"
        assert action.normalized_value == "450 W"


# ---------------------------------------------------------------------------
# Hardware identity resolution (in-memory engine)
# ---------------------------------------------------------------------------


class TestHardwareMatching(BaseEngine):
    def test_exact_segment_match_resolves_hardware_id(self):
        hid = self._seed_gpu(name="NVIDIA RTX 4090", segment="desktop")
        value = make_value(hardware_name="NVIDIA RTX 4090", field="tdp_w")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.resolve_against(self.session_factory(), plan.actions[0])
        assert action.status == "apply"
        assert action.hardware_id == hid

    def test_ambiguous_name_across_segments_is_conflict_not_guess(self):
        self._seed_gpu(name="NVIDIA RTX 4090", segment="desktop")
        self._seed_gpu(name="NVIDIA RTX 4090", segment="mobile")
        value = make_value(hardware_name="NVIDIA RTX 4090", hardware_kind="GPU")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.resolve_against(self.session_factory(), plan.actions[0])
        # No segment signal on the acquisition -> ambiguity is surfaced as
        # conflict, never resolved by guessing desktop vs mobile.
        assert action.status == "conflict"
        assert "ambig" in action.reason.lower()

    def test_explicit_segment_signal_resolves_that_segment(self):
        self._seed_gpu(name="NVIDIA RTX 4090", segment="desktop")
        hid_mobile = self._seed_gpu(name="NVIDIA RTX 4090", segment="mobile")
        value = make_value(hardware_name="NVIDIA RTX 4090", hardware_kind="GPU",
                           segment_hint="mobile")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.resolve_against(self.session_factory(), plan.actions[0])
        assert action.status == "apply"
        assert action.hardware_id == hid_mobile

    def test_conflicting_segment_is_flagged(self):
        self._seed_gpu(name="NVIDIA RTX 4090", segment="desktop")
        value = make_value(hardware_name="NVIDIA RTX 4090")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.resolve_against(self.session_factory(), plan.actions[0])
        assert action.status != "reject"

    def test_no_match_yields_reject_for_unknown_hardware(self):
        value = make_value(hardware_name="Totally Unknown GPU", field="tdp_w")
        plan = ep.EnrichmentPlan([value], source_reference="gpuark.csv", batch_no=19)
        action = plan.resolve_against(self.session_factory(), plan.actions[0])
        assert action.status == "reject"
        assert "no match" in action.reason.lower()


# ---------------------------------------------------------------------------
# validate_acquisitions
# ---------------------------------------------------------------------------


class TestValidateAcquisitions:
    def test_accepts_all_clear_known_values(self):
        values = [make_value(hardware_name="A"), make_value(hardware_name="B")]
        result = ep.validate_acquisitions(values)
        assert result["accepted"] == 2
        assert result["rejected"] == 0
        assert result["blocked"] is False

    def test_blocks_on_restricted_source(self):
        value = make_value(hardware_name="A", license_status="restricted")
        result = ep.validate_acquisitions([value])
        assert result["accepted"] == 0
        assert result["rejected"] == 1
        assert result["blocked"] is True

    def test_unknown_field_reported(self):
        value = make_value(hardware_name="A", field="nope")
        result = ep.validate_acquisitions([value])
        assert result["accepted"] == 0
        assert result["rejected"] == 1


# ---------------------------------------------------------------------------
# import_dev (file-backed dev DB only)
# ---------------------------------------------------------------------------


class TestImportDev:
    def _make_dev_db(self, tmp_path: Path, seed_gpu=True):
        db = tmp_path / "dev.db"
        engine = create_engine(f"sqlite:///{db}",
                               connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=engine)
        sf = sessionmaker(bind=engine)
        if seed_gpu:
            with sf() as session:
                hw = Hardware(name="NVIDIA RTX 4090", manufacturer="NVIDIA",
                              type="GPU", segment="desktop")
                session.add(hw)
                session.commit()
        return db, sf

    def test_rejects_production_db_path(self, tmp_path):
        with pytest.raises(ValueError):
            ep.import_dev("data/spectra.db", [make_value()])

    def test_import_is_idempotent(self, tmp_path):
        db, sf = self._make_dev_db(tmp_path)
        values = [make_value(unit="W", hardware_name="NVIDIA RTX 4090", field="tdp_w")]
        first = ep.import_dev(str(db), values)
        second = ep.import_dev(str(db), values)
        assert first["applied"] == 1
        assert second["applied"] == 0  # idempotent re-run
        with sf() as session:
            gpu = session.scalars(select(GPUSpecification)).all()
            assert len(gpu) == 1
            prov = session.scalars(select(FieldProvenance)).all()
            assert len(prov) == 1

    def test_import_adds_provenance_for_applied_field(self, tmp_path):
        db, sf = self._make_dev_db(tmp_path)
        values = [make_value(field="tdp_w", unit="W")]
        res = ep.import_dev(str(db), values)
        assert res["applied"] == 1
        with sf() as session:
            prov = session.scalars(select(FieldProvenance)).one()
            assert prov.field_name == "tdp_w"
            assert prov.table_name == "gpu_specifications"
            assert prov.evidence_status == "verified"

    def test_rollback_dev_restores_baseline(self, tmp_path):
        db, sf = self._make_dev_db(tmp_path)
        baseline = tmp_path / "baseline.db"
        # snapshot the pristine dev db
        import shutil
        shutil.copyfile(db, baseline)
        values = [make_value(field="tdp_w", unit="W")]
        ep.import_dev(str(db), values)
        with sf() as session:
            assert len(session.scalars(select(GPUSpecification)).all()) == 1
        res = ep.rollback_dev(str(db), str(baseline))
        assert res["status"] == "rolled-back"
        with sf() as session:
            assert len(session.scalars(select(GPUSpecification)).all()) == 0
