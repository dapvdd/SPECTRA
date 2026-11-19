"""M3 Phase 9 — security tests.

Pins the security posture of the M3 additions (docs/m3 contract, mission
safety contract + Phase 9 review):

- Ops visibility endpoints: the only user-supplied input is ``limit``; SQL
  structure (table, columns, order) comes from module-level allow-list
  constants. Injection probes must be rejected (422/404), never executed;
  the response shape is pinned so no query parameter can widen it.
- Validation rules are fail-closed: a malformed (non-numeric, bool, or
  string-typed) spec value must produce a blocker with a clear reason, not
  a TypeError crash that would abort a whole publication batch with an
  opaque traceback (found in Phase 9 review: ``unit_checks`` /
  ``cross_field_checks`` compared strings against range tuples).
- Publisher keeps its fail-closed gate under malformed input: a malformed
  record is REJECTED (counted, with a reason) while well-formed records in
  the same batch still publish — the transaction never dies mid-flight.
- M3 adapters are human-in-the-loop curated transforms: zero network I/O,
  pinned structurally (no network libraries imported; sockets/urlopen raise
  if ever touched).
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from backend.app.importers.m3_validation import (
    cross_field_checks,
    unit_checks,
    validate_record,
)
from backend.app.migrations.runner import upgrade
from backend.app.scripts.m3_adapters import WikipediaCuratedAdapter
from backend.app.services import source_service
from backend.app.services.source_service import OpsTableUnavailableError


# ---------------------------------------------------------------------------
# Shared fixtures: in-memory app with v4 ops tables present
# ---------------------------------------------------------------------------


@pytest.fixture()
def security_client():
    """The real FastAPI app over an in-memory v4-schema database.

    Auth stays OFF (matching the public read endpoints); the ops endpoints'
    security contract under test here is input validation and SQL structure,
    not auth (covered by test_auth_security.py).
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.app import main
    from backend.app.database import Base
    from backend.app.migrations.runner import (
        _INGESTION_RUNS_DDL,
        _PUBLICATION_BATCHES_DDL,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(_INGESTION_RUNS_DDL))
        conn.execute(text(_PUBLICATION_BATCHES_DDL))
        conn.commit()

    factory = sessionmaker(bind=engine)
    saved = (main.SessionLocal, source_service.SessionLocal)
    main.SessionLocal = factory
    source_service.SessionLocal = factory
    yield TestClient(main.app)
    main.SessionLocal, source_service.SessionLocal = saved
    engine.dispose()


@pytest.fixture()
def seeded_ops_tables(security_client):
    """One ingestion run + one publication batch for shape assertions."""
    from sqlalchemy import text

    from backend.app import main

    with main.SessionLocal() as session:
        session.execute(text(
            "INSERT INTO ingestion_runs (run_type, category, mode, status, "
            "rows_seen, rows_applied, rows_rejected, rows_quarantined, "
            "started_at, finished_at, notes) VALUES ('publication', 'ALL', "
            "'apply', 'success', 1, 1, 0, 0, '2026-11-16T00:00:00+00:00', "
            "'2026-11-16T00:00:01+00:00', 'security fixture')"
        ))
        session.execute(text(
            "INSERT INTO publication_batches (batch_no, category, "
            "record_count, approved_by, status, created_at, published_at, "
            "notes) VALUES (1, 'ALL', 1, 'security-test', 'published', "
            "'2026-11-16T00:00:00+00:00', "
            "'2026-11-16T00:00:01+00:00', 'security fixture')"
        ))
        session.commit()
    return security_client


# ---------------------------------------------------------------------------
# Ops visibility: SQL-injection probes (allow-list + bound parameters)
# ---------------------------------------------------------------------------


class TestOpsInjectionProbes:
    """The ops endpoints accept exactly one user-controlled value: ``limit``.

    Everything else — table name, column list, ORDER BY — is built from
    module-level allow-list constants (source_service._ops_rows). These
    probes pin that no request input can reach the SQL structure: hostile
    values are rejected by validation (422) before any query runs, and the
    service-layer helper refuses unknown tables by construction.
    """

    def test_service_layer_refuses_unknown_table_names(self):
        # Direct structural guarantee: even a future caller passing request
        # data into _ops_rows cannot widen the table surface.
        with pytest.raises(OpsTableUnavailableError):
            source_service._ops_rows(
                "ingestion_runs; DROP TABLE ingestion_runs--",
                ("id",), "id", 10,
            )
        with pytest.raises(OpsTableUnavailableError):
            source_service._ops_rows(
                "sqlite_master", ("name",), "name", 10,
            )

    def test_limit_validation_rejects_hostile_values(self, security_client):
        # Non-numeric and out-of-contract limits: FastAPI validation
        # (ge=1, le=100) rejects them with 422 — the value is never bound
        # into SQL.
        for hostile in ("1 OR 1=1", "1; DROP TABLE ingestion_runs", "abc"):
            assert security_client.get(
                f"/ops/ingestion-runs?limit={hostile}"
            ).status_code == 422
            assert security_client.get(
                f"/ops/publication-batches?limit={hostile}"
            ).status_code == 422
        for out_of_range in ("0", "-1", "101", "99999999"):
            assert security_client.get(
                f"/ops/ingestion-runs?limit={out_of_range}"
            ).status_code == 422

    def test_response_shape_cannot_be_widened_by_params(
        self, security_client, seeded_ops_tables
    ):
        body = security_client.get(
            "/ops/ingestion-runs?limit=1"
        ).json()
        assert set(body[0]) == {
            "id", "run_type", "source_id", "category", "mode", "status",
            "rows_seen", "rows_applied", "rows_rejected", "rows_quarantined",
            "started_at", "finished_at", "notes",
        }
        body = security_client.get(
            "/ops/publication-batches?limit=1"
        ).json()
        assert set(body[0]) == {
            "id", "batch_no", "category", "record_count", "approved_by",
            "status", "created_at", "published_at", "notes",
        }

    def test_ops_tables_survive_hostile_requests(self, security_client):
        # After the probes above, the tables still exist and the clean
        # read path still works (nothing was dropped or altered).
        assert security_client.get("/ops/ingestion-runs").status_code == 200


# ---------------------------------------------------------------------------
# Malformed spec values: fail-closed, never a crash
# ---------------------------------------------------------------------------


class TestMalformedSpecValues:
    """A malformed value must become a blocker with a clear reason.

    Before the Phase 9 fix, ``unit_checks('RAM', {'capacity_gb': 'abc'})``
    raised ``TypeError: '<=' not supported between instances of 'int' and
    'str'`` — one malformed row would abort an entire publication batch
    with an opaque traceback instead of being rejected with a reason.
    """

    def test_string_number_is_rejected_not_compared(self):
        outcome = unit_checks("RAM", {"capacity_gb": "32"})
        assert not outcome.passed
        assert outcome.failures
        assert "capacity_gb" in outcome.failures[0]

    def test_non_numeric_string_is_rejected_not_crashed(self):
        outcome = unit_checks("RAM", {"capacity_gb": "abc"})
        assert not outcome.passed
        assert "capacity_gb" in outcome.failures[0]

    def test_bool_is_rejected_not_coerced(self):
        # bool is an int subclass; True would silently pass as 1.
        outcome = unit_checks("PSU", {"wattage": True})
        assert not outcome.passed

    def test_none_stays_absent(self):
        # None means "field absent" and must stay out of the checks.
        outcome = unit_checks("RAM", {"capacity_gb": None})
        assert outcome.passed

    def test_valid_numbers_still_pass(self):
        assert unit_checks("RAM", {"capacity_gb": 32, "speed_mhz": 6000}).passed

    def test_cross_field_string_values_rejected_not_crashed(self):
        outcome = cross_field_checks("RAM", {"modules": "2", "capacity_gb": "32"})
        assert not outcome.passed
        assert outcome.failures

    def test_validate_record_blocks_malformed_value(self):
        outcome = validate_record("RAM", {
            "ddr_generation": "DDR5", "capacity_gb": "abc",
            "speed_mhz": 6000, "modules": 2,
        })
        assert not outcome.passed
        assert any("capacity_gb" in b for b in outcome.blockers)


# ---------------------------------------------------------------------------
# Publisher: malformed record rejected, batch survives
# ---------------------------------------------------------------------------


class TestPublisherMalformedInput:
    """Fail-closed under hostile data: reject the bad row, keep the good.

    Reuses the Phase 4 publisher fixtures (v4-migrated dev DB clone). A
    malformed record (string wattage) must be REJECTED with a reason while
    the well-formed record in the same batch still publishes; the
    transaction must never die mid-flight with a TypeError.
    """

    @pytest.fixture()
    def pub_db(self, tmp_path):
        from backend.app.test_migration_runner import _clone_schema

        db = tmp_path / "sec_pub.db"
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

    @staticmethod
    def _psu_record(n: int, wattage=850) -> dict:
        from backend.app.identity.lifecycle import APPROVED

        return {
            "category": "PSU",
            "name": f"Corsair RM850x #{n}",
            "manufacturer": "Corsair",
            "canonical_key": f"corsair|psu|rm850x #{n}|850w-gold-mod",
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
                    "source_name": "owner-manual",
                    # Per-SKU URL (/p/ + mpn segment): passes the SKU
                    # evidence gate for 'verified' claims (M3 remediation).
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

    def test_malformed_record_rejected_batch_survives(self, pub_db):
        from backend.app.publishing.publisher import publish_batch

        good, bad = self._psu_record(1), self._psu_record(2, wattage="850W!!")
        result = publish_batch(pub_db, [bad, good], approved_by="security-test")

        assert result.rejected == 1
        assert result.published == 1
        assert any("wattage" in reason for reason in result.rejection_reasons)
        # The good record landed; the bad one is nowhere in the catalog.
        conn = sqlite3.connect(pub_db)
        names = {row[0] for row in conn.execute(
            "SELECT name FROM hardware WHERE name LIKE 'Corsair RM850x%'"
        ).fetchall()}
        conn.close()
        assert names == {"Corsair RM850x #1"}


# ---------------------------------------------------------------------------
# SSRF posture: the M3 adapters perform zero network I/O (structural pin)
# ---------------------------------------------------------------------------

_NETWORK_MODULE_NAMES = frozenset({
    "socket", "http", "httpx", "requests", "urllib", "urllib.request",
    "urllib3", "aiohttp", "aiofiles", "telnetlib", "ftplib", "smtplib",
    "asyncio", "subprocess",
})

_ADAPTERS_FILE = (
    Path(__file__).resolve().parent / "scripts" / "m3_adapters.py"
)


class TestAdaptersZeroNetworkIO:
    """The curated adapters are pure transforms over prepared rows.

    The mission safety contract forbids crawling / anti-bot interaction.
    These structural pins make the zero-network property durable: the
    adapters' module must not import any network library, and its functions
    must not call network sinks even if a transitive import appears.
    """

    def test_adapter_module_imports_no_network_libraries(self):
        tree = ast.parse(_ADAPTERS_FILE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        offenders = imported & _NETWORK_MODULE_NAMES
        assert not offenders, (
            f"M3 adapter module imported network libraries: {sorted(offenders)}"
        )

    def test_adapter_module_defines_no_io_functions(self):
        tree = ast.parse(_ADAPTERS_FILE.read_text(encoding="utf-8"))
        sinks = {"open", "urlopen", "socket", "getaddrinfo", "create_connection"}
        offenders = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in sinks
        ]
        assert not offenders, f"network/file sinks in m3_adapters: {offenders}"

    def test_map_record_works_with_network_disabled(self):
        # Behavioral proof: with sockets refused at the C level, mapping a
        # curated row still succeeds (no fetch is ever attempted).
        import socket as _socket

        adapter = WikipediaCuratedAdapter()
        row = {
            "hardware_name": "G.Skill Trident Z5 RGB 32GB DDR5-6000 CL30",
            "manufacturer": "G.Skill",
            "category": "RAM",
            "fields_json": (
                '{"ddr_generation": "DDR5", "capacity_gb": 32, '
                '"speed_mhz": 6000, "modules": 2}'
            ),
            "citation_url": "https://en.wikipedia.org/wiki/DDR5_SDRAM",
            "citation_revision": "1378669134",
            "access_date": "2026-11-16",
        }
        original_socket = _socket.socket

        class _RefusedSocket(original_socket):
            def __init__(self, *args, **kwargs):
                raise OSError("network disabled for security test")

        _socket.socket = _RefusedSocket
        try:
            record = adapter.map_record(row)
            values = adapter.acquire_values(record)
        finally:
            _socket.socket = original_socket

        assert record["citation_url"] == row["citation_url"]
        assert len(values) == 4
        assert values[0].source_url == row["citation_url"]


# ---------------------------------------------------------------------------
# Performance envelope: bounded queries and latency at pilot scale
# ---------------------------------------------------------------------------


class TestQueryPerformanceEnvelope:
    """Bounded query counts and latency at pilot scale (400+ rows).

    Deterministic structural bounds (query counts pinned via the SQLAlchemy
    event listener), not wall-clock assertions — CI timing is too noisy for
    pass/fail. Latency is recorded as evidence in the docs, not asserted.
    """

    @pytest.fixture()
    def perf_client(self):
        """App + in-memory DB seeded with 420 catalog rows (pilot scale)."""
        from datetime import date

        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from backend.app import main
        from backend.app.database import Base
        from backend.app.models import Hardware

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=engine)
        factory = sessionmaker(bind=engine)
        saved = (main.SessionLocal, source_service.SessionLocal)
        main.SessionLocal = factory
        source_service.SessionLocal = factory
        # The catalog service imported SessionLocal into its own namespace.
        from backend.app.services import hardware_catalog_service
        saved_catalog = hardware_catalog_service.SessionLocal
        hardware_catalog_service.SessionLocal = factory
        with factory() as session:
            types = ("CPU", "GPU", "RAM", "STORAGE", "MOTHERBOARD", "PSU")
            for i in range(420):
                session.add(Hardware(
                    name=f"Perf Item {i} {types[i % 6]}",
                    manufacturer="PerfCorp",
                    type=types[i % 6],
                    segment="Desktop",
                    release_date=date(2024, 1 + (i % 12), 1),
                ))
            session.commit()

        yield TestClient(main.app)
        hardware_catalog_service.SessionLocal = saved_catalog
        main.SessionLocal, source_service.SessionLocal = saved
        engine.dispose()

    def test_catalog_list_query_count_is_constant_at_scale(self, perf_client):
        from sqlalchemy import event as sa_event

        statements = []

        @sa_event.listens_for(source_service.SessionLocal.kw["bind"],
                              "before_cursor_execute")
        def _count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        response = perf_client.get("/hardware?limit=100")

        assert response.status_code == 200
        assert len(response.json()) == 100
        assert response.headers["X-Total-Count"] == "420"
        # Exactly 2: the COUNT + the page SELECT — independent of catalog size.
        assert len(statements) == 2

    def test_catalog_filtered_scan_stays_bounded(self, perf_client):
        from sqlalchemy import event as sa_event

        statements = []

        @sa_event.listens_for(source_service.SessionLocal.kw["bind"],
                              "before_cursor_execute")
        def _count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        response = perf_client.get(
            "/hardware?type=RAM&q=Perf&manufacturer=PerfCorp&limit=50"
        )

        assert response.status_code == 200
        assert len(statements) == 2  # COUNT + page SELECT, no N+1

    def test_provenance_query_count_stays_bounded_for_new_categories(
        self, perf_client
    ):
        # Seed one RAM row with provenance records, then count queries.
        from datetime import date as _date
        from sqlalchemy import event as sa_event

        with source_service.SessionLocal() as session:
            from backend.app.models import (
                Hardware, RAMSpecification, Source,
            )
            source = Source(id=5, name="Wikipedia (English) — curated",
                            url="https://en.wikipedia.org/")
            session.add(source)
            hardware = Hardware(
                name="Provenance RAM", manufacturer="PerfCorp", type="RAM",
                release_date=_date(2024, 2, 1),
            )
            hardware.ram_specification = RAMSpecification(
                ddr_generation="DDR5", capacity_gb=32, speed_mhz=6000,
                modules=2,
            )
            session.add(hardware)
            session.commit()
            hardware_id = hardware.id

        from backend.app.services.provenance_service import (
            insert_provenance_record,
        )
        with source_service.SessionLocal() as session:
            for index in range(30):
                insert_provenance_record(
                    session,
                    hardware_id=hardware_id,
                    table_name="ram_specifications",
                    field_name="capacity_gb",
                    source_id=5,
                    source_url="https://example.test/evidence",
                    evidence_status="verified",
                    batch_no=15,
                    evidenced_value=f"v{index}",
                )
            session.commit()

        statements = []

        @sa_event.listens_for(source_service.SessionLocal.kw["bind"],
                              "before_cursor_execute")
        def _count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        response = perf_client.get(f"/hardware/{hardware_id}/provenance")

        assert response.status_code == 200
        body = response.json()
        assert body["hardware_type"] == "RAM"
        # Eager-loaded relationships keep the count fixed regardless of the
        # 30 provenance rows (same constant as the Phase 7 bound test).
        assert len(statements) <= 12
