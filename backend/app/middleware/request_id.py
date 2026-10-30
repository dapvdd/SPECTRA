"""Request-ID middleware for SPECTRA.

Assigns a ``X-Request-ID`` header to every response so logs emitted during a
request can be correlated end to end (frontend --> API -- > AI provider).

Behaviour:
- If the request carries an upstream ``X-Request-ID`` (e.g. set by nginx or a
  load balancer), it is echoed on the response so the original ID is preserved.
- Otherwise a fresh UUID is generated and set on the response.
- The request ID is exposed to the request ``state`` as ``request_id`` so route
  handlers and services can include it in structured log ``extra`` payloads.
- The middleware never logs PII itself; it only forwards the ID.

Additive and safe: setting a response header cannot change behaviour or break
existing tests (no test asserts the absence of a header).
"""

from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every response and surface it on request state."""

    async def dispatch(self, request: Request, call_next):
        existing = request.headers.get(REQUEST_ID_HEADER.lower())
        request_id = existing or uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_request_id_middleware(app) -> object:
    """Attach the request-ID middleware to a FastAPI app (idempotent-safe)."""
    app.add_middleware(RequestIDMiddleware)
    return app
