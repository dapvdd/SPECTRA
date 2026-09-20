import json
import os
from urllib import error, request
from urllib.parse import quote

from backend.app.schemas.explanation import ComparisonFacts


SYSTEM_PROMPT = """You are SPECTRA's comparison explanation assistant.
Only use the structured comparison facts supplied by SPECTRA. Never invent missing data, calculate new metrics or percentages, fabricate benchmarks, or infer performance for unsupported workloads such as gaming, temperatures, power consumption, or productivity. Treat unavailable and pending values as unavailable. Distinguish benchmark results from specifications. Explain the measurable differences and relevant trade-offs without deciding which CPU is universally better or making up use cases. Keep the response concise, readable, and factual."""


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, comparison: ComparisonFacts) -> str:
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                comparison.model_dump(),
                                separators=(",", ":"),
                            ),
                        }
                    ],
                },
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self.model, safe='')}:generateContent"
            f"?key={quote(self.api_key, safe='')}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=30) as response:
                response_payload = json.load(response)
        except (error.HTTPError, error.URLError, TimeoutError, ValueError) as provider_error:
            raise ProviderError("The AI provider request failed.") from provider_error

        try:
            parts = response_payload["candidates"][0]["content"]["parts"]
            explanation = "".join(
                part["text"] for part in parts if isinstance(part.get("text"), str)
            )
        except (KeyError, IndexError, TypeError) as response_error:
            raise ProviderError("The AI provider returned an invalid response.") from response_error

        if not isinstance(explanation, str) or not explanation.strip():
            raise ProviderError("The AI provider returned an empty response.")

        return explanation.strip()


def _get_provider() -> GeminiProvider:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    if not api_key or not model:
        raise ProviderUnavailableError(
            "Gemini API is not configured. Set GEMINI_API_KEY and GEMINI_MODEL."
        )

    return GeminiProvider(
        api_key=api_key,
        model=model,
    )


def generate_explanation(comparison: ComparisonFacts) -> str:
    return _get_provider().generate(comparison)
