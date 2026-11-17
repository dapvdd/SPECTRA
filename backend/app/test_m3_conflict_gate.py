"""M3 Phase 10b — conflict gate wired into publication (RED first).

Review scope 2 finding (High): `detect_conflicts` existed but was never
called by `publish_batch` — `conflict_free=True` was hardcoded, so two
individually-valid records with the SAME canonical_key but differing facts
would both publish (the second skipped as existing, the first published
with whichever values arrived first). The gate is now wired: intra-batch
conflicts reject ALL involved records with a named-reason; conflicting
against an already-published record rejects the incoming one.

Review scope 3 finding (Low #7): dry-run counted provenance rows without
checking the sources registry, overstating success relative to apply-time
behavior when a source is unregistered. Dry-run now rejects records whose
cited sources are missing from the registry, mirroring apply.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.app.identity.lifecycle import APPROVED
from backend.app.migrations.runner import upgrade


@pytest.fixture()
def pub_db(tmp_path):
    from backend.app.test_migration_runner import _clone_schema

    db = tmp_path / "gate_pub.db"
    _clone_schema(db)
    upgrade(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO sources (name, url) VALUES "
        "('owner-manual', 'https://spectra.local/manual')"
    )
    conn.commit()
    conn.close()
    return db


def _psu_record(n: int, *, wattage=850, key_suffix="850w",
                source_name="owner-manual") -> dict:
    return {
        "category": "PSU",
        "name": f"Corsair RM850x #{n}",
        "manufacturer": "Corsair",
        "canonical_key": f"corsair|psu|rm850x|{key_suffix}",
        "record_status": APPROVED,
        "approved_by": "curator",
        "spec": {
            "wattage": wattage,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
            "pcie_8pin_count": 4,
            "pcie_12vhpwr": 1,
        },
        "provenance": {
            field: {
                "source_name": source_name,
                "source_url": "https://en.wikipedia.org/wiki/"
                              "Power_supply_unit_(computer)",
                "license_name": "CC BY-SA 4.0",
                "evidence_status": "verified",
                "access_date": "2026-11-16",
            }
            for field in ("wattage", "efficiency_rating", "modular",
                          "pcie_8pin_count", "pcie_12vhpwr")
        },
    }


def _hardware_rows(db) -> list[tuple]:
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT name, canonical_key FROM hardware "
        "WHERE name LIKE 'Corsair RM850x%'"
    ).fetchall()
    conn.close()
    return rows


def test_intra_batch_conflict_rejects_all_involved(pub_db):
    from backend.app.publishing.publisher import publish_batch

    a = _psu_record(1, wattage=850)
    b = _psu_record(2, wattage=999)  # same canonical_key, different wattage

    result = publish_batch(pub_db, [a, b], approved_by="gate")

    assert result.published == 0
    assert result.rejected == 2
    assert any("conflict" in r.lower() for r in result.rejection_reasons)
    assert _hardware_rows(pub_db) == []


def test_conflict_against_published_record_rejects_incoming(pub_db):
    from backend.app.publishing.publisher import publish_batch

    first = publish_batch(pub_db, [_psu_record(1, wattage=850)],
                          approved_by="gate")
    assert first.published == 1

    incoming = _psu_record(3, wattage=999)
    second = publish_batch(pub_db, [incoming], approved_by="gate")

    assert second.published == 0
    assert second.rejected == 1
    assert any("conflict" in r.lower() for r in second.rejection_reasons)
    # The published record's values are untouched.
    rows = _hardware_rows(pub_db)
    assert len(rows) == 1
    assert rows[0][0] == "Corsair RM850x #1"


def test_no_conflict_between_distinct_keys(pub_db):
    from backend.app.publishing.publisher import publish_batch

    a = _psu_record(1, wattage=850, key_suffix="850w")
    b = _psu_record(2, wattage=999, key_suffix="999w")
    result = publish_batch(pub_db, [a, b], approved_by="gate")
    assert result.published == 2
    assert result.rejected == 0


def test_dry_run_rejects_records_with_unregistered_sources(pub_db):
    from backend.app.publishing.publisher import dry_run_batch

    good = _psu_record(1)
    ghost = _psu_record(2, source_name="ghost-source")

    result = dry_run_batch(pub_db, [good, ghost])

    assert result.would_publish == 1
    assert result.provenance_rows_planned == 5
    assert result.rejected == 1
    assert any("ghost-source" in r for r in result.rejection_reasons)
