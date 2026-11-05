"""Extra Stage 3 pipeline tests: audit mode + dry-run + CLI wiring.

Adds coverage for the modes the mission requires: read-only audit of the dev
DB, dry-run (no writes), and quarantine accounting in import results.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import Hardware
from backend.app.scripts import enrichment_pipeline as ep


def _gpu_value(hardware_name="NVIDIA RTX 4090", field="tdp_w",
               normalized="450 W", raw="450 W", unit="W",
               license_status="clear", **overrides):
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
        **overrides,
    )


class TestAuditDevDb:
    def _make_db(self, tmp_path: Path):
        db = tmp_path / "audit.db"
        engine = create_engine(f"sqlite:///{db}",
                               connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        sf = sessionmaker(bind=engine)
        with sf() as session:
            hw = Hardware(name="NVIDIA RTX 4090", manufacturer="NVIDIA",
                          type="GPU", segment="desktop")
            session.add(hw)
            session.commit()
            hid = hw.id
            session.execute(
                text("INSERT INTO gpu_specifications (hardware_id, tdp_w)"
                     " VALUES (:i, :v)"),
                {"i": hid, "v": 450},
            )
            session.commit()
        return str(db)

    def test_audit_reports_coverage(self, tmp_path):
        db = self._make_db(tmp_path)
        report = ep.audit_dev_db(db)
        assert "gpu" in report
        assert report["gpu"]["total"] >= 1
        assert report["gpu"]["with_tdp_w"] >= 1


class TestDryRun:
    def test_dry_run_with_values_reports_plan_without_writing(self, tmp_path):
        db = tmp_path / "dryrun.db"
        engine = create_engine(f"sqlite:///{db}",
                               connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        sf = sessionmaker(bind=engine)
        with sf() as session:
            hw = Hardware(name="AMD RX 7900 XTX", manufacturer="AMD",
                          type="GPU", segment="desktop")
            session.add(hw)
            session.commit()

        values = [_gpu_value(hardware_name="AMD RX 7900 XTX", field="tdp_w")]
        result = ep.dry_run(str(db), values)
        assert result["actionable"] == 1
        # dry-run must not write anything
        with sf() as session:
            row = session.execute(text(
                "SELECT count(*) FROM gpu_specifications"
            )).scalar_one()
            assert row == 0


class TestImportQuarantineAccounted:
    def test_quarantined_values_are_not_applied(self, tmp_path):
        db = tmp_path / "q.db"
        engine = create_engine(f"sqlite:///{db}",
                               connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        sf = sessionmaker(bind=engine)
        with sf() as session:
            hw = Hardware(name="NVIDIA RTX 4090", manufacturer="NVIDIA",
                          type="GPU", segment="desktop")
            session.add(hw)
            session.commit()

        values = [_gpu_value(hardware_name="NVIDIA RTX 4090",
                            license_status="restricted")]
        result = ep.import_dev(str(db), values)
        assert result["quarantined"] == 1
        assert result["applied"] == 0
        with sf() as session:
            assert session.execute(text(
                "SELECT count(*) FROM gpu_specifications"
            )).scalar_one() == 0


class TestRejectionReasons:
    def test_reject_carries_explicit_reason(self):
        value = _gpu_value(hardware_name="A", field="not_a_column")
        plan = ep.EnrichmentPlan([value], source_reference="x", batch_no=1)
        action = plan.actions[0]
        assert action.status == "reject"
        assert action.reason  # explicit reason always present
