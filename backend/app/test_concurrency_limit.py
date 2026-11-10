"""M4.4 concurrency limit and retry-safety tests for the provider layer.

Covered:
- The concurrency bound: calls beyond the limit get ProviderBusyError
  immediately (no queueing behind a slow provider).
- The semaphore is released after success AND after failure (no leak).
- Limit disabled (SPECTRA_AI_CONCURRENCY=0) passes everything through.
- The bound is per-process (shared across AI endpoints), matching the
  one-container deployment.
"""

import threading
import time

import pytest

from backend.app.services import explanation_service as es


@pytest.fixture
def fresh_limit(monkeypatch):
    """Rebuild the semaphore with a known limit for each test."""
    def _make(limit: int):
        monkeypatch.setattr(es, "_CONCURRENCY_LIMIT", limit)
        sem = (
            threading.BoundedSemaphore(limit) if limit > 0 else None
        )
        monkeypatch.setattr(es, "_concurrency_semaphore", sem)
        return sem
    return _make


class TestConcurrencyLimit:
    def test_bound_rejected_when_full(self, fresh_limit):
        fresh_limit(1)
        sem = es._concurrency_semaphore

        # Simulate one in-flight call.
        acquired = sem.acquire(blocking=False)
        assert acquired

        with pytest.raises(es.ProviderBusyError, match="concurrent request limit"):
            es._run_with_concurrency_limit(lambda: "unused")

        sem.release()

    def test_call_allowed_within_bound(self, fresh_limit):
        fresh_limit(2)
        result = es._run_with_concurrency_limit(lambda: "ok")
        assert result == "ok"

    def test_semaphore_released_after_success(self, fresh_limit):
        fresh_limit(1)
        for _ in range(3):
            assert es._run_with_concurrency_limit(lambda: "ok") == "ok"

    def test_semaphore_released_after_failure(self, fresh_limit):
        fresh_limit(1)

        def failing():
            raise RuntimeError("provider exploded")

        for _ in range(3):
            with pytest.raises(RuntimeError, match="provider exploded"):
                es._run_with_concurrency_limit(failing)

        # The bound must still accept calls: no leaked permits.
        assert es._run_with_concurrency_limit(lambda: "ok") == "ok"

    def test_disabled_limit_passes_everything(self, fresh_limit):
        fresh_limit(0)  # disabled
        assert es._concurrency_semaphore is None
        for _ in range(10):
            assert es._run_with_concurrency_limit(lambda: "ok") == "ok"

    def test_concurrent_calls_bounded(self, fresh_limit):
        limit = 2
        fresh_limit(limit)

        in_flight = 0
        max_in_flight = 0
        lock = threading.Lock()
        busy_errors = []

        def slow_call():
            nonlocal in_flight, max_in_flight
            with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            time.sleep(0.05)
            with lock:
                in_flight -= 1
            return "ok"

        def worker():
            try:
                es._run_with_concurrency_limit(slow_call)
            except es.ProviderBusyError:
                with lock:
                    busy_errors.append(1)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert max_in_flight <= limit
        assert len(busy_errors) == 8 - limit  # the excess were refused


class TestProviderBusyErrorMapping:
    def test_busy_error_is_a_runtime_error(self):
        assert issubclass(es.ProviderBusyError, RuntimeError)

    def test_distinct_from_unavailable(self):
        # 429 (busy) must not be caught by the 503 (unavailable) handler.
        assert not issubclass(es.ProviderBusyError, es.ProviderUnavailableError)
