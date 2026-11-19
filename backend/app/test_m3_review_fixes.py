"""M3 Phase 10 — review-driven regression fixes (RED first).

Pins the fixes for the independent-review findings:

1. Critical: publisher silently skipped provenance when the source_name was
   not registered (INSERT..SELECT matched 0 rows). Fail-closed now: an
   unregistered source aborts the batch with an explicit error.
2. High: publisher prod-path refusal was case-sensitive; on Windows/macOS
   `DATA/SPECTRA.DB` would open the production DB. Now case-insensitive and
   realpath-aware.
3. High: migration runner CLI defaulted --database to data/spectra.db and
   never refused it. The prod-named path is now refused on the write paths
   (upgrade/downgrade), matching the publisher/ingest guard.
4. High: v4 declared reversible=False but downgrade() checked only
   `downgrade is None`, so `--target 3` executed a partial downgrade that
   leaves five un-droppable columns and bricks re-upgrade. downgrade() now
   honors the reversible flag (blocked with a precise reason).
5. Medium: detect_conflicts keyed values by source_name, so two records from
   the SAME source with differing facts collided in the dict and the
   conflict was silently missed. Values are now positional per record.
6. Medium: canonical_key truncation could collapse distinct SKUs; truncation
   now keeps a deterministic uniqueness suffix when the 300-char cap is hit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.app.identity.canonical import canonical_key
from backend.app.identity.lifecycle import APPROVED
from backend.app.importers.m3_validation import detect_conflicts
from backend.app.migrations.runner import downgrade, upgrade


# ---------------------------------------------------------------------------
# 1. Critical: unregistered source must abort the batch, never skip silently
# ---------------------------------------------------------------------------


@pytest.fixture()
def pub_db(tmp_path):
    from backend.app.test_migration_runner import _clone_schema

    db = tmp_path / "fix_pub.db"
    _clone_schema(db)
    upgrade(db)
    # Register only ONE source; the bad record will cite a different one.
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO sources (name, url) VALUES "
        "('owner-manual', 'https://spectra.local/manual')"
    )
    conn.commit()
    conn.close()
    return db


def _psu_record(n: int, source_name: str = "owner-manual") -> dict:
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
                "source_name": source_name,
                # Per-SKU URL (/p/ + mpn segment): passes the SKU evidence
                # gate for 'verified' claims. Wikipedia = technology facts
                # only, never SKU specs (M3 remediation contract).
                "source_url": "https://www.corsair.com/us/en/p/"
                              "psu/cp-9020200-na/rmx-series-rm850x",
                "license_name": "CC BY-SA 4.0",
                "evidence_status": "verified",
                "access_date": "2026-11-16",
                # Layer 3: auditable curator assertion (M3 merge-gate)
                "source_reference": "Tech Specs > " + field,
                "match_method": "spec-table-row",
            }
            for field in ("wattage", "efficiency_rating", "modular",
                          "pcie_8pin_count", "pcie_12vhpwr")
        },
        "mpn": f"CP-9020200-NA-{n}",
    }


def test_unregistered_source_aborts_batch(pub_db):
    from backend.app.publishing.publisher import publish_batch

    unregistered = _psu_record(1, source_name="ghost-source")
    good = _psu_record(2)

    with pytest.raises(Exception) as excinfo:
        publish_batch(pub_db, [good, unregistered],
                      approved_by="review-fix")

    # The failure must NAME the unregistered source (diagnosable fail-closed).
    message = str(excinfo.value)
    assert "ghost-source" in message

    # Nothing was published: the transaction is all-or-nothing.
    conn = sqlite3.connect(pub_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM hardware WHERE name LIKE 'Corsair RM850x%'"
    ).fetchone()[0]
    conn.close()
    assert count == 0


def test_registered_source_still_publishes(pub_db):
    from backend.app.publishing.publisher import publish_batch

    result = publish_batch(pub_db, [_psu_record(1)],
                           approved_by="review-fix")
    assert result.published == 1


# ---------------------------------------------------------------------------
# 2. High: prod-path refusal must be case-insensitive
# ---------------------------------------------------------------------------


def test_publisher_refuses_prod_path_case_insensitive(tmp_path):
    from backend.app.publishing.publisher import _check_db_path

    for hostile in (
        "data/SPECTRA.DB",
        "DATA/spectra.db",
        r"repo\DATA\SPECTRA.db",
        "data/spectra.db",
    ):
        with pytest.raises(ValueError, match="refuses production path"):
            _check_db_path(hostile)


def test_publisher_still_accepts_dev_paths(tmp_path):
    from backend.app.publishing.publisher import _check_db_path

    dev = tmp_path / "dev_catalog.db"
    dev.touch()
    assert _check_db_path(dev) == dev


# ---------------------------------------------------------------------------
# 3. High: migration runner refuses the production-named path
# ---------------------------------------------------------------------------


def test_migration_runner_refuses_prod_path(tmp_path):
    from backend.app.migrations.runner import _ensure_not_prod_path

    prod = tmp_path / "data" / "spectra.db"
    prod.parent.mkdir(parents=True, exist_ok=True)
    prod.touch()
    with pytest.raises(RuntimeError, match="production"):
        _ensure_not_prod_path(prod)


def test_migration_upgrade_refuses_prod_path(tmp_path):
    from backend.app.migrations.runner import upgrade

    prod = tmp_path / "data" / "spectra.db"
    prod.parent.mkdir(parents=True, exist_ok=True)
    prod.write_bytes(b"")
    with pytest.raises(RuntimeError, match="production"):
        upgrade(prod)


# ---------------------------------------------------------------------------
# 4. High: non-reversible migrations are never partially downgraded
# ---------------------------------------------------------------------------


def test_downgrade_blocks_partial_v4_revert(tmp_path):
    from backend.app.test_migration_runner import _clone_schema

    db = tmp_path / "partial.db"
    _clone_schema(db)
    upgrade(db)

    result = downgrade(db, target_version=3)

    # v4 is not reversible: the request is refused, nothing changes.
    assert result["status"] == "blocked"
    assert "not reversible" in result["reason"]


def test_downgrade_still_works_for_reversible_v2(tmp_path):
    from backend.app.test_migration_runner import _clone_schema

    db = tmp_path / "rev.db"
    _clone_schema(db)
    # Upgrade to v2 only (v4 is not reversible and would block 1..4 targets;
    # v2 exercises the reversible path this test pins).
    from backend.app.migrations.runner import MIGRATIONS

    from backend.app.migrations import runner as runner_module

    db_url = f"sqlite:///{db.as_posix()}"
    import sqlite3 as _sq

    conn = _sq.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    runner_module._ensure_schema_version(conn)
    for migration in MIGRATIONS:
        if migration.version > 2:
            break
        for statement in migration.statements:
            conn.execute(statement)
        if migration.verify is not None:
            migration.verify(conn)
        runner_module._record_version(conn, migration.version)
    conn.commit()
    conn.close()

    result = downgrade(db, target_version=1)
    assert result["status"] == "downgraded"
    assert result["to_version"] == 1


# ---------------------------------------------------------------------------
# 5. Medium: same-source conflicting values are detected
# ---------------------------------------------------------------------------


def test_same_source_conflicting_values_detected():
    records = [
        {"canonical_key": "k|ram|kit|32", "_type": "RAM",
         "source_name": "S", "capacity_gb": 16},
        {"canonical_key": "k|ram|kit|32", "_type": "RAM",
         "source_name": "S", "capacity_gb": 32},
    ]
    conflicts = detect_conflicts(records)
    assert len(conflicts) == 1
    assert conflicts[0].field == "capacity_gb"


def test_different_source_conflicts_still_detected():
    records = [
        {"canonical_key": "k|ram|kit|32", "_type": "RAM",
         "source_name": "A", "capacity_gb": 16},
        {"canonical_key": "k|ram|kit|32", "_type": "RAM",
         "source_name": "B", "capacity_gb": 32},
    ]
    conflicts = detect_conflicts(records)
    assert len(conflicts) == 1


# ---------------------------------------------------------------------------
# 6. Medium: canonical_key truncation keeps distinct SKUs distinct
# ---------------------------------------------------------------------------


def test_long_components_do_not_collapse_distinct_skus():
    # 150 (manufacturer) + 1 + 3 + 1 + 150 (model) = 305 > 300: the variant
    # is cut off entirely by naive truncation, merging two distinct SKUs
    # (the scope-1 review probe). The fix must keep them distinct.
    manufacturer = "m" * 150
    model = "f" * 150
    key_a = canonical_key(manufacturer, "RAM", model, "aaa")
    key_b = canonical_key(manufacturer, "RAM", model, "bbb")
    # Truncation must not silently merge two different variants.
    assert key_a != key_b
    assert len(key_a) <= 300 and len(key_b) <= 300
