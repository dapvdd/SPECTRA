"""Metrics middleware tests — counters, latency, cardinality safety.

Covered:
- The collector counts requests against the route TEMPLATE, not the raw path
  (two different hardware IDs aggregate under one route entry).
- 4xx and 5xx responses are counted in their own status classes.
- Latency samples are bounded (no unbounded growth).
- No request bodies, query strings, or IDs appear in the snapshot.

The /metrics endpoint itself is exercised in backend/app/test_observability.py
against the real app; these tests target the collector directly so a route
name collision in the test app cannot shadow it.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.middleware.metrics import (
    MetricsCollector,
    MetricsMiddleware,
    install_metrics_middleware,
)


def _app():
    app = FastAPI()

    @app.get("/hardware/{hardware_id}")
    def hw(hardware_id: int):
        return {"id": hardware_id}

    @app.get("/boom")
    def boom():
        raise HTTPException(status_code=503, detail="nope")

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="nope")

    from backend.app.middleware.metrics import collector

    @app.get("/metrics")
    def metrics():
        return collector.snapshot()

    install_metrics_middleware(app)
    return app


@pytest.fixture
def client():
    return TestClient(_app())


class TestMetricsEndpoint:
    def test_counts_requests(self, client):
        client.get("/hardware/1")
        client.get("/hardware/2")
        snap = client.get("/metrics").json()

        assert snap["total_requests"] >= 2
        # Route template aggregates both IDs under one entry.
        hw_routes = [k for k in snap["routes"] if "hardware_id" in k]
        assert len(hw_routes) == 1
        assert snap["routes"][hw_routes[0]]["count"] >= 2

    def test_status_classes_counted(self, client):
        client.get("/boom")      # 503
        client.get("/missing")   # 404
        snap = client.get("/metrics").json()

        classes = snap["status_classes"]
        assert classes.get("5xx", 0) >= 1
        assert classes.get("4xx", 0) >= 1  # /missing → 404
        assert classes.get("2xx", 0) >= 1  # /metrics scrape itself

    def test_latency_present(self, client):
        client.get("/hardware/7")
        snap = client.get("/metrics").json()
        entry = next(
            v for k, v in snap["routes"].items() if "hardware_id" in k
        )
        assert "latency_ms" in entry
        assert entry["latency_ms"]["avg"] >= 0
        assert entry["latency_ms"]["p50"] >= 0
        assert entry["latency_ms"]["p95"] >= entry["latency_ms"]["p50"] - 0.01


class TestCardinalitySafety:
    def test_bounded_latency_samples(self):
        c = MetricsCollector(max_samples=8)
        for i in range(200):
            c.observe("/route", 200, 0.001)
        route = c.routes["/route"]
        assert len(route["latency"]) == 8
        assert route["count"] == 200

    def test_route_flood_folds_into_other(self):
        c = MetricsCollector()
        for i in range(100):
            c.observe(f"/flood/{i}", 200, 0.001)
        assert len(c.routes) <= 64 + 1  # tracked routes + _other bucket
        assert c.routes["_other"]["count"] == 100 - 64

    def test_no_query_strings_or_bodies_recorded(self, client):
        client.get("/hardware/123?q=secret-search&token=abc")
        snap = client.get("/metrics").json()
        raw = repr(snap)
        assert "secret-search" not in raw
        assert "token=abc" not in raw
        assert "123" not in [k for k in snap["routes"]]
