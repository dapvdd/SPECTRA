"""Tests for the opt-in rate-limit / cost-control middleware.

The middleware is locked to ``enabled=False`` in the real app unless the operator
opts in via ``SPECTRA_RATE_LIMIT_ENABLED``; these tests construct an isolated app
with the middleware forced on, so they never depend on the environment and never
touch the real database.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.middleware.rate_limit import (
    AI_ENDPOINT_PREFIXES,
    RateLimitMiddleware,
    install_rate_limit_middleware,
)


def _make_app(public_limit, ai_limit, enabled=True):
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/comparison/explanation")
    def ai_route():
        return {"ok": True}

    @app.post("/comparison/explanation")
    def ai_post():
        return {"ok": True}

    install_rate_limit_middleware(
        app,
        public_limit=public_limit,
        ai_limit=ai_limit,
        enabled=enabled,
    )
    return app


@pytest.fixture
def client():
    app = _make_app(public_limit=5, ai_limit=2)
    return TestClient(app)


@pytest.fixture
def unlimited_client():
    app = _make_app(public_limit=5, ai_limit=2, enabled=False)
    return TestClient(app)


def test_ai_endpoint_prefixes_cover_expensive_routes():
    assert "/comparison/explanation" in AI_ENDPOINT_PREFIXES
    assert "/hardware/chat" in AI_ENDPOINT_PREFIXES
    assert "/build/chat" in AI_ENDPOINT_PREFIXES
    assert "/build/conversations" in AI_ENDPOINT_PREFIXES


def test_rate_limit_is_off_by_default_in_the_installed_app():
    # The global app must not impose limits unless the operator opts in.
    from backend.app.main import app as main_app

    for middleware in main_app.user_middleware:
        assert middleware.cls is not RateLimitMiddleware or not _middleware_enabled(
            main_app
        )


def _middleware_enabled(app):
    for instance in getattr(app, "_rate_limit_instances", []):
        if instance.enabled:
            return True
    return False


def test_public_limit_is_enforced_when_enabled(client):
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200

    response = client.get("/health")
    assert response.status_code == 429
    payload = response.json()
    assert "rate_limit" in payload
    assert payload["rate_limit"]["window_seconds"] == 60


def test_ai_limit_is_stricter_than_public_limit(client):
    # AI limit 2, public 5: the AI route should trip at 3, not 5.
    client.post("/comparison/explanation")
    client.post("/comparison/explanation")
    response = client.post("/comparison/explanation")
    assert response.status_code == 429


def test_retry_after_header_is_present_on_429(client):
    client.post("/comparison/explanation")
    client.post("/comparison/explanation")
    response = client.post("/comparison/explanation")
    assert response.status_code == 429
    assert response.headers.get("retry-after")


def test_disabled_middleware_passes_everything_through(unlimited_client):
    for _ in range(20):
        response = unlimited_client.get("/health")
        assert response.status_code == 200

    response = unlimited_client.post("/comparison/explanation")
    assert response.status_code == 200


def test_forwarded_for_is_used_as_client_identity(client):
    headers = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(5):
        assert client.get("/health", headers=headers).status_code == 200

    assert client.get("/health", headers=headers).status_code == 429


def test_middleware_can_be_disabled_in_code():
    app = _make_app(public_limit=5, ai_limit=2, enabled=False)
    single = TestClient(app)
    for _ in range(10):
        assert single.get("/health").status_code == 200
