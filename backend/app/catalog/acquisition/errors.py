"""M3.1 Task 2 — source error classification and deterministic retry math.

The acquisition pipeline talks to network-adjacent code paths (adapters in
Task 3). This module gives every failure a stable classification vocabulary
and a deterministic exponential backoff so retries are reproducible and
testable:

- ``SourceError`` carries a ``kind`` from a closed vocabulary;
- ``classify_exception`` maps any exception (including lower-level ones like
  ``socket.timeout`` or ``json.JSONDecodeError``) to that vocabulary;
- ``retry_delay`` computes exponential backoff (base 1.0 s, factor 2.0,
  cap 30.0 s) with an injectable jitter source — deterministic (0.0) by
  default so tests pin exact values.
"""
from __future__ import annotations

import random

ERROR_KINDS = (
    "network",
    "http_status",
    "parse",
    "blocked",
    "auth",
    "rate_limited",
    "not_found",
    "unknown",
)

_RETRYABLE_KINDS = frozenset(
    {"network", "rate_limited", "http_status", "unknown"}
)

_BACKOFF_BASE_S = 1.0
_BACKOFF_FACTOR = 2.0
_BACKOFF_CAP_S = 30.0


class SourceError(Exception):
    """A classified acquisition failure.

    ``kind`` is always one of ``ERROR_KINDS``; ``http_status`` carries the
    numeric status in ``status`` (None otherwise).
    """

    def __init__(
        self,
        message: str,
        kind: str = "unknown",
        *,
        status: int | None = None,
        retryable: bool | None = None,
    ) -> None:
        if kind not in ERROR_KINDS:
            raise ValueError(
                f"unknown SourceError kind {kind!r}; expected one of "
                f"{ERROR_KINDS}"
            )
        super().__init__(message)
        self.kind = kind
        self.status = status
        if retryable is None:
            retryable = kind in _RETRYABLE_KINDS
        self.retryable = retryable


# HTTP status -> error kind. 4xx (except 429) is not retryable; 5xx is.
_STATUS_KINDS_4XX = {
    401: "auth",
    403: "blocked",
    404: "not_found",
    429: "rate_limited",
}


def classify_exception(exc: BaseException) -> SourceError:
    """Map any exception to the closed ``SourceError`` vocabulary.

    Deterministic and total: an unclassifiable exception becomes
    ``kind='unknown'`` (never raises).
    """
    # Already-classified errors pass through unchanged.
    if isinstance(exc, SourceError):
        return exc

    text = str(exc).lower()
    name = type(exc).__name__.lower()

    # --- HTTPStatusError / requests.HTTPError style (httpx, requests) ---
    status = getattr(exc, "response", None)
    status_code = getattr(status, "status_code", None)
    if status_code is None:
        # urllib.error.HTTPError carries .code
        status_code = getattr(exc, "code", None)
    if status_code is None and hasattr(exc, "status"):
        status_code = getattr(exc, "status")

    if status_code is not None:
        code = int(status_code)
        if code == 429:
            return SourceError(f"HTTP {code}: rate limited", "rate_limited",
                               status=code)
        if code in _STATUS_KINDS_4XX:
            return SourceError(f"HTTP {code}", _STATUS_KINDS_4XX[code],
                               status=code)
        if 400 <= code < 500:
            return SourceError(f"HTTP {code}: client error", "http_status",
                               status=code, retryable=False)
        if 500 <= code < 600:
            return SourceError(f"HTTP {code}: server error", "http_status",
                               status=code, retryable=True)
        return SourceError(f"HTTP {code}", "http_status", status=code)

    # --- Timeouts / connection problems -> network ---
    if isinstance(exc, TimeoutError) or "timeout" in name or "timeout" in text:
        return SourceError(f"network timeout: {exc}", "network")
    if isinstance(exc, ConnectionError) or "connection" in name:
        return SourceError(f"connection failure: {exc}", "network")
    if "connection" in text or "getaddrinfo" in text or "unreachable" in text:
        return SourceError(f"network failure: {exc}", "network")

    # --- Parse failures -> parse ---
    if isinstance(exc, ValueError) and "json" in name or "json" in text:
        return SourceError(f"parse failure: {exc}", "parse")
    if "decode" in name or "parse" in name or "syntax" in name:
        return SourceError(f"parse failure: {exc}", "parse")

    # --- Authentication signals in message text ---
    if "unauthorized" in text or "api key" in text or "credentials" in text:
        return SourceError(f"authentication failure: {exc}", "auth")

    return SourceError(f"unclassified source failure: {exc}", "unknown")


def retry_delay(
    attempt: int,
    *,
    jitter: float = 0.0,
    base: float = _BACKOFF_BASE_S,
    factor: float = _BACKOFF_FACTOR,
    cap: float = _BACKOFF_CAP_S,
) -> float:
    """Exponential backoff for ``attempt`` (0-based): base * factor**attempt,
    capped, plus injected jitter.

    Deterministic when ``jitter`` is fixed (default 0.0). Callers may pass
    ``jitter=random.uniform(0, 1)`` for production jitter; the cap applies
    to the total (delay + jitter) so worst-case latency stays bounded.
    Non-positive attempt numbers are treated as attempt 0.
    """
    if attempt < 0:
        attempt = 0
    delay = min(base * (factor ** attempt), cap)
    total = delay + float(jitter)
    return min(total, cap)


def jitter_source() -> float:
    """Production jitter in [0, 1); tests inject their own value instead."""
    return random.random()
