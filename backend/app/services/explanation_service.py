import json
import logging
import os
import re
import threading
import time
from urllib import error, request
from urllib.parse import quote

from backend.app.schemas.explanation import ComparisonFacts


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SPECTRA's comparison explanation assistant.
Only use the structured comparison facts supplied by SPECTRA. Never invent missing data, calculate new metrics or percentages, fabricate benchmarks, or infer performance for unsupported workloads such as gaming, temperatures, power consumption, or productivity. Treat unavailable and pending values as unavailable. Distinguish benchmark results from specifications. Explain the measurable differences and relevant trade-offs without deciding which CPU is universally better or making up use cases. Keep the response concise, readable, and factual."""

_MAX_LOG_MESSAGE_LENGTH = 2000
_MAX_RETRIES = 3
_RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_DELAYS = (1, 2, 4)

# M4.4 concurrency limit: bound simultaneous provider calls so a slow or
# hanging provider cannot accumulate unbounded in-flight requests (each one
# holds a worker thread and client connection). Configurable; a value of 0
# or less disables the limit.
_CONCURRENCY_LIMIT = max(0, int(os.getenv("SPECTRA_AI_CONCURRENCY", "4")))
_concurrency_semaphore = (
    threading.BoundedSemaphore(_CONCURRENCY_LIMIT)
    if _CONCURRENCY_LIMIT > 0
    else None
)


class ProviderBusyError(RuntimeError):
    """Too many concurrent provider requests; the caller should retry later."""


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


def _sanitize_provider_message(message: object, api_key: str) -> str:
    sanitized = str(message)
    if api_key:
        sanitized = sanitized.replace(api_key, "[REDACTED_API_KEY]")
    sanitized = re.sub(
        r"(?i)([?&]key=)[^&\s\"']+",
        r"\1[REDACTED_API_KEY]",
        sanitized,
    )
    sanitized = re.sub(r"https?://[^\s\"']+", "[REDACTED_URL]", sanitized)
    sanitized = sanitized.replace("\r", " ").replace("\n", " ")
    if len(sanitized) > _MAX_LOG_MESSAGE_LENGTH:
        sanitized = sanitized[:_MAX_LOG_MESSAGE_LENGTH] + "..."
    return sanitized


def _read_http_error_message(provider_error: error.HTTPError) -> str:
    try:
        response_body = provider_error.read()
    except (AttributeError, OSError, ValueError):
        response_body = b""

    if isinstance(response_body, bytes):
        message = response_body.decode("utf-8", errors="replace").strip()
    else:
        message = str(response_body).strip() if response_body else ""

    return message or str(provider_error.reason)


def _is_retryable_request_error(provider_error: BaseException) -> bool:
    if isinstance(provider_error, error.URLError):
        return True
    return isinstance(provider_error, (TimeoutError, ConnectionError))


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, comparison: ComparisonFacts) -> str:
        return self.generate_text(
            SYSTEM_PROMPT,
            json.dumps(
                comparison.model_dump(),
                separators=(",", ":"),
            ),
        )

    def generate_text(self, system_prompt: str, user_text: str) -> str:
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_text,
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

        for attempt in range(_MAX_RETRIES + 1):
            try:
                with request.urlopen(http_request, timeout=30) as response:
                    response_payload = json.load(response)
                break
            except error.HTTPError as provider_error:
                should_retry = provider_error.code in _RETRYABLE_HTTP_STATUS_CODES
                if should_retry and attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "Gemini request returned transient HTTP status=%s; "
                        "retrying in %s seconds",
                        provider_error.code,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                logger.error(
                    "Gemini request failed: HTTP status=%s, response=%s",
                    provider_error.code,
                    _sanitize_provider_message(
                        _read_http_error_message(provider_error),
                        self.api_key,
                    ),
                )
                raise ProviderError("The AI provider request failed.") from provider_error
            except (error.URLError, OSError, TimeoutError) as provider_error:
                if _is_retryable_request_error(provider_error) and attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "Gemini request failed with a transient network error; "
                        "retrying in %s seconds",
                        delay,
                    )
                    time.sleep(delay)
                    continue

                logger.error(
                    "Gemini request failed before receiving an HTTP response: %s",
                    _sanitize_provider_message(str(provider_error), self.api_key),
                )
                raise ProviderError("The AI provider request failed.") from provider_error
            except ValueError as provider_error:
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
    return _run_with_concurrency_limit(
        lambda: _get_provider().generate(comparison)
    )


def generate_chat_response(system_prompt: str, user_text: str) -> str:
    return _run_with_concurrency_limit(
        lambda: _get_provider().generate_text(system_prompt, user_text)
    )


def _run_with_concurrency_limit(call):
    """Run a provider call under the global concurrency bound (M4.4).

    Non-blocking acquire: when the bound is reached the caller gets
    ProviderBusyError immediately (mapped to 429 by main.py) instead of
    queueing behind an unbounded pile of in-flight provider requests.
    """
    if _concurrency_semaphore is None:
        return call()

    acquired = _concurrency_semaphore.acquire(blocking=False)
    if not acquired:
        raise ProviderBusyError(
            "The AI service is at its concurrent request limit. "
            "Please retry shortly."
        )
    try:
        return call()
    finally:
        _concurrency_semaphore.release()
