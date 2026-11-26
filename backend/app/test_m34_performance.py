"""M3.4 Task 6 — catalog performance: gzip compression + response shape.

Pins:
- A client sending Accept-Encoding: gzip on the unfiltered catalog receives
  Content-Encoding: gzip and the decoded JSON shape is byte-compatible with
  the uncompressed response (same fields, same order, X-Total-Count intact).
- Small responses are NOT compressed (minimum_size threshold).
- No scoring/recommendation logic is touched (boundary with M4).
"""

from __future__ import annotations

import gzip
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult,
    BuildConversation,
    BuildMessage,
    CPUSpecification,
    GPUSpecification,
    Hardware,
    Source,
)
from backend.app.services import hardware_catalog_service


class GzipSetup:
    def __init__(self, rows: int = 40):
        self._saved = {
            "main.SessionLocal": main.SessionLocal,
            "catalog.SessionLocal": hardware_catalog_service.SessionLocal,
        }
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main.SessionLocal = self.session_factory
        hardware_catalog_service.SessionLocal = self.session_factory
        with self.session_factory() as session:
            for i in range(rows):
                session.add(
                    Hardware(
                        name=f"Component {i} Ultra Pro Max Edition",
                        manufacturer="Vendor",
                        type="CPU",
                        architecture="Zen",
                    )
                )
            session.commit()
        self.client = TestClient(main.app)

    def restore(self):
        main.SessionLocal = self._saved["main.SessionLocal"]
        hardware_catalog_service.SessionLocal = self._saved["catalog.SessionLocal"]


class TestCatalogCompression(unittest.TestCase):
    def setUp(self):
        self.setup = GzipSetup()
        self.client = self.setup.client

    def tearDown(self):
        self.setup.restore()

    def test_unfiltered_catalog_is_gzipped_when_requested(self):
        response = self.client.get(
            "/hardware", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-encoding"), "gzip")

    def test_decoded_payload_matches_uncompressed_shape(self):
        plain = self.client.get("/hardware")
        gz = self.client.get("/hardware", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(plain.status_code, 200)
        self.assertEqual(gz.status_code, 200)

        # httpx (TestClient transport) auto-decompresses and strips the
        # header, so gz.content is already the decoded body: identical to
        # the plain response's bytes. Raw compressed bytes are verified at
        # the ASGI level in test_raw_asgi_response_is_gzipped below.
        self.assertEqual(gz.content, plain.content)
        self.assertEqual(
            gz.headers.get("x-total-count"), plain.headers.get("x-total-count")
        )

    def test_raw_asgi_response_is_gzipped(self):
        import asyncio

        from backend.app import main as main_module

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/hardware",
            "raw_path": b"/hardware",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"accept-encoding", b"gzip"),
            ],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }

        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(main_module.app(scope, receive, send))

        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(
            m["body"] for m in messages if m["type"] == "http.response.body"
        )
        headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
        self.assertEqual(headers.get("content-encoding"), "gzip")
        self.assertTrue(body.startswith(b"\x1f\x8b"))  # gzip magic
        decoded = json.loads(gzip.decompress(body).decode("utf-8"))
        self.assertEqual(len(decoded), 40)

    def test_small_responses_not_compressed(self):
        # /health is far below the minimum_size threshold.
        response = self.client.get("/health", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("content-encoding"))

    def test_uncompressed_request_stays_byte_compatible(self):
        # httpx always advertises gzip, so transport-level requests appear
        # compressed. The compatibility guarantee that matters is the
        # payload shape and total count, verified here on a no-encoding
        # ASGI request in test_raw_asgi_response_is_gzipped's sibling:
        # without Accept-Encoding, Starlette GZipMiddleware does not set
        # content-encoding (its compress_if_needed is header-gated).
        response = self.client.get("/hardware")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-total-count"), "40")
        self.assertTrue(len(response.json()) == 40)

    def test_raw_asgi_no_encoding_not_compressed(self):
        import asyncio

        from backend.app import main as main_module

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/hardware",
            "raw_path": b"/hardware",
            "query_string": b"",
            "headers": [(b"host", b"testserver")],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(main_module.app(scope, receive, send))
        start = next(m for m in messages if m["type"] == "http.response.start")
        headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
        self.assertIsNone(headers.get("content-encoding"))


if __name__ == "__main__":
    unittest.main()
