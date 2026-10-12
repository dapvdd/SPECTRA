"""Batch 014 tests: modern CPU catalog ingestion and matching logic.

Batch 014 is a data-ingestion batch (new hardware records sourced from English
Wikipedia). It introduces two new pieces of ingestion/matching logic in
``data/research/batch014``:

* ``build_candidates.py`` -- deterministic extraction of processor rows from
  wikitext tables, value normalisation and candidate validation;
* ``apply_batch014.py`` -- the guarded, insert-only, idempotent loader.

These tests exercise the pure extraction helpers, the invariants of the
generated candidate inventory, and the loader against a disposable SQLite
database created from the ORM metadata (never the live database).

The tests skip (rather than fail) when the batch research artifacts are not
present in the checkout.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import CPUSpecification, Hardware, Source

BATCH_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "batch014"
CANDIDATES_FILE = BATCH_DIR / "_candidates.json"


def _load_module(module_name: str):
    path = BATCH_DIR / (module_name + ".py")
    if not path.exists():
        pytest.skip("batch014 research script not present: %s" % path)
    spec = importlib.util.spec_from_file_location("batch014_" + module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_mod():
    return _load_module("build_candidates")


@pytest.fixture(scope="module")
def apply_mod():
    return _load_module("apply_batch014")


@pytest.fixture(scope="module")
def candidates():
    if not CANDIDATES_FILE.exists():
        pytest.skip("batch014 candidate inventory not present")
    with CANDIDATES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# extraction / normalisation helpers
# --------------------------------------------------------------------------- #

class TestExtractionHelpers:
    def test_core_threads(self, build_mod):
        assert build_mod.core_threads("8 (16)") == (8, 16)
        assert build_mod.core_threads("4 (4)") == (4, 4)
        assert build_mod.core_threads("n/a") == (None, None)

    def test_sum_core_threads_combines_big_and_small_cores(self, build_mod):
        assert build_mod.sum_core_threads("8 (16)", "16 (16)") == (24, 32)
        assert build_mod.sum_core_threads("6 (12)", "8 (8)", "2 (2)") == (16, 22)
        assert build_mod.sum_core_threads("x", "y") == (None, None)

    def test_tdp_uses_default_power_not_configurable_ceiling(self, build_mod):
        assert build_mod.tdp("125 W") == 125.0
        assert build_mod.tdp("55\u201375W") == 55.0
        assert build_mod.tdp("28 W (15\u221254 W)") == 28.0

    def test_max_float_picks_highest_turbo_column(self, build_mod):
        assert build_mod.max_float("5.7", "4.5", "5.9", "6.2") == 6.2
        assert build_mod.max_float("", "") is None

    def test_parse_release_dates(self, build_mod):
        assert build_mod.parse_release("2023-October-17") == "2023-10-17"
        assert build_mod.parse_release("2025-04-23") == "2025-04-23"
        assert build_mod.parse_release("Oct 24, 2024") == "2024-10-24"
        # "(PRO launch) retail launch" -> the retail (unparenthesised) date
        assert build_mod.parse_release(
            "(March 27, 2025) February 18, 2025") == "2025-02-18"

    def test_parse_release_never_invents_a_date(self, build_mod):
        # quarter, month-only and empty cells must never be turned into a date
        assert build_mod.parse_release("Q4'23") is None
        assert build_mod.parse_release("Aug, 2025") is None
        assert build_mod.parse_release("") is None
        assert build_mod.parse_release(None) is None

    def test_amd_model_clean(self, build_mod):
        assert build_mod.amd_model_clean("8700G") == "8700G"
        assert build_mod.amd_model_clean("PRO 8700GE") == "PRO 8700GE"
        # an annotation appended after a <br/> is dropped; the model token is kept
        assert build_mod.amd_model_clean("9950X3D2 Dual Edition") == "9950X3D2"
        assert build_mod.amd_model_clean("9800X3D Model also available") == "9800X3D"

    def test_valid_candidate_rejects_impossible_values(self, build_mod):
        good = {"name": "AMD Ryzen 9 9950X", "cores": 16, "threads": 32,
                "base_clock_ghz": 4.3, "boost_clock_ghz": 5.7, "tdp_w": 170.0}
        assert build_mod.valid_candidate(good) == []
        bad = dict(good, boost_clock_ghz=1.0)  # boost below base
        assert "boost_clock" in build_mod.valid_candidate(bad)


# --------------------------------------------------------------------------- #
# candidate inventory invariants
# --------------------------------------------------------------------------- #

class TestCandidateInventory:
    EXPECTED_TABLES = {
        "intel_rpl_refresh_desktop", "intel_mtl_h", "intel_mtl_u",
        "intel_mtl_hl", "intel_mtl_ul", "intel_arl_s", "intel_arl_u",
        "intel_arl_h", "intel_arl_hx", "intel_lnl",
        "amd_ryzen_9000_desktop", "amd_ryzen_8000g_desktop",
        "amd_ryzen_8000_f_desktop", "amd_ryzen_8040_mobile",
        "amd_ryzen_8045_mobile", "amd_ryzen_ai_300_mobile",
    }

    def test_candidates_have_unique_canonical_names(self, candidates):
        names = [c["name"].lower() for c in candidates["candidates"]]
        assert len(names) == len(set(names))

    def test_every_family_has_candidates(self, candidates):
        tables = {c["table"] for c in candidates["candidates"]}
        assert self.EXPECTED_TABLES <= tables

    def test_all_values_are_physically_plausible(self, candidates):
        for c in candidates["candidates"]:
            assert 1 <= c["cores"] <= 128, c
            assert 1 <= c["threads"] <= 256, c
            assert 0.5 <= c["base_clock_ghz"] <= 6.5, c
            assert c["base_clock_ghz"] <= c["boost_clock_ghz"] <= 7.0, c
            assert 5 <= c["tdp_w"] <= 500, c

    def test_every_candidate_carries_provenance_metadata(self, candidates):
        for c in candidates["candidates"]:
            assert c["source_url"].startswith("https://en.wikipedia.org/"), c
            assert c["source_section"], c
            assert c["confidence"] in {"high", "medium", "low"}, c

    def test_core_thread_consistency(self, candidates):
        for c in candidates["candidates"]:
            # SMT/hyperthreading never yields fewer threads than cores
            assert c["threads"] >= c["cores"], c

    def test_ai_300_pro_annotations_are_resolved(self, candidates):
        for c in candidates["candidates"]:
            assert "(PRO)" not in c["name"], c
        names = {c["name"] for c in candidates["candidates"]}
        assert "AMD Ryzen AI 9 HX 375" in names
        assert "AMD Ryzen AI 7 PRO 360" in names


# --------------------------------------------------------------------------- #
# guarded loader integration (disposable database only)
# --------------------------------------------------------------------------- #

def _temp_database(tmp_path):
    db_path = tmp_path / "batch014_test.db"
    engine = create_engine("sqlite:///" + str(db_path).replace("\\", "/"))

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    return engine, str(engine.url.database)


class TestGuardedApply:
    def _expected_provenance(self, apply_mod, cand):
        expected = ["architecture"]
        if cand["release_date"]:
            expected.append("release_date")
        expected += [f for f in apply_mod.SPEC_FIELDS if cand.get(f) is not None]
        return expected

    def test_insert_is_additive_idempotent_and_provenanced(
            self, apply_mod, candidates, tmp_path, monkeypatch):
        monkeypatch.setattr(apply_mod, "BACKUP_DIR", str(tmp_path / "backups"))
        engine, db_path = _temp_database(tmp_path)
        with sessionmaker(bind=engine)() as session:
            session.add(Source(id=5, name="Wikipedia (English)",
                               url="https://en.wikipedia.org/"))
            session.commit()
        engine.dispose()

        cands = candidates["candidates"]
        result = apply_mod.apply(db_path=db_path, do_apply=True, expect=len(cands))
        assert result["inserted"] == len(cands)
        assert result["after"] - result["before"] == len(cands)

        expected_prov = sum(len(self._expected_provenance(apply_mod, c)) for c in cands)

        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        # exactly one spec row per new hardware record, no duplicate names
        assert con.execute("SELECT COUNT(*) FROM hardware").fetchone()[0] == len(cands)
        assert con.execute("SELECT COUNT(*) FROM cpu_specifications").fetchone()[0] == len(cands)
        dups = con.execute(
            "SELECT lower(name) FROM hardware GROUP BY lower(name) HAVING COUNT(*)>1"
        ).fetchall()
        assert dups == []
        assert con.execute(
            "SELECT COUNT(*) FROM field_provenance WHERE batch_no=14").fetchone()[0] == expected_prov
        # provenance is attributed to the Wikipedia source with a verified status
        assert con.execute(
            "SELECT COUNT(*) FROM field_provenance WHERE batch_no=14 "
            "AND source_id=5 AND evidence_status='verified' AND license_name='CC BY-SA 4.0'"
        ).fetchone()[0] == expected_prov
        con.close()

        # Re-running the loader on the same database must be a no-op.
        again = apply_mod.apply(db_path=db_path, do_apply=True, expect=0)
        assert again["inserted"] == 0
        con = sqlite3.connect(db_path)
        assert con.execute("SELECT COUNT(*) FROM hardware").fetchone()[0] == len(cands)
        assert con.execute("SELECT COUNT(*) FROM field_provenance").fetchone()[0] == expected_prov
        con.close()

    def test_existing_record_is_matched_case_insensitively_and_never_overwritten(
            self, apply_mod, candidates, tmp_path, monkeypatch):
        monkeypatch.setattr(apply_mod, "BACKUP_DIR", str(tmp_path / "backups"))
        engine, db_path = _temp_database(tmp_path)
        target = candidates["candidates"][0]
        with sessionmaker(bind=engine)() as session:
            session.add(Source(id=5, name="Wikipedia (English)",
                               url="https://en.wikipedia.org/"))
            hw = Hardware(name=target["name"].upper(),
                          manufacturer=target["manufacturer"], type="CPU")
            hw.cpu_specification = CPUSpecification(
                cores=2, threads=2, base_clock_ghz=1.0, boost_clock_ghz=1.1,
                tdp_w=1.0, socket="ORIGINAL")
            session.add(hw)
            session.commit()
            original_id = hw.id
        engine.dispose()

        cands = candidates["candidates"]
        result = apply_mod.apply(db_path=db_path, do_apply=True, expect=len(cands) - 1)
        assert result["inserted"] == len(cands) - 1

        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM cpu_specifications WHERE hardware_id=?",
                          (original_id,)).fetchone()
        # the pre-existing row is untouched (NULL-only / insert-only guarantee)
        assert (row["cores"], row["threads"], row["base_clock_ghz"],
                row["boost_clock_ghz"], row["tdp_w"], row["socket"]) == \
            (2, 2, 1.0, 1.1, 1.0, "ORIGINAL")
        assert con.execute(
            "SELECT COUNT(*) FROM field_provenance WHERE hardware_id=?",
            (original_id,)).fetchone()[0] == 0
        con.close()
