"""Tests for the additive Batch 015 ``sources`` migration and metadata seed.

Exercises the upgrade against a deliberately old ``sources`` table (the
pre-Batch-015 shape), proves it is additive and idempotent, and proves the
metadata seed is fill-only — it never overwrites a value and never creates,
deletes or renames a source.
"""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.migrations.add_source_license_metadata import (
    _ADDED_COLUMNS,
    existing_columns,
    upgrade_sources,
)
from backend.app.source_registry import SOURCE_METADATA, seed_source_metadata


def _create_legacy_sources_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE sources ("
            " id INTEGER PRIMARY KEY,"
            " name VARCHAR(200) NOT NULL,"
            " url VARCHAR(500) NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sources (id, name, url) VALUES (?, ?, ?)",
            (5, SOURCE_METADATA[5]["name"], "https://en.wikipedia.org/"),
        )
        connection.execute(
            "INSERT INTO sources (id, name, url) VALUES (?, ?, ?)",
            (7, "Unrelated legacy source", "https://legacy.test"),
        )
        connection.commit()
    finally:
        connection.close()


def test_upgrade_is_additive_and_preserves_rows(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_sources_db(db_path)

    added = upgrade_sources(db_path)

    assert set(added) == {name for name, _ in _ADDED_COLUMNS}
    columns = set(existing_columns(db_path))
    assert {name for name, _ in _ADDED_COLUMNS} <= columns

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT id, name, url FROM sources ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [
        (5, SOURCE_METADATA[5]["name"], "https://en.wikipedia.org/"),
        (7, "Unrelated legacy source", "https://legacy.test"),
    ]


def test_upgrade_is_idempotent(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_sources_db(db_path)

    upgrade_sources(db_path)

    assert upgrade_sources(db_path) == []


def test_seed_is_fill_only_and_never_overwrites(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_sources_db(db_path)
    upgrade_sources(db_path)

    # Pre-set one column on one row; the seed must leave it untouched.
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "UPDATE sources SET publisher = 'Pre-existing publisher' WHERE id = 5"
        )
        connection.commit()
    finally:
        connection.close()

    engine = create_engine("sqlite:///" + str(db_path).replace("\\", "/"))
    try:
        with Session(engine) as session:
            report = seed_source_metadata(session)
            # id 7 exists but its name does not match any register entry.
            assert report["unmatched"] == [7]
    finally:
        engine.dispose()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        row5 = connection.execute(
            "SELECT * FROM sources WHERE id = 5"
        ).fetchone()
        row7 = connection.execute(
            "SELECT * FROM sources WHERE id = 7"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    finally:
        connection.close()

    # Non-NULL value preserved; NULL fields filled from the register.
    assert row5["publisher"] == "Pre-existing publisher"
    assert row5["license_name"] == "CC BY-SA 4.0"
    assert row5["license_status"] == "clear"
    # A row that is not in the register is reported, not invented.
    assert row7["publisher"] is None
    assert row7["license_status"] is None
    assert count == 2
