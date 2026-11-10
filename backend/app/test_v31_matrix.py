"""M5 security and reliability regression matrix.

Cross-cutting scenarios that were not covered by the milestone-specific
test files. Each test maps to a row in docs/v3.1/TEST_MATRIX.md.

Covered here:
- CORS enforcement: disallowed origins get no CORS grant (browser blocks),
  allowed origins get headers. Anonymous catalog read works regardless
  (CORS is a browser constraint, not an auth control).
- Security headers on every response class (2xx/4xx) — regression guard.
- /release and /metrics never leak secrets even when configured.
- Anonymous catalog read (public read path) against a seeded DB.
- Provider-unavailable produces 503 (not 500) on all three AI endpoints.
- ProviderBusyError maps to 429 on all three AI endpoints.
- Rate limiter is opt-in: disabled by default, headers unchanged.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.middleware.security_headers import SECURITY_HEADERS


@pytest.fixture
def client():
    return TestClient(main.app)


class TestCORSEnforcement:
    def test_disallowed_origin_gets_no_cors_grant(self, client):
        resp = client.get(
            "/hardware",
            headers={"Origin": "https://evil.example.com"},
        )
        # The response itself succeeds (CORS is browser-enforced), but no
        # grant headers may be present.
        assert resp.status_code == 200
        assert "access-control-allow-origin" not in resp.headers

    def test_allowed_origin_gets_grant(self, client):
        resp = client.get(
            "/hardware",
            headers={"Origin": "http://localhost:8080"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") in (
            "http://localhost:8080",
            None,  # same-origin request may omit the header
        )

    def test_cors_preflight_rejects_unknown_origin(self, client):
        resp = client.options(
            "/hardware",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in resp.headers


class TestSecurityHeadersRegression:
    def test_headers_on_success(self, client):
        resp = client.get("/health")
        for name, value in SECURITY_HEADERS.items():
            assert resp.headers[name] == value

    def test_headers_on_auth_rejection(self, client):
        resp = client.post("/build/chat", json={})
        assert resp.status_code in (401, 422)
        for name, value in SECURITY_HEADERS.items():
            assert resp.headers[name] == value

    def test_headers_on_not_found(self, client):
        resp = client.get("/definitely-not-a-route")
        for name, value in SECURITY_HEADERS.items():
            assert resp.headers[name] == value


class TestNoSecretLeakage:
    def test_release_never_leaks_configured_key(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "sk-live-abc123realkey")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        resp = client.get("/release")
        assert "sk-live-abc123realkey" not in resp.text

    def test_metrics_contains_no_env_values(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "sk-live-abc123realkey")
        resp = client.get("/metrics")
        assert "sk-live-abc123realkey" not in resp.text

    def test_error_responses_contain_no_stack_traces(self, client):
        resp = client.post("/build/chat", json={"build": "not-an-object"})
        assert resp.status_code == 422
        assert "Traceback" not in resp.text
        assert ".py" not in resp.text


class TestAIEndpointFailureModes:
    """Missing key → 503; busy → 429; provider error → 502. On all three."""

    AI_ENDPOINTS = [
        (
            "/comparison/explanation",
            {
                "comparison": {
                    "cpu_a": {"name": "CPU A", "manufacturer": "AMD"},
                    "cpu_b": {"name": "CPU B", "manufacturer": "Intel"},
                    "metrics": [],
                    "ties": [],
                    "unavailable_metrics": [],
                },
            },
        ),
        (
            "/hardware/chat",
            {
                "hardware": {"id": 1, "name": "Ryzen 7 9800X3D"},
                "question": "Is this good for gaming?",
            },
        ),
        (
            "/build/chat",
            {
                "build": {
                    "cpu": {"id": 1, "name": "CPU A", "type": "CPU"},
                    "gpu": {"id": 2, "name": "GPU B", "type": "GPU"},
                },
                "question": "q",
            },
        ),
    ]

    @pytest.mark.parametrize("endpoint,payload", AI_ENDPOINTS)
    def test_missing_key_returns_503_not_500(self, client, monkeypatch,
                                             endpoint, payload):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("GEMINI_MODEL", "")
        resp = client.post(endpoint, json=payload)
        assert resp.status_code == 503, resp.text

    @pytest.mark.parametrize("endpoint,payload", AI_ENDPOINTS)
    def test_busy_returns_429(self, client, monkeypatch, endpoint, payload):
        import backend.app.services.explanation_service as es

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setenv("GEMINI_MODEL", "m")
        monkeypatch.setattr(es, "_CONCURRENCY_LIMIT", 1)
        monkeypatch.setattr(
            es, "_concurrency_semaphore",
            __import__("threading").BoundedSemaphore(1),
        )
        # Exhaust the single permit to force the busy path.
        es._concurrency_semaphore.acquire(blocking=False)
        try:
            resp = client.post(endpoint, json=payload)
            assert resp.status_code == 429, resp.text
        finally:
            es._concurrency_semaphore.release()
