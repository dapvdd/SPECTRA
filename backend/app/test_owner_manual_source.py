"""Tests for the owner-manual source registration (M1 Task 2 Step 5).

Contract: ``ensure_owner_manual_source`` registers the owner-manual source
exactly once — calling twice yields one row with license_status="clear".

Uses an isolated on-disk engine (the functions under test take an optional
session factory; no live DB is touched).
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Source
from backend.app.seed_sources import (
    OWNER_MANUAL_SOURCE,
    ensure_owner_manual_source,
)


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    yield factory
    engine.dispose()


class TestOwnerManualSource:
    def test_creates_owner_manual_source(self, session_factory):
        ensure_owner_manual_source(session_factory)

        with session_factory() as session:
            row = session.scalar(
                select(Source).where(
                    Source.name == OWNER_MANUAL_SOURCE["name"]
                )
            )
        assert row is not None
        assert row.license_status == "clear"
        assert row.url

    def test_idempotent_second_call_yields_one_row(self, session_factory):
        ensure_owner_manual_source(session_factory)
        ensure_owner_manual_source(session_factory)

        with session_factory() as session:
            rows = session.scalars(
                select(Source).where(
                    Source.name == OWNER_MANUAL_SOURCE["name"]
                )
            ).all()
        assert len(rows) == 1
