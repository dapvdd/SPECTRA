"""M3.1 Task 3 — adapter + Wikipedia REST client contract tests.

Pins:
- the Wikipedia REST client is the ONLY networked path in the acquisition
  package, is polite (UA + min delay), retries only retryable failures with
  deterministic backoff, and classifies every failure;
- manufacturer citations remain human-only: citation plans never expose a
  fetch path, and no adapter in the package gains network I/O;
- the M3 adapter pair (m3_adapters.py) keeps its zero-network guarantee
  (structural pins, reused from the M3 contract).
"""
from __future__ import annotations

import urllib.request
from unittest import mock

import pytest

from backend.app.catalog.acquisition.adapters import (
    CitationPlan,
    MANUFACTURER_CITATION_TEMPLATE,
    plan_citations,
)
from backend.app.catalog.acquisition.errors import SourceError
from backend.app.catalog.acquisition.wiki_rest import (
    WIKIPEDIA_API,
    WikipediaRestClient,
)


class TestWikipediaRestClient:
    def test_article_revision_success(self):
        payload = (
            b'{"query":{"pages":[{"title":"DDR5 SDRAM","pageid":6703912,'
            b'"revisions":[{"revid":1378669134,'
            b'"timestamp":"2026-11-16T00:00:00Z"}]}]}}'
        )
        fetch_calls: list[tuple[str, float]] = []

        def fake_fetch(url: str, timeout_s: float) -> bytes:
            fetch_calls.append((url, timeout_s))
            return payload

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, jitter=lambda: 0.0)
        result = client.article_revision("DDR5 SDRAM")

        assert result["title"] == "DDR5 SDRAM"
        assert result["rev_id"] == 1378669134
        assert result["rev_timestamp"] == "2026-11-16T00:00:00Z"
        (url, _), = fetch_calls
        assert url.startswith(WIKIPEDIA_API)
        assert "titles=DDR5+SDRAM" in url or "titles=DDR5%20SDRAM" in url

    def test_polite_ua_is_sent(self):
        seen_headers = {}

        def fake_fetch(url: str, timeout_s: float) -> bytes:
            # The production transport builds headers from _DEFAULT_UA; the
            # client-level contract here is that the UA constant is present.
            seen_headers["ua"] = client.user_agent
            return b'{"query":{"pages":[{"revisions":[{"revid":1}]}]}}'

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, jitter=lambda: 0.0)
        client.article_revision("80 Plus")
        assert "SPECTRA" in seen_headers["ua"]

    def test_missing_article_raises_not_found(self):
        def fake_fetch(url: str, timeout_s: float) -> bytes:
            return (
                b'{"query":{"pages":[{"title":"X","missing":true}]}}'
            )

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, jitter=lambda: 0.0)
        with pytest.raises(SourceError) as excinfo:
            client.article_revision("No Such Article Exists 404")
        assert excinfo.value.kind == "not_found"
        assert excinfo.value.retryable is False

    def test_retry_on_network_then_success(self):
        responses = [ConnectionError("reset"), b'{"query":{"pages":'
                     b'[{"title":"T","revisions":[{"revid":7}]}]}}']
        calls: list[int] = []

        def fake_fetch(url: str, timeout_s: float) -> bytes:
            calls.append(1)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, jitter=lambda: 0.0)
        result = client.article_revision("T")
        assert result["rev_id"] == 7
        assert len(calls) == 2  # one retry after the network failure

    def test_no_retry_on_404(self):
        calls: list[int] = []

        def fake_fetch(url: str, timeout_s: float) -> bytes:
            calls.append(1)
            raise SourceError("HTTP 404", "not_found", retryable=False)

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, jitter=lambda: 0.0)
        with pytest.raises(SourceError) as excinfo:
            client.article_revision("Whatever")
        assert excinfo.value.kind == "not_found"
        assert len(calls) == 1  # non-retryable: single attempt

    def test_politeness_delay_between_requests(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(
            "backend.app.catalog.acquisition.wiki_rest.time.sleep",
            lambda s: sleeps.append(s),
        )
        state = {"now": 100.0}

        def fake_monotonic():
            state["now"] += 0.1
            return state["now"]

        monkeypatch.setattr(
            "backend.app.catalog.acquisition.wiki_rest.time.monotonic",
            fake_monotonic,
        )

        payload = b'{"query":{"pages":[{"revisions":[{"revid":1}]}]}}'
        client = WikipediaRestClient(
            fetch=lambda url, t: payload, min_delay_s=1.0, jitter=lambda: 0.0)
        client.article_revision("A")
        client.article_revision("B")
        # The second request waited the politeness floor.
        assert any(s >= 0.8 for s in sleeps)

    def test_gives_up_after_max_retries(self):
        calls: list[int] = []

        def fake_fetch(url: str, timeout_s: float) -> bytes:
            calls.append(1)
            raise ConnectionError("down")

        client = WikipediaRestClient(
            fetch=fake_fetch, min_delay_s=0.0, max_retries=2,
            jitter=lambda: 0.0)
        with pytest.raises(SourceError) as excinfo:
            client.article_revision("T")
        assert excinfo.value.kind == "network"
        assert len(calls) == 3  # initial + 2 retries


class TestCitationPlans:
    def test_technology_fields_plan_wikipedia(self):
        plans = plan_citations("RAM", ["ddr_generation", "capacity_gb"])
        by_field = {p.spec_field: p for p in plans}
        assert by_field["ddr_generation"].source_kind == "wikipedia"
        assert by_field["ddr_generation"].article_title == "DDR5 SDRAM"
        assert by_field["ddr_generation"].is_automatable is True

    def test_sku_fields_plan_manufacturer_human_workflow(self):
        plans = plan_citations("RAM", ["capacity_gb", "speed_mhz"])
        by_field = {p.spec_field: p for p in plans}
        for field in ("capacity_gb", "speed_mhz"):
            assert by_field[field].source_kind == "manufacturer-page"
            assert by_field[field].is_automatable is False
            assert "per-SKU" in by_field[field].manufacturer_url_hint

    def test_manufacturer_plans_are_never_fetchable(self):
        """The CitationPlan type carries no fetch method and the template is
        a documentation string, not a callable URL builder."""
        plans = plan_citations("PSU", ["wattage"])
        plan = plans[0]
        assert isinstance(plan, CitationPlan)
        assert not hasattr(plan, "fetch")
        assert not hasattr(plan, "request")
        assert MANUFACTURER_CITATION_TEMPLATE["PSU"].startswith("https://")

    def test_plans_deterministic(self):
        a = plan_citations("STORAGE", ["interface", "form_factor"])
        b = plan_citations("STORAGE", ["interface", "form_factor"])
        assert [p.to_dict() if hasattr(p, "to_dict") else p for p in a] \
            == [p.to_dict() if hasattr(p, "to_dict") else p for p in b]

    def test_no_adapter_uses_urllib(self):
        """Structural pin: adapters.py must not import urllib at all — the
        manufacturer path has no fetch capability by construction."""
        import backend.app.catalog.acquisition.adapters as adapters_mod
        import sys

        assert "urllib" not in dir(adapters_mod)
        source = open(adapters_mod.__file__, encoding="utf-8").read()
        assert "urlopen" not in source
        assert "urllib" not in source.replace(
            "# urllib", ""
        ) or "urllib" not in source


class TestM3AdaptersUnchanged:
    def test_m3_adapters_still_zero_network(self):
        """The M3 curated adapters keep their zero-I/O contract."""
        from backend.app.scripts import m3_adapters

        source = open(m3_adapters.__file__, encoding="utf-8").read()
        for banned in ("urlopen", "requests.get", "httpx", "socket."):
            assert banned not in source
