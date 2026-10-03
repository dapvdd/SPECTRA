import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models import Hardware, BuildConversation, BuildMessage

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DockerComposeConfigTests(unittest.TestCase):
    def test_compose_file_exists_and_defines_services(self):
        compose_path = PROJECT_ROOT / "compose.yaml"
        self.assertTrue(compose_path.is_file(), "compose.yaml should exist")

        content = compose_path.read_text(encoding="utf-8")
        self.assertIn("backend:", content)
        self.assertIn("frontend:", content)
        self.assertIn("spectra-sqlite-data:", content)
        self.assertIn("healthcheck:", content)
        self.assertIn("service_healthy", content)

    def test_dockerfile_backend_exists_and_configured(self):
        df_path = PROJECT_ROOT / "Dockerfile.backend"
        self.assertTrue(df_path.is_file(), "Dockerfile.backend should exist")

        content = df_path.read_text(encoding="utf-8")
        self.assertIn("FROM python:3.13-slim", content)
        self.assertIn("SPECTRA_DATABASE_URL", content)
        self.assertIn("EXPOSE 8000", content)
        self.assertIn("ENTRYPOINT", content)

    def test_dockerfile_frontend_exists_and_configured(self):
        df_path = PROJECT_ROOT / "Dockerfile.frontend"
        self.assertTrue(df_path.is_file(), "Dockerfile.frontend should exist")

        content = df_path.read_text(encoding="utf-8")
        self.assertIn("FROM node:22-alpine", content)
        self.assertIn("VITE_API_BASE_URL", content)
        self.assertIn("FROM nginx:alpine", content)
        self.assertIn("EXPOSE 8080", content)

    def test_dockerignore_protects_repository_state(self):
        ignore_path = PROJECT_ROOT / ".dockerignore"
        self.assertTrue(ignore_path.is_file(), ".dockerignore should exist")

        content = ignore_path.read_text(encoding="utf-8")
        self.assertIn(".venv", content)
        self.assertIn(".opencode", content)
        self.assertIn("node_modules", content)


class ContainerCORSAndHealthTests(unittest.TestCase):
    def test_health_check_responds_for_container_healthcheck(self):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_cors_allows_frontend_container_origin(self):
        client = TestClient(app)
        response = client.options(
            "/hardware",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        allow_origin = response.headers.get("access-control-allow-origin")
        self.assertEqual(allow_origin, "http://localhost:8080")


class PersistentStorageCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.template_db = PROJECT_ROOT / "data" / "spectra.db"
        self.volume_db = Path(self.temp_dir) / "spectra.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_entrypoint_initialization_prevents_empty_volume_masking(self):
        # 1. Simulate fresh empty volume mounted over /app/data
        self.assertFalse(self.volume_db.exists())

        # 2. Simulate entrypoint.sh: if target DB does not exist, copy from template
        shutil.copy2(self.template_db, self.volume_db)
        self.assertTrue(self.volume_db.exists())

        # 3. Verify SQLite engine opens volume database and has expected hardware rows
        db_url = f"sqlite:///{self.volume_db.as_posix()}"
        engine = create_engine(db_url)
        with Session(engine) as session:
            count = session.query(Hardware).count()
            self.assertEqual(count, 5239)

    def test_database_persistence_across_restart_cycle(self):
        # Step 1: Initialize database in volume
        shutil.copy2(self.template_db, self.volume_db)
        db_url = f"sqlite:///{self.volume_db.as_posix()}"

        # Step 2: First container run - create a persistent conversation record
        engine_run1 = create_engine(db_url)
        with Session(engine_run1) as session:
            cpu = session.scalars(select(Hardware).where(Hardware.type == "CPU")).first()
            gpu = session.scalars(select(Hardware).where(Hardware.type == "GPU")).first()
            self.assertIsNotNone(cpu)
            self.assertIsNotNone(gpu)

            conv = BuildConversation(
                cpu_hardware_id=cpu.id,
                gpu_hardware_id=gpu.id,
            )
            conv.messages.append(
                BuildMessage(
                    role="user",
                    content="Is this build good for 1440p gaming?",
                )
            )
            session.add(conv)
            session.commit()
            created_conv_id = conv.id

        # Step 3: Simulate "docker compose down" -> engine disposed, connections closed
        engine_run1.dispose()

        # Step 4: Simulate "docker compose up" -> new container starts, reusing same volume
        # Verify entrypoint would NOT overwrite because file already exists
        self.assertTrue(self.volume_db.exists())

        engine_run2 = create_engine(db_url)
        with Session(engine_run2) as session:
            restored = session.get(BuildConversation, created_conv_id)
            self.assertIsNotNone(restored)
            self.assertEqual(len(restored.messages), 1)
            self.assertEqual(
                restored.messages[0].content,
                "Is this build good for 1440p gaming?",
            )

        engine_run2.dispose()


if __name__ == "__main__":
    unittest.main()
