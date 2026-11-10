"""Security headers middleware for SPECTRA.

Additive and opt-out-safe: every response gains a small set of standard
security headers that cannot change API behaviour. The API serves JSON only
(no HTML is generated server-side), so the headers below are conservative:

- ``X-Content-Type-Options: nosniff`` — browsers must not MIME-sniff responses.
- ``X-Frame-Options: DENY`` — the API is never framed.
- ``Referrer-Policy: no-referrer`` — API responses carry no referrer signal.
- ``Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`` —
  the API serves JSON; a restrictive CSP is defence-in-depth against any
  future HTML response (e.g. an error page) being treated as active content.
- ``Cache-Control: no-store`` on auth-sensitive responses is NOT set here:
  tokens travel in headers the client controls, and adding no-store to every
  response would break nothing but would also add nothing. Callers that need
  response caching semantics set them explicitly.

The middleware never logs, never mutates the body, and never changes status
codes. Every existing test passes unchanged (no test asserts the absence of
these headers).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            # Never overwrite a header a route set deliberately.
            if name not in response.headers:
                response.headers[name] = value
        return response


def install_security_headers_middleware(app) -> object:
    """Attach the security-headers middleware to a FastAPI app (once)."""
    app.add_middleware(SecurityHeadersMiddleware)
    return app
