"""Aggregate request metrics for SPECTRA.

A tiny, dependency-free in-process metrics collector. Purpose: give the
operator error counters and latency baselines (M3.3) without pulling in a
metrics stack or introducing high-cardinality labels.

Design
------
- Counters are per status class (2xx/3xx/4xx/5xx) and per route TEMPLATE
  (e.g. ``/hardware/{hardware_id}``), never per raw path — IDs would explode
  cardinality and leak user data into metrics.
- Latency samples are kept in a bounded deque (default 512) per route
  template; percentile math runs on demand at scrape time. This bounds memory
  regardless of traffic.
- No request bodies, headers, query strings, or user identifiers are ever
  recorded.
- Everything lives in process memory: restarting the container resets the
  counters, which is acceptable for a single-container deployment (documented
  in OBSERVABILITY_PLAN.md — this is a baseline, not a TSDB).

Exposed via ``GET /metrics`` (aggregate only, no secrets): totals, per-class
counts, per-route counts, and latency avg/p50/p95 for the hottest routes.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware


_MAX_LATENCY_SAMPLES = 512
_MAX_TRACKED_ROUTES = 64


class MetricsCollector:
    """Bounded, thread-safe-enough (GIL-atomic ops) in-process metrics."""

    def __init__(self, max_samples: int = _MAX_LATENCY_SAMPLES) -> None:
        self.max_samples = max_samples
        self.started_at = time.time()
        self.total_requests = 0
        self.status_classes: dict[str, int] = defaultdict(int)
        # route_template -> {"count": int, "latency": deque[float]}
        self.routes: dict[str, dict] = {}

    def observe(self, route_template: str, status_code: int, duration_s: float) -> None:
        self.total_requests += 1
        self.status_classes[f"{status_code // 100}xx"] += 1

        route = self.routes.get(route_template)
        if route is None:
            if len(self.routes) >= _MAX_TRACKED_ROUTES:
                # Untracked overflow: fold into a fixed bucket so memory stays
                # bounded even under route-flood conditions.
                route_template = "_other"
                route = self.routes.get(route_template)
                if route is None:
                    route = {"count": 0, "latency": deque(maxlen=self.max_samples)}
                    self.routes[route_template] = route
            else:
                route = {
                    "count": 0,
                    "latency": deque(maxlen=self.max_samples),
                }
                self.routes[route_template] = route

        route["count"] += 1
        route["latency"].append(duration_s)

    def snapshot(self) -> dict:
        """Aggregate view for the /metrics endpoint. Percentiles over the
        bounded sample window (not lifetime)."""

        def _percentile(samples: Deque[float], pct: float) -> float:
            if not samples:
                return 0.0
            ordered = sorted(samples)
            idx = min(int(len(ordered) * pct), len(ordered) - 1)
            return round(ordered[idx] * 1000, 2)  # ms

        routes_view = {}
        for template, data in list(self.routes.items())[:_MAX_TRACKED_ROUTES]:
            samples = data["latency"]
            routes_view[template] = {
                "count": data["count"],
                "latency_ms": {
                    "avg": round(sum(samples) / len(samples) * 1000, 2)
                    if samples
                    else 0.0,
                    "p50": _percentile(samples, 0.50),
                    "p95": _percentile(samples, 0.95),
                },
            }

        return {
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "total_requests": self.total_requests,
            "status_classes": dict(self.status_classes),
            "routes": routes_view,
        }


# Single process-wide collector. The middleware and the /metrics route share
# this instance; it is created at import time alongside the app.
collector = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record per-request status class and latency against the route template."""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Prefer the matched route template (low cardinality). Falls back to
        # the raw path only when no route matched (404 from the router).
        route = getattr(request.scope, "get", lambda *_: None)("route")
        template = getattr(route, "path", None) or "unmatched"

        collector.observe(template, response.status_code, duration)
        return response


def install_metrics_middleware(app) -> object:
    app.add_middleware(MetricsMiddleware)
    return app
