"""Opt-in API rate limiting and cost-control middleware for SPECTRA.

Design
------
- Disabled by default so existing behaviour (and the existing test suite) is
  unchanged until the operator opts in.
- Enabled with ``SPECTRA_RATE_LIMIT_ENABLED=1``.
- Per-client fixed-window limiter keyed by ``X-Forwarded-For`` / remote IP.
- Two limit classes are configurable:

  * ``SPECTRA_RATE_LIMIT_PUBLIC`` — applies to every request (a safe
    lower bound for anything the frontend might poll).
  * ``SPECTRA_RATE_LIMIT_AI`` — applies to the expensive AI endpoints
    (``/comparison/explanation``, ``/hardware/chat``, ``/build/chat`` and the
    build conversation ``turn`` / ``messages`` write endpoints), the
    likely cost centre.

- When disabled, the middleware passes every request through untouched.
- Exceeding a limit returns ``429 Too Many Requests`` with a ``Retry-After``
  header, and a JSON detail that names the class that was exceeded.

Explicitly NOT a security boundary on its own: without authentication a
distributed client can rotate IPs. Treat this as a cost-control knob for a
single-user / small-team self-hosted deployment, not as a login gate.
"""

import os
import time
from collections import defaultdict, OrderedDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

AI_ENDPOINT_PREFIXES = (
    "/comparison/explanation",
    "/hardware/chat",
    "/build/chat",
    "/build/conversations",
)

DEFAULT_PUBLIC_LIMIT_PER_MINUTE = 240
DEFAULT_AI_LIMIT_PER_MINUTE = 30

_WINDOW_SECONDS = 60
_DEFAULT_COST_SAFETY = None

# Bounded limiter memory: evict least-recently-used buckets beyond this count.
_MAX_BUCKETS = 4096


def _env_int(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(int(raw), 0)
    except ValueError:
        return default


def _is_enabled() -> bool:
    return os.getenv("SPECTRA_RATE_LIMIT_ENABLED", "0").strip() in {"1", "true", "yes"}


def _trusted_proxy_ips() -> frozenset[str]:
    """IPs allowed to set X-Forwarded-For.

    When SPECTRA_TRUSTED_PROXIES is empty/unset, no proxy header is trusted and
    the limiter keys on the direct peer (safe default for a self-hosted app).
    """
    raw = os.getenv("SPECTRA_TRUSTED_PROXIES", "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


class _SlidingWindowLimiter:
    """Per-key fixed-window counter with LRU eviction of dead buckets."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, int], int] = defaultdict(int)
        self._window_started: OrderedDict[tuple[str, int], float] = OrderedDict()

    def allow(self, key: str, limit: int) -> int:
        """Return 0 when allowed, else seconds until the window resets."""
        if limit <= 0:
            return 0

        bucket = (key, limit)
        now = time.monotonic()
        started = self._window_started.get(bucket)

        if started is None or now - started >= _WINDOW_SECONDS:
            self._window_started[bucket] = now
            self._hits[bucket] = 1
        elif self._hits[bucket] >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - started)) + 1)
            return retry_after
        else:
            self._hits[bucket] += 1

        # Evict when the table exceeds the bound. The bucket touched just now
        # is moved to the end of the OrderedDict (most-recently-used) so the
        # eviction walks genuinely cold buckets first.
        self._window_started.move_to_end(bucket)

        while len(self._window_started) > _MAX_BUCKETS:
            stale, _ = self._window_started.popitem(last=False)
            self._hits.pop(stale, None)

        return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Opt-in per-IP rate limiting. Disabled unless explicitly configured."""

    def __init__(
        self,
        app,
        public_limit: int | None = None,
        ai_limit: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = _is_enabled() if enabled is None else enabled
        self.public_limit = (
            public_limit
            if public_limit is not None
            else _env_int(
                "SPECTRA_RATE_LIMIT_PUBLIC",
                DEFAULT_PUBLIC_LIMIT_PER_MINUTE,
            )
        )
        self.ai_limit = (
            ai_limit
            if ai_limit is not None
            else _env_int(
                "SPECTRA_RATE_LIMIT_AI",
                DEFAULT_AI_LIMIT_PER_MINUTE,
            )
        )
        self._limiter = _SlidingWindowLimiter()

    def _identify_client(self, request) -> str:
        """Rate-limit key.

        Trusted-proxy aware: only when the immediate peer is in the configured
        trusted set, take the left-most X-Forwarded-For entry (the value added
        by the first untrusted hop is ignored). Otherwise fall back to the
        direct peer host name.
        """
        forwarded = request.headers.get("x-forwarded-for", "")
        remote = request.client.host if request.client else None

        trusted = _trusted_proxy_ips()
        if forwarded and remote in trusted:
            return forwarded.split(",")[0].strip()

        # X-Forwarded-For is present? Ignore it: not trusted. Use direct peer.
        return remote or "unknown"

    def _limit_for(self, path: str) -> int:
        if self.ai_limit is not None and path.startswith(AI_ENDPOINT_PREFIXES):
            return self.ai_limit
        return self.public_limit or 0

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)

        key = self._identify_client(request)
        limit = self._limit_for(request.url.path)

        if limit:
            retry_after = self._limiter.allow(key, limit)
            if retry_after:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            "Rate limit exceeded. Please wait and try again "
                            "shortly."
                        ),
                        "rate_limit": {
                            "window_seconds": _WINDOW_SECONDS,
                            "retry_after_seconds": retry_after,
                        },
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)


def install_rate_limit_middleware(app, **kwargs):
    """Attach the middleware to a FastAPI app with the given overrides.

    Used by ``main.py`` so the middleware is wired exactly once at module load,
    and by tests to construct isolated limiters without touching ``main.py``.
    """
    app.add_middleware(RateLimitMiddleware, **kwargs)
    return app
