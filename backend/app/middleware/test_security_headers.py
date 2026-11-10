"""Security headers middleware tests.

Covered:
- Every response carries X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy and Content-Security-Policy.
- Headers never overwrite values a route set deliberately.
- The middleware does not change status codes or bodies.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.middleware.security_headers import (
    SECURITY_HEADERS,
    SecurityHeadersMiddleware,
    install_security_headers_middleware,
)


def _app():
    app = FastAPI()

    @app.get("/plain")
    def plain():
        return {"ok": True}

    @app.get("/custom")
    def custom():
        from fastapi import Response

        return Response(
            content="{}",
            media_type="application/json",
            headers={"X-Content-Type-Options": "custom-value"},
        )

    install_security_headers_middleware(app)
    return app


@pytest.fixture
def client():
    return TestClient(_app())


class TestSecurityHeaders:
    def test_all_headers_present(self, client):
        resp = client.get("/plain")
        assert resp.status_code == 200
        for name, value in SECURITY_HEADERS.items():
            assert resp.headers[name] == value, name

    def test_route_headers_not_overwritten(self, client):
        resp = client.get("/custom")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "custom-value"
        # Other headers still applied.
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_body_unchanged(self, client):
        resp = client.get("/plain")
        assert resp.json() == {"ok": True}
        assert resp.status_code == 200

    def test_error_responses_also_get_headers(self, client):
        resp = client.get("/does-not-exist")
        assert resp.status_code == 404
        for name, value in SECURITY_HEADERS.items():
            assert resp.headers[name] == value, name
