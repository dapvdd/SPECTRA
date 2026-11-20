"""M3.1 Task 3 — Wikipedia REST client (the ONE permitted automated path).

Registry row M3-1 (docs/m3/M3_SOURCE_REGISTRY.md): Wikipedia (English) is
CC BY-SA 4.0 "clear", and the registry explicitly allows "REST API ... for
future automation with polite UA". This module is that automation, scoped
tightly to what M3.1 needs:

- resolve an article title to its current revision id + timestamp, so a
  curated citation can carry an immutable revision anchor;
- fetch nothing else; parse nothing else.

Everything a manufacturer page needs stays human-citation-only
(``ManualOfficialCitationAdapter`` — zero network I/O, enforced by pins in
``test_acquisition_adapters.py``).

Politeness contract (Wikimedia API etiquette):
- a descriptive User-Agent naming this project and a contact point;
- a minimum delay between successive requests (default 1.0 s);
- retry only retryable failures (network / 5xx / 429), exponential backoff
  from ``errors.retry_delay`` with capped jitter;
- classification of every failure via ``errors.classify_exception`` so the
  pipeline records WHY a fetch failed, uniformly.

The client never runs at import time and is never imported by the publisher
path; only an explicit curator/acquisition invocation constructs it.
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request

from backend.app.catalog.acquisition.errors import (
    SourceError,
    classify_exception,
    retry_delay,
    jitter_source,
)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

_DEFAULT_UA = (
    "SPECTRA-catalog-acquisition/1.0 "
    "(https://github.com/dapvdd/SPECTRA; davidcandra2006@gmail.com)"
)

# Politeness floor between two successive requests (seconds).
_DEFAULT_MIN_DELAY_S = 1.0

_MAX_RETRIES = 4


class WikipediaRestClient:
    """Minimal, polite Wikipedia action-API client.

    ``fetch`` is injectable for tests (callable(url, timeout) -> bytes);
    production uses ``urllib.request.urlopen``. No other I/O exists.
    """

    def __init__(
        self,
        *,
        user_agent: str = _DEFAULT_UA,
        min_delay_s: float = _DEFAULT_MIN_DELAY_S,
        max_retries: int = _MAX_RETRIES,
        fetch=None,
        jitter=jitter_source,
        timeout_s: float = 15.0,
    ) -> None:
        self.user_agent = user_agent
        self.min_delay_s = float(min_delay_s)
        self.max_retries = int(max_retries)
        self._fetch = fetch if fetch is not None else _urllib_fetch
        self._jitter = jitter
        self.timeout_s = float(timeout_s)
        self._last_request_monotonic: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def article_revision(self, title: str) -> dict:
        """Resolve an article title to {title, pageid, rev_id, rev_timestamp}.

        Raises ``SourceError`` (classified) on failure. Successive calls are
        separated by at least ``min_delay_s`` (politeness floor).
        """
        title = (title or "").strip()
        if not title:
            raise SourceError("empty article title", "not_found", retryable=False)
        params = urllib.parse.urlencode({
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvlimit": 1,
            "rvprop": "ids|timestamp",
            "format": "json",
            "formatversion": "2",
        })
        url = f"{WIKIPEDIA_API}?{params}"
        payload = self._get_json(url)
        return self._parse_revision(payload, title)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _polite_wait(self) -> None:
        now = time.monotonic()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            remaining = self.min_delay_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_monotonic = time.monotonic()

    def _get_json(self, url: str) -> bytes:
        last_error: SourceError | None = None
        for attempt in range(self.max_retries + 1):
            self._polite_wait()
            try:
                return self._fetch(url, self.timeout_s)
            except Exception as exc:  # noqa: BLE001 - classified below
                last_error = classify_exception(exc)
                if not last_error.retryable or attempt == self.max_retries:
                    raise last_error from exc
                delay = retry_delay(
                    attempt, jitter=self._jitter() if self._jitter else 0.0,
                )
                time.sleep(delay)
        raise last_error or SourceError("unreachable", "unknown")

    @staticmethod
    def _parse_revision(payload: bytes | dict, requested: str) -> dict:
        try:
            data = payload if isinstance(payload, dict) else json_loads(payload)
            pages = data["query"]["pages"]
            page = pages[0]
            if "missing" in page:
                raise SourceError(
                    f"article not found: {requested!r}", "not_found",
                    retryable=False,
                )
            rev = page["revisions"][0]
            return {
                "title": page.get("title", requested),
                "pageid": page.get("pageid"),
                "rev_id": int(rev["revid"]),
                "rev_timestamp": rev.get("timestamp", ""),
            }
        except SourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - classified below
            raise classify_exception(exc) from exc


def _urllib_fetch(url: str, timeout_s: float) -> bytes:
    """Production transport: GET with the polite UA, return response bytes.

    Kept as a module function (not a method) so tests can replace the whole
    transport without touching network code paths.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _DEFAULT_UA,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise SourceError(f"HTTP {status}", "http_status", status=status)
        return response.read()


def json_loads(payload: bytes) -> dict:
    import json

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"parse failure: {exc}", "parse") from exc
