import json

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from backend.app import main
from backend.app.services import explanation_service
from backend.app.schemas.explanation import ComparisonFacts


def _comparison_payload():
    return {
        "comparison": {
            "cpu_a": {"name": "CPU A", "manufacturer": "Vendor A"},
            "cpu_b": {"name": "CPU B", "manufacturer": "Vendor B"},
            "metrics": [
                {
                    "metric_key": "cores",
                    "name": "Cores",
                    "value_a": 8,
                    "value_b": 6,
                    "unit": "",
                    "source": "specification",
                    "direction": "higher",
                    "winner": "cpu_a",
                    "difference_percent": 33.3,
                }
            ],
            "ties": [],
            "unavailable_metrics": [
                {
                    "metric_key": "multi_core",
                    "name": "Geekbench 7 Multi-Core",
                    "source": "benchmark",
                    "reason": "unavailable",
                }
            ],
        }
    }


class TestExplanationAPI:
    def setup_method(self):
        self.client = TestClient(main.app)
        self.original_generator = explanation_service.generate_explanation

    def teardown_method(self):
        explanation_service.generate_explanation = self.original_generator

    def test_returns_explanation_for_valid_comparison(self):
        explanation_service.generate_explanation = lambda comparison: (
            "CPU A has more cores in the supplied specifications."
        )

        response = self.client.post(
            "/comparison/explanation",
            json=_comparison_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "explanation": "CPU A has more cores in the supplied specifications."
        }

    def test_rejects_invalid_comparison_payload(self):
        response = self.client.post(
            "/comparison/explanation",
            json={"comparison": {"cpu_a": {"name": "CPU A"}}},
        )

        assert response.status_code == 422

    def test_returns_service_unavailable_when_provider_is_not_configured(self):
        def unavailable(comparison):
            raise explanation_service.ProviderUnavailableError(
                "AI provider is not configured."
            )

        explanation_service.generate_explanation = unavailable

        response = self.client.post(
            "/comparison/explanation",
            json=_comparison_payload(),
        )

        assert response.status_code == 503
        assert response.json() == {"detail": "AI provider is not configured."}

    def test_returns_bad_gateway_when_provider_fails(self):
        def failed(comparison):
            raise explanation_service.ProviderError(
                "The AI provider request failed."
            )

        explanation_service.generate_explanation = failed

        response = self.client.post(
            "/comparison/explanation",
            json=_comparison_payload(),
        )

        assert response.status_code == 502
        assert response.json() == {"detail": "The AI provider request failed."}


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _comparison_facts():
    return TypeAdapter(ComparisonFacts).validate_python(
        _comparison_payload()["comparison"]
    )


class TestGeminiProvider:
    def setup_method(self):
        self.original_urlopen = explanation_service.request.urlopen

    def teardown_method(self):
        explanation_service.request.urlopen = self.original_urlopen

    def test_parses_generated_text_and_sends_structured_prompt(self):
        captured = {}

        def urlopen(http_request, timeout):
            captured["request"] = http_request
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "CPU A has more cores. "},
                                    {"text": "The benchmark value is unavailable."},
                                ]
                            }
                        }
                    ]
                }
            )

        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        result = provider.generate(_comparison_facts())

        assert result == "CPU A has more cores. The benchmark value is unavailable."
        assert captured["timeout"] == 30
        assert "generativelanguage.googleapis.com/v1beta/models/test-model:generateContent" in captured["request"].full_url
        assert "key=test-key" in captured["request"].full_url
        payload = json.loads(captured["request"].data)
        assert explanation_service.SYSTEM_PROMPT in payload["systemInstruction"]["parts"][0]["text"]
        assert "CPU A" in payload["contents"][0]["parts"][0]["text"]

    def test_rejects_malformed_response(self):
        explanation_service.request.urlopen = lambda http_request, timeout: _FakeResponse(
            {"candidates": []}
        )
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        with pytest.raises(
            explanation_service.ProviderError,
            match="invalid response",
        ):
            provider.generate(_comparison_facts())

    def test_rejects_empty_response(self):
        explanation_service.request.urlopen = lambda http_request, timeout: _FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "   "}]}}
                ]
            }
        )
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        with pytest.raises(
            explanation_service.ProviderError,
            match="empty response",
        ):
            provider.generate(_comparison_facts())

    def test_converts_gemini_api_error_to_provider_error(self):
        def urlopen(http_request, timeout):
            raise explanation_service.error.HTTPError(
                http_request.full_url,
                429,
                "rate limited",
                {},
                None,
            )

        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        with pytest.raises(
            explanation_service.ProviderError,
            match="request failed",
        ):
            provider.generate(_comparison_facts())

    def test_requires_gemini_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_MODEL", "test-model")

        with pytest.raises(
            explanation_service.ProviderUnavailableError,
            match="GEMINI_API_KEY and GEMINI_MODEL",
        ):
            explanation_service._get_provider()

    def test_requires_gemini_model(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        with pytest.raises(
            explanation_service.ProviderUnavailableError,
            match="GEMINI_API_KEY and GEMINI_MODEL",
        ):
            explanation_service._get_provider()
