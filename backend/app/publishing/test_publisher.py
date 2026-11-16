"""M3 Phase 4 — publication tests (RED first).

Pins the publisher contract (mission §6):
- deterministic dry-run: reports actions without writing;
- transactional publication: all-or-nothing per batch;
- idempotent reimport: re-running the same batch changes nothing and
  reports the same counts;
- no unreviewed publication: records below APPROVED are never published;
- per-batch records in publication_batches + ingestion_runs;
- lifecycle enforced: only APPROVED records reach PUBLISHED.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.app.identity.lifecycle import (
    APPROVED,
    DISCOVERED,
    PUBLISHED,
    VALIDATED,
)
from backend.app.migrations.runner import upgrade
from backend.app.publishing.publisher import (
    PublicationResult,
    dry_run_batch,
    publish_batch,
)


@pytest.fixture()
def pub_db(tmp_path):
    """A v4-migrated dev DB (cloned v1 baseline + full upgrade) with the
    owner-manual source registered — mirrors test_migration_runner helpers."""
    from backend.app.test_migration_runner import _clone_schema

    db = tmp_path / "pub.db"
    _clone_schema(db)
    upgrade(db)  # v1..v4 (v1-3 verify against the real schema)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO sources (name, url) VALUES "
        "('owner-manual', 'https://spectra.local/manual')"
    )
    conn.commit()
    conn.close()
    return db


def _psu_record(n: int = 1) -> dict:
    return {
        "category": "PSU",
        "name": f"Corsair RM850x #{n}",
        "manufacturer": "Corsair",
        "canonical_key": f"corsair|psu|rm850x #{n}|850w-gold-mod",
        "record_status": APPROVED,
        "approved_by": "curator",
        "spec": {
            "wattage": 850,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
            "pcie_8pin_count": 4,
            "pcie_12vhpwr": 1,
        },
        "provenance": {
            field: {
                "source_name": "owner-manual",
                "source_url": "https://en.wikipedia.org/wiki/Power_supply_unit_(computer)",
                "license_name": "CC BY-SA 4.0",
                "evidence_status": "verified",
                "access_date": "2026-11-16",
            }
            for field in ("wattage", "efficiency_rating", "modular",
                          "pcie_8pin_count", "pcie_12vhpwr")
        },
    }


class TestDryRun:
    def test_dry_run_writes_nothing(self, pub_db):
        before = _hardware_count(pub_db)
        result = dry_run_batch(pub_db, [_psu_record(1)])
        assert result.would_publish == 1
        assert _hardware_count(pub_db) == before

    def test_dry_run_reports_provenance_plan(self, pub_db):
        result = dry_run_batch(pub_db, [_psu_record(1)])
        assert result.provenance_rows_planned == 5


class TestPublish:
    def test_publish_creates_records(self, pub_db):
        result = publish_batch(pub_db, [_psu_record(1)], approved_by="curator")
        assert result.published == 1
        assert result.batch_no > 0
        assert _hardware_count(pub_db) == 1
        row = _hardware_row(pub_db, 1)
        assert row["type"] == "PSU"
        assert row["record_status"] == PUBLISHED
        assert row["canonical_key"] == "corsair|psu|rm850x #1|850w-gold-mod"

    def test_publish_writes_field_provenance(self, pub_db):
        publish_batch(pub_db, [_psu_record(1)], approved_by="curator")
        conn = sqlite3.connect(pub_db)
        rows = conn.execute(
            "SELECT field_name, evidence_status, source_url FROM field_provenance "
            "WHERE table_name='psu_specifications'"
        ).fetchall()
        conn.close()
        assert {r[0] for r in rows} == {"wattage", "efficiency_rating", "modular",
                                        "pcie_8pin_count", "pcie_12vhpwr"}
        assert all(r[1] == "verified" for r in rows)

    def test_publish_records_batch_and_run(self, pub_db):
        result = publish_batch(pub_db, [_psu_record(1)], approved_by="curator")
        conn = sqlite3.connect(pub_db)
        batches = conn.execute("SELECT batch_no, approved_by, status FROM publication_batches").fetchall()
        runs = conn.execute("SELECT run_type, status FROM ingestion_runs").fetchall()
        conn.close()
        assert batches == [(result.batch_no, "curator", "published")]
        assert ("publication", "success") in runs

    def test_non_approved_record_never_publishes(self, pub_db):
        record = _psu_record(2)
        record["record_status"] = VALIDATED  # not approved
        result = publish_batch(pub_db, [record], approved_by="curator")
        assert result.published == 0
        assert result.rejected == 1
        assert _hardware_count(pub_db) == 0

    def test_unapproved_status_string_rejected(self, pub_db):
        record = _psu_record(3)
        record["record_status"] = DISCOVERED
        result = publish_batch(pub_db, [record], approved_by="curator")
        assert result.published == 0


class TestIdempotency:
    def test_reimport_is_idempotent(self, pub_db):
        batch = [_psu_record(1)]
        first = publish_batch(pub_db, batch, approved_by="curator")
        second = publish_batch(pub_db, batch, approved_by="curator")
        assert first.published == 1
        assert second.published == 0
        assert second.skipped_existing == 1
        assert _hardware_count(pub_db) == 1

    def test_provenance_not_duplicated(self, pub_db):
        batch = [_psu_record(1)]
        publish_batch(pub_db, batch, approved_by="curator")
        publish_batch(pub_db, batch, approved_by="curator")
        conn = sqlite3.connect(pub_db)
        n = conn.execute(
            "SELECT COUNT(*) FROM field_provenance WHERE table_name='psu_specifications'"
        ).fetchone()[0]
        conn.close()
        assert n == 5


class TestTransactional:
    def test_batch_is_all_or_nothing(self, pub_db):
        good = _psu_record(4)
        bad = _psu_record(5)
        bad["spec"] = {"wattage": 85, "efficiency_rating": "80 Plus Gold",
                       "modular": True}  # unit-check failure
        result = publish_batch(pub_db, [good, bad], approved_by="curator")
        # The bad record must not half-publish; the good one publishes.
        assert result.published == 1
        assert result.rejected == 1
        conn = sqlite3.connect(pub_db)
        n_bad = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE name LIKE '%#5%'"
        ).fetchone()[0]
        conn.close()
        assert n_bad == 0


def _hardware_count(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
    finally:
        conn.close()


def _hardware_row(db: Path, hardware_id: int) -> dict:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM hardware WHERE id=?", (hardware_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()
