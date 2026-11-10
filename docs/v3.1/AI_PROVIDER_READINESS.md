# SPECTRA V3.1 — AI Provider Readiness

Date: 2026-11-10
Scope: Gemini provider configuration, failure modes, concurrency control, and
the exact steps to activate AI features. Built in M4; production remains
unconfigured (activation is user-gated).

---

## 1. Current state

| Item | Production | Local dev (.env, gitignored) |
|---|---|---|
| `GEMINI_API_KEY` | empty → AI **unconfigured** | dummy test value only |
| `GEMINI_MODEL` | empty | `gemini-2.0-flash` |
| Effective state | All three AI endpoints return **503** with a safe message | AI-gated tests skip (2 skipped in the suite) |

## 2. Configuration states (reported by `/api/release` → `ai_provider_state`)

| State | Meaning | API behaviour |
|---|---|---|
| `unconfigured` | no key (and/or no model) | AI endpoints → **503** `Gemini API is not configured…` |
| `unusable` | key set but model missing, or model without key | AI endpoints → **503**; diagnostics point at the missing half |
| `configured` | key + model present | AI endpoints live; failures map per §3 |

The state string never contains the key value — leak-tested in
`test_v31_matrix.py::TestNoSecretLeakage` and `test_release.py`.

## 3. Failure-mode map (all three AI endpoints behave identically)

| Condition | HTTP | Source |
|---|---|---|
| Missing/empty key or model | **503** | `ProviderUnavailableError` → handler in `main.py` |
| Concurrency bound reached | **429** | `ProviderBusyError` (M4.4 semaphore, non-blocking acquire) |
| Provider 4xx/5xx after 3 retries (1s/2s/4s backoff) | **502** | `ProviderError` |
| Validation rejection | **422** | pydantic (`extra=forbid`, length/alternation limits) |

Defaults: `SPECTRA_AI_CONCURRENCY=4` (0 disables the bound); retries with
exponential backoff on {408, 429, 500, 502, 503, 504}; 30 s timeouts. The
prompt layer forbids invention (no fabricated metrics/percentages/benchmarks)
and responses never echo the key.

## 4. Concurrency bound (M4.4)

A process-wide `BoundedSemaphore` bounds in-flight provider calls so a slow or
hanging provider cannot pile up unbounded requests (each holds a worker thread
and a client connection). Beyond the bound, callers get an **immediate 429**
instead of queueing. The permit is released on success AND failure (leak-tested
by `test_concurrency_limit.py`, 8 tests, including a true concurrent test).

Per-process scope matches the one-container deployment; scale-out would need a
revisit (documented, not built).

## 5. Input limits (already enforced, tested)

- Chat history: ≤10 messages × ≤4000 chars
- Evidence items: ≤10 × ≤1000 chars
- Analysis items: ≤5 × ≤500 chars
- Question: ≤2000 chars, non-blank after strip
- `extra="forbid"` on every AI request model — unknown fields rejected

## 6. Activation runbook (USER-GATED — not executed)

1. Obtain a Gemini API key (Google AI Studio).
2. On the host, add to the backend environment (compose env / `.env`):
   `GEMINI_API_KEY=<real key>`, `GEMINI_MODEL=gemini-2.0-flash` — never commit
   the real value; `.env` is gitignored (verified via history).
3. Recreate the backend container (deployment approval required).
4. Verify: `GET /api/release` → `ai_provider_state: "configured"`; one real
   `/api/comparison/explanation` call returns 200 with a grounded answer.
5. Optional cost control: enable `SPECTRA_RATE_LIMIT_ENABLED=1` with
   `SPECTRA_RATE_LIMIT_AI=30` (see AUTHORIZATION_MATRIX.md §4).

Rollback: unset the two variables and recreate the container → endpoints
return 503 again (harmless to data).

## 7. Test coverage

| Area | Tests |
|---|---|
| 503 on missing key (all 3 endpoints) | `test_v31_matrix.py::TestAIEndpointFailureModes` |
| 429 on concurrency exhaustion (all 3 endpoints) | same + `test_concurrency_limit.py` |
| Semaphore leak-safety (success/failure paths) | `test_concurrency_limit.py` |
| Provider state strings + key non-leak | `test_release.py::TestProviderState` |
| Existing retry/sanitize/prompt behaviour | pre-existing suite (green, 1067→1095 total) |
