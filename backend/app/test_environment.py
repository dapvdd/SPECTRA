import os

from backend.app import main


def test_backend_loads_environment_from_project_root(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=test-key\nGEMINI_MODEL=test-model\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)

    try:
        main.load_backend_environment()

        assert os.getenv("GEMINI_API_KEY") == "test-key"
        assert os.getenv("GEMINI_MODEL") == "test-model"
    finally:
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GEMINI_MODEL", None)
