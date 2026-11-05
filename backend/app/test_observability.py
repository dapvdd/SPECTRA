"""Tests for Phase 1.4 observability: request-id middleware, /ready, structured logs.

Verifies:
- Every response carries a X-Request-ID (generated or echoed from upstream).
- An upstream X-Request-ID is echoed on the response (correlation preserved).
- /ready returns 200 "ready" with a reachable DB and reports migration state.
- Structured JSON logs emit single-line JSON records via the JsonFormatter.
- configure_logging is idempotent (no duplicate handlers).
"""

import io
import json
import logging
import sys
import unittest

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.logging_config import (
    JsonFormatter,
    configure_logging,
    get_logger,
)
from backend.app.middleware.request_id import REQUEST_ID_HEADER


class RequestIDMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_response_carries_request_id(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.headers.get(REQUEST_ID_HEADER))
        self.assertTrue(response.headers.get(REQUEST_ID_HEADER))

    def test_upstream_request_id_is_echoed(self):
        upstream_id = "echo-me-12345"
        response = self.client.get(
            "/health", headers={REQUEST_ID_HEADER: upstream_id}
        )
        self.assertEqual(response.headers.get(REQUEST_ID_HEADER), upstream_id)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_ready_returns_200_when_db_reachable(self):
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["database"], "reachable")
        # Migration state is informational; both tracked and untracked are valid.
        self.assertIn(data["migrations"], {
            "tracked-version-1",
            "tracked-version-0",
            "untracked",
            "unknown",
        })

    def test_ready_returns_503_when_db_unreachable(self):
        # Point the app's SessionLocal at an unreachable database URL.
        from sqlalchemy import create_engine

        bad_engine = create_engine(
            "sqlite:///nonexistent_dir_xyz/does_not_exist.db",
            connect_args={"check_same_thread": False},
        )
        from sqlalchemy.orm import sessionmaker

        original_session = main.SessionLocal
        main.SessionLocal = sessionmaker(bind=bad_engine)
        try:
            response = self.client.get("/ready")
            self.assertEqual(response.status_code, 503)
        finally:
            main.SessionLocal = original_session


class StructuredLoggingTests(unittest.TestCase):
    def test_configure_logging_is_idempotent(self):
        root = logging.getLogger()
        before = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
        # Run twice; should not add a second JSON handler.
        configure_logging()
        configure_logging()
        after = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
        self.assertEqual(len(after), len(before) or 1)
        # At least one JSON handler present.
        self.assertGreaterEqual(len(after), 1)

    def test_json_format_outputs_single_json_line(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("test.json.format")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("hello world", extra={
            "structured_extra": {"request_id": "abc", "duration_ms": 12}
        })

        line = stream.getvalue().strip()
        parsed = json.loads(line)
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["message"], "hello world")
        self.assertEqual(parsed["request_id"], "abc")
        self.assertEqual(parsed["duration_ms"], 12)
        # Exactly one record, no embedded newlines.
        self.assertEqual(line.count("\n"), 0)

    def test_logger_helper_returns_logger(self):
        log = get_logger("backend.test")
        self.assertIsInstance(log, logging.Logger)
