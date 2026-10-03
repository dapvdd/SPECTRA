import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app, CORS_ORIGINS


class HealthEndpointTests(unittest.TestCase):
    def test_health_returns_200(self):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_returns_healthy_status(self):
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_health_is_deterministic(self):
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        self.assertEqual(data, {"status": "healthy"})


class DatabaseConfigurationTests(unittest.TestCase):
    def test_database_url_defaults_to_sqlite(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import backend.app.database as db_module

            importlib.reload(db_module)
            self.assertIn("sqlite", db_module.DATABASE_URL)

    def test_database_url_uses_environment_variable(self):
        with patch.dict(os.environ, {"SPECTRA_DATABASE_URL": "sqlite:///./test.db"}):
            import importlib

            import backend.app.database as db_module

            importlib.reload(db_module)
            self.assertEqual(db_module.DATABASE_URL, "sqlite:///./test.db")


class CORSConfigurationTests(unittest.TestCase):
    def test_cors_origins_default_to_localhost(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import backend.app.main as main_module

            importlib.reload(main_module)
            self.assertIn("http://localhost:5173", main_module.CORS_ORIGINS)

    def test_cors_origins_uses_environment_variable(self):
        with patch.dict(os.environ, {"SPECTRA_CORS_ORIGINS": "http://example.com,http://localhost:3000"}):
            import importlib

            import backend.app.main as main_module

            importlib.reload(main_module)
            self.assertIn("http://example.com", main_module.CORS_ORIGINS)
            self.assertIn("http://localhost:3000", main_module.CORS_ORIGINS)

    def test_cors_origins_strips_whitespace(self):
        with patch.dict(os.environ, {"SPECTRA_CORS_ORIGINS": " http://example.com , http://localhost:3000 "}):
            import importlib

            import backend.app.main as main_module

            importlib.reload(main_module)
            self.assertIn("http://example.com", main_module.CORS_ORIGINS)
            self.assertIn("http://localhost:3000", main_module.CORS_ORIGINS)


if __name__ == "__main__":
    unittest.main()
