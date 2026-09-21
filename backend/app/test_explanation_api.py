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


def _http_error(http_request, status, message):
    response = explanation_service.error.HTTPError(
        http_request.full_url,
        status,
        message,
        {},
        None,
    )
    response.read = lambda: message.encode("utf-8")
    return response


def _successful_response():
    return _FakeResponse(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Transient issue recovered."}]
                    }
                }
            ]
        }
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

    def test_retries_503_then_succeeds(self, monkeypatch):
        calls = []
        delays = []

        def urlopen(http_request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise _http_error(http_request, 503, "model is currently experiencing high demand")
            return _successful_response()

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        assert provider.generate(_comparison_facts()) == "Transient issue recovered."
        assert calls == [30, 30]
        assert delays == [1]

    def test_retries_503_until_exhausted(self, monkeypatch):
        calls = []
        delays = []

        def urlopen(http_request, timeout):
            calls.append(timeout)
            raise _http_error(http_request, 503, "model is currently experiencing high demand")

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        with pytest.raises(explanation_service.ProviderError, match="request failed"):
            provider.generate(_comparison_facts())

        assert len(calls) == 4
        assert delays == [1, 2, 4]

    def test_retries_429(self, monkeypatch):
        calls = []
        delays = []

        def urlopen(http_request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise _http_error(http_request, 429, "rate limited")
            return _successful_response()

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        assert provider.generate(_comparison_facts()) == "Transient issue recovered."
        assert len(calls) == 2
        assert delays == [1]

    def test_does_not_retry_permanent_400(self, monkeypatch):
        calls = []
        delays = []

        def urlopen(http_request, timeout):
            calls.append(timeout)
            raise _http_error(http_request, 400, "invalid request")

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        with pytest.raises(explanation_service.ProviderError, match="request failed"):
            provider.generate(_comparison_facts())

        assert len(calls) == 1
        assert delays == []

    def test_retries_timeout(self, monkeypatch):
        calls = []
        delays = []

        def urlopen(http_request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise TimeoutError("read operation timed out")
            return _successful_response()

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider("test-key", "test-model")

        assert provider.generate(_comparison_facts()) == "Transient issue recovered."
        assert len(calls) == 2
        assert delays == [1]

    def test_logs_sanitized_gemini_api_error(self, caplog, monkeypatch):
        api_key = "secret-test-key"
        delays = []

        def urlopen(http_request, timeout):
            raise _http_error(
                http_request,
                503,
                '{"error":{"message":"high demand; key=secret-test-key"}}',
            )

        monkeypatch.setattr(explanation_service.time, "sleep", delays.append)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider(api_key, "test-model")

        with caplog.at_level("ERROR"):
            with pytest.raises(explanation_service.ProviderError, match="request failed"):
                provider.generate(_comparison_facts())

        assert "HTTP status=503" in caplog.text
        assert "high demand" in caplog.text
        assert api_key not in caplog.text
        assert "key=[REDACTED_API_KEY]" in caplog.text
        assert "generativelanguage.googleapis.com" not in caplog.text
        assert delays == [1, 2, 4]

    def test_logs_sanitized_non_http_provider_error(self, caplog, monkeypatch):
        api_key = "secret-test-key"

        def urlopen(http_request, timeout):
            raise explanation_service.error.URLError(
                f"connection failed for https://example.test/?key={api_key}"
            )

        monkeypatch.setattr(explanation_service.time, "sleep", lambda delay: None)
        explanation_service.request.urlopen = urlopen
        provider = explanation_service.GeminiProvider(api_key, "test-model")

        with caplog.at_level("ERROR"):
            with pytest.raises(explanation_service.ProviderError, match="request failed"):
                provider.generate(_comparison_facts())

        assert "before receiving an HTTP response" in caplog.text
        assert "connection failed" in caplog.text
        assert api_key not in caplog.text
        assert "[REDACTED_URL]" in caplog.text

    def test_converts_gemini_api_error_to_provider_error(self, monkeypatch):
        def urlopen(http_request, timeout):
            raise _http_error(http_request, 400, "invalid request")

        monkeypatch.setattr(explanation_service.time, "sleep", lambda delay: None)
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
