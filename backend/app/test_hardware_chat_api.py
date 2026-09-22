import json

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.services import explanation_service, hardware_chat_service


def _hardware_payload():
    return {
        "hardware": {
            "id": 123,
            "name": "AMD Ryzen 5 5600",
            "manufacturer": "AMD",
            "type": "CPU",
            "specifications": {
                "cores": 6,
                "threads": 12,
                "base_clock_ghz": 3.5,
                "boost_clock_ghz": 4.4,
                "tdp_w": 65,
            },
            "benchmarks": [
                {
                    "benchmark_name": "Geekbench 7",
                    "test_type": "single-core",
                    "score": 2100,
                    "unit": "points",
                    "source": "Geekbench Browser - Geekbench 7 CPU",
                }
            ],
        },
        "question": "Kuat buat GTA V nggak?",
    }


class TestHardwareChatAPI:
    def setup_method(self):
        self.client = TestClient(main.app)
        self.original_generator = hardware_chat_service.generate_chat_answer

    def teardown_method(self):
        hardware_chat_service.generate_chat_answer = self.original_generator

    @pytest.mark.parametrize(
        "payload",
        [
            {**_hardware_payload(), "question": ""},
            {**_hardware_payload(), "question": "   "},
            {**_hardware_payload(), "question": "x" * 2001},
            {
                **_hardware_payload(),
                "hardware": {**_hardware_payload()["hardware"], "id": 0},
            },
            {
                **_hardware_payload(),
                "hardware": {
                    **_hardware_payload()["hardware"],
                    "specifications": {"cores": {"unexpected": "object"}},
                },
            },
            {
                **_hardware_payload(),
                "hardware": {
                    **_hardware_payload()["hardware"],
                    "benchmarks": {"score": 2100},
                },
            },
        ],
    )
    def test_rejects_invalid_request(self, payload):
        response = self.client.post("/hardware/chat", json=payload)

        assert response.status_code == 422

    def test_returns_answer_and_preserves_markdown(self):
        hardware_chat_service.generate_chat_answer = lambda request: (
            "## Jawaban\n\n**Bisa**, secara kualitatif."
        )

        response = self.client.post("/hardware/chat", json=_hardware_payload())

        assert response.status_code == 200
        assert response.json() == {
            "answer": "## Jawaban\n\n**Bisa**, secara kualitatif."
        }

    @pytest.mark.parametrize(
        ("exception", "status_code"),
        [
            (explanation_service.ProviderUnavailableError("not configured"), 503),
            (explanation_service.ProviderError("provider failed"), 502),
        ],
    )
    def test_maps_provider_failures(self, exception, status_code):
        def failed(request):
            raise exception

        hardware_chat_service.generate_chat_answer = failed

        response = self.client.post("/hardware/chat", json=_hardware_payload())

        assert response.status_code == status_code

    def test_returns_service_unavailable_when_gemini_is_not_configured(self, monkeypatch):
        def unavailable():
            raise explanation_service.ProviderUnavailableError(
                "Gemini API is not configured."
            )

        monkeypatch.setattr(explanation_service, "_get_provider", unavailable)

        response = self.client.post("/hardware/chat", json=_hardware_payload())

        assert response.status_code == 503

    def test_missing_hardware_is_rejected(self):
        response = self.client.post("/hardware/chat", json={"question": "Help"})

        assert response.status_code == 422


class TestHardwareChatService:
    def setup_method(self):
        self.original_generator = explanation_service.generate_chat_response

    def teardown_method(self):
        explanation_service.generate_chat_response = self.original_generator

    def test_sends_hardware_context_and_safety_prompt(self):
        captured = {}

        def generate(system_prompt, user_text):
            captured["system_prompt"] = system_prompt
            captured["user_text"] = user_text
            return "Jawaban aman."

        explanation_service.generate_chat_response = generate
        request = hardware_chat_service.HardwareChatRequest.model_validate(
            _hardware_payload()
        )

        assert hardware_chat_service.generate_chat_answer(request) == "Jawaban aman."

        context = json.loads(captured["user_text"])
        serialized_context = captured["user_text"]
        assert context["hardware"]["name"] == "AMD Ryzen 5 5600"
        assert context["hardware"]["specifications"]["cores"] == 6
        assert context["hardware"]["benchmarks"][0]["score"] == 2100
        assert context["question"] == "Kuat buat GTA V nggak?"
        normalized_prompt = " ".join(captured["system_prompt"].split())
        for phrase in (
            "Never invent specifications",
            "benchmark scores",
            "FPS",
            "application timings",
            "known supplied facts",
            "qualitative inference",
            "cannot be determined",
            "GPU, RAM",
            "resolution",
            "Source-code line count alone is not a deterministic compile",
            "Do not universally",
        ):
            assert phrase in normalized_prompt
        assert "AMD Ryzen 5 5600" in serialized_context

    def test_realistic_benchmark_fields_are_accepted(self):
        payload = _hardware_payload()
        payload["hardware"]["benchmarks"][0].update(
            {
                "id": 7,
                "hardware_id": 123,
                "recorded_at": "2026-09-16T00:00:00Z",
                "source": {"id": 1, "name": "Geekbench", "url": "https://example.test"},
            }
        )

        request = hardware_chat_service.HardwareChatRequest.model_validate(payload)

        assert request.hardware.benchmarks[0].hardware_id == 123

    def test_context_is_forwarded_to_the_shared_gemini_provider_path(self, monkeypatch):
        captured = {}

        class FakeProvider:
            def generate_text(self, system_prompt, user_text):
                captured["system_prompt"] = system_prompt
                captured["user_text"] = user_text
                return "Provider answer."

        monkeypatch.setattr(explanation_service, "_get_provider", lambda: FakeProvider())
        request = hardware_chat_service.HardwareChatRequest.model_validate(
            _hardware_payload()
        )

        assert hardware_chat_service.generate_chat_answer(request) == "Provider answer."
        assert "AMD Ryzen 5 5600" in captured["user_text"]
        assert "Kuat buat GTA V nggak?" in captured["user_text"]
        assert "Never invent specifications" in captured["system_prompt"]

    @pytest.mark.parametrize(
        "provider_error",
        [
            "The AI provider returned an empty response.",
            "The AI provider returned an invalid response.",
        ],
    )
    def test_invalid_provider_response_maps_to_provider_error(self, provider_error):
        explanation_service.generate_chat_response = lambda system_prompt, user_text: (
            (_ for _ in ()).throw(explanation_service.ProviderError(provider_error))
        )

        with pytest.raises(
            explanation_service.ProviderError,
            match="provider returned",
        ):
            hardware_chat_service.generate_chat_answer(
                hardware_chat_service.HardwareChatRequest.model_validate(
                    _hardware_payload()
                )
            )
