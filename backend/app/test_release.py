"""Release identity endpoint tests.

Covered:
- /release returns version, sha, built_at, auth state and AI provider state.
- Unset env vars resolve to "unknown", never fabricated values.
- No secret values (API keys, DB URLs, paths) ever appear in the response.
- ai_provider reports configured/unconfigured, never a key value.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.release import get_release_identity


@pytest.fixture
def client():
    return TestClient(main.app)


class TestReleaseEndpoint:
    def test_unknown_when_env_unset(self, client, monkeypatch):
        # Patch the helper so it sees an empty environment regardless of what
        # the process env actually holds. Isolates the test from host-level
        # or cross-test env pollution.
        monkeypatch.setattr(
            "backend.app.release._env",
            lambda name, default="unknown": None,
        )
        monkeypatch.setattr(
            "backend.app.release.os.getenv",
            lambda name, default=None: "",
        )
        resp = client.get("/release")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "unknown"
        assert data["git_sha"] == "unknown"
        assert data["built_at"] == "unknown"
        assert data["image_digest"] is None
        assert data["ai_provider"] == "unconfigured"

    def test_reports_injected_identity(self, client, monkeypatch):
        monkeypatch.setenv("SPECTRA_RELEASE_VERSION", "3.1.0")
        monkeypatch.setenv("SPECTRA_RELEASE_SHA", "a" * 40)
        monkeypatch.setenv("SPECTRA_RELEASE_BUILT_AT", "2026-11-10T00:00:00Z")

        resp = client.get("/release")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "3.1.0"
        assert data["git_sha"] == "a" * 40
        assert data["built_at"] == "2026-11-10T00:00:00Z"

    def test_ai_provider_never_leaks_key(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key-value")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

        resp = client.get("/release")
        assert resp.status_code == 200
        body = resp.text
        assert "super-secret-key-value" not in body
        assert resp.json()["ai_provider"] == "configured"

    def test_no_db_url_or_paths_in_response(self, client, monkeypatch):
        monkeypatch.setenv(
            "SPECTRA_DATABASE_URL", "sqlite:////app/data/spectra.db"
        )
        monkeypatch.setenv("SPECTRA_AUTH_SECRET", "should-not-appear")

        resp = client.get("/release")
        body = resp.text
        assert "spectra.db" not in body
        assert "should-not-appear" not in body
        assert "/app/data" not in body

    def test_auth_state_reflected(self, client, monkeypatch):
        monkeypatch.setattr("backend.app.auth._AUTH_ENABLED", True)
        resp = client.get("/release")
        assert resp.json()["auth_enabled"] is True

    def test_auth_disabled_reflected(self, client, monkeypatch):
        monkeypatch.setattr("backend.app.auth._AUTH_ENABLED", False)
        resp = client.get("/release")
        assert resp.json()["auth_enabled"] is False
