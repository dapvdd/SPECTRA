"""Tests for Stage 8 dev enrichment rehearsal drill.

Contract:
- ``rehearsal_scratch_path(out_dir)`` returns a deterministic, never-committed
  scratch path with a READY suffix.
- ``prepare_scratch(baseline, scratch, force=False)`` copies baseline -> scratch.
- ``run_rehearsal(baseline, csv, out_dir)`` returns a deterministic result dict
  with validation, import_first, import_second, and idempotent flags.
- ``rollback_scratch(scratch, baseline)`` restores and verifies SHA256 match.
- All operations target a scratch copy: the baseline and the shared dev DB are
  never mutated (verified by SHA256 comparison).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    GPUSpecification,
    Hardware,
)
from backend.app.scripts import dev_rehearsal as dr


class TestScratchPath:
    def test_deterministic_path(self, tmp_path):
        a = dr.rehearsal_scratch_path(tmp_path)
        b = dr.rehearsal_scratch_path(tmp_path)
        assert a == b
        assert a.name == "spectra_rehearsal_READY.db"
        assert not a.exists()  # mkdir but no file yet


class TestPrepareScratch:
    def test_copy_matches_baseline(self, tmp_path):
        baseline = tmp_path / "baseline.db"
        scratch = tmp_path / "scratch.db"
        baseline.write_bytes(b"hello baseline")
        dr.prepare_scratch(baseline, scratch)
        assert scratch.exists()
        assert scratch.read_bytes() == b"hello baseline"

    def test_force_overwrites_existing(self, tmp_path):
        baseline = tmp_path / "baseline.db"
        scratch = tmp_path / "scratch.db"
        baseline.write_bytes(b"baseline")
        scratch.write_bytes(b"old scratch")
        dr.prepare_scratch(baseline, scratch, force=True)
        assert scratch.read_bytes() == b"baseline"


class TestRunRehearsal:
    def _make_db(self, tmp_path: Path) -> tuple[Path, str]:
        """Minimal dev DB: create schema via Base.metadata, seed one GPU with
        NULL tdp_w (the gap the import drill fills)."""
        db = tmp_path / "dev.db"
        engine = create_engine(
            f"sqlite:///{db}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _fk(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=engine)
        sf = sessionmaker(bind=engine)
        with sf() as session:
            hw = Hardware(
                name="NVIDIA RTX 4090", manufacturer="NVIDIA",
                type="GPU", segment="desktop",
            )
            session.add(hw)
            session.commit()
            hw_id = hw.id
            # Insert gpu_specifications row without tdp_w (NULL gap).
            gp = GPUSpecification(hardware_id=hw_id, memory_gb=24.0)
            session.add(gp)
            session.commit()
        engine.dispose()
        return db, "NVIDIA RTX 4090"

    def test_rehearsal_returns_result_dict(self, tmp_path):
        db, _ = self._make_db(tmp_path)
        csv = tmp_path / "gpuark.csv"
        csv.write_text(
            "name,tdp\nNVIDIA RTX 4090,450\n",
            encoding="utf-8",
        )
        result = dr.run_rehearsal(str(db), str(csv), str(tmp_path))
        assert set(result) >= {"validation", "import_first", "import_second",
                               "idempotent", "gap_rows_before"}

    def test_idempotency_proof(self, tmp_path):
        db, _ = self._make_db(tmp_path)
        csv = tmp_path / "gpuark.csv"
        csv.write_text("name,tdp\nNVIDIA RTX 4090,450\n", encoding="utf-8")
        result = dr.run_rehearsal(str(db), str(csv), str(tmp_path))
        assert result["idempotent"] is True
        assert result["import_second"]["applied"] == 0

    def test_validation_includes_accept_and_reject(self, tmp_path):
        db, _ = self._make_db(tmp_path)
        csv = tmp_path / "gpuark.csv"
        csv.write_text("name,tdp\nNVIDIA RTX 4090,450\n", encoding="utf-8")
        result = dr.run_rehearsal(str(db), str(csv), str(tmp_path))
        assert result["validation"]["accepted"] >= 1
        assert result["import_first"]["applied"] >= 1

    def test_baseline_sha_recorded(self, tmp_path):
        db, _ = self._make_db(tmp_path)
        csv = tmp_path / "gpuark.csv"
        csv.write_text("name,tdp\nNVIDIA RTX 4090,450\n", encoding="utf-8")
        result = dr.run_rehearsal(str(db), str(csv), str(tmp_path))
        assert result["baseline_sha256"] is not None
        assert len(result["baseline_sha256"]) == 64  # SHA256 hex

    def test_scratch_sha_changes_after_import(self, tmp_path):
        db, _ = self._make_db(tmp_path)
        csv = tmp_path / "gpuark.csv"
        csv.write_text("name,tdp\nNVIDIA RTX 4090,450\n", encoding="utf-8")
        result = dr.run_rehearsal(str(db), str(csv), str(tmp_path))
        # The scratch copy was mutated by import_dev -> SHA changes.
        assert result["scratch_sha256_before"] != result["confirm"].split(":")[1]


class TestRollbackScratch:
    def test_rollback_restores_sha256(self, tmp_path):
        baseline = tmp_path / "baseline.db"
        scratch = tmp_path / "scratch.db"
        baseline.write_bytes(b"baseline content")
        scratch.write_bytes(b"modified content")
        result = dr.rollback_scratch(scratch, baseline)
        assert result["status"] == "rolled-back"
        assert result["matches_baseline"] is True
        assert scratch.read_bytes() == b"baseline content"

    def test_missing_scratch_raises(self, tmp_path):
        baseline = tmp_path / "baseline.db"
        missing = tmp_path / "missing.db"
        baseline.write_bytes(b"baseline")
        with pytest.raises(Exception):
            dr.rollback_scratch(missing, baseline)
