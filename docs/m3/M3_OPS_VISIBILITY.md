# M3 Ops Visibility — Admin Endpoints for the Ingestion Audit Trail (Phase 8)

**Date**: 2026-11-17
**Scope**: read-only `/ops/ingestion-runs` and `/ops/publication-batches`
endpoints surfacing the migration v4 ops tables
**Auth model**: unchanged — the existing feature-flagged `require_auth`
dependency (`SPECTRA_AUTH_ENABLED=1` → Bearer required; OFF → open, as every
other read endpoint). No new auth code, no role system invented.

## 1. Endpoints

| Endpoint | Method | Query | Response |
|---|---|---|---|
| `/ops/ingestion-runs` | GET | `limit` (1-100, default 50) | `list[IngestionRunResponse]` |
| `/ops/publication-batches` | GET | `limit` (1-100, default 50) | `list[PublicationBatchResponse]` |

Both:

- are **read-only** (no write path exists in the API for ops tables — the
  publisher writes them server-side inside `publish_batch` transactions);
- order newest-first (`ingestion_runs.id DESC`,
  `publication_batches.batch_no DESC`) — a visibility feed, not an export;
- are bounded: `limit` is validated by FastAPI (`ge=1, le=100`), violating
  values are a 422; the service clamps defensively a second time;
- **require a valid Bearer token when auth is ON** (401 otherwise), exactly
  like the AI/cost endpoints; auth-OFF behavior matches the public read
  endpoints;
- report **503 with a precise detail message** when the ops table does not
  exist (pre-v4 database) instead of a 500 traceback — fail-closed honesty.

## 2. Implementation

### `schemas/provenance.py`
- `IngestionRunResponse` / `PublicationBatchResponse`: mirror the migration
  v4 DDL column-for-column; nullable audit columns (`source_id`,
  `finished_at`, `published_at`, `notes`) stay optional because a running
  row has not finished yet.

### `services/source_service.py`
- New `OpsTableUnavailableError`.
- `_ops_rows(table, columns, order_column, limit)`: the ops tables have **no
  ORM models** (created by migration v4 DDL on databases the ORM may never
  touch), so the read goes through parameterless SQL with a hard column
  allow-list (`_INGESTION_RUN_COLUMNS` / `_PUBLICATION_BATCH_COLUMNS`), a
  table-name allow-list, deterministic ORDER BY, and an existence probe that
  raises `OpsTableUnavailableError` on absence.
- `list_ingestion_runs(limit)` / `list_publication_batches(limit)` — thin,
  documented wrappers.

### `main.py`
- The two GET endpoints above, each with `_user_id: int | None =
  Depends(require_auth)` following the existing protected-route pattern.

## 3. Tests (TDD)

### RED
- `TestOpsVisibility` (4 tests) written first: 404s — endpoints missing.
- `test_ops_endpoints_require_a_token` + `test_ops_endpoints_readable_with_token`
  in `test_auth_security.py::TestProtectedRoutesWhenAuthOn` (auth forced ON).

### GREEN
- `test_source_provenance_api.py`: 25 passed (includes table-existence
  contract, pre-v4 503 honesty, limit bounds/order, auth-off readability).
- `test_auth_security.py`: 21 passed — ops endpoints 401 without token when
  auth ON; with token, reach the handler (503 on pre-v4 schema, asserted).
- One test-expectation fix during GREEN: `limit=500` is a 422 (rejected by
  FastAPI validation), not a silent clamp — the test now pins the 422 plus
  the default (no-param) full read.
- Full backend (CI-parity flags): **1362 passed, 2 skipped, 2 deselected**.

## 4. Security review

- SQL surface: table and column names come from module-level allow-list
  constants, never from request input; the only interpolated value is
  `LIMIT :limit`, bound as a parameter. No injection path.
- No secrets, paths, or user data in the responses (approver identity and
  notes are operational metadata written by the publisher).
- Rate limiting / metrics / security-header middleware apply to the new
  routes automatically (app-level middleware, added before routing).
- CORS unchanged; CSP unchanged (these are API routes).
- Zero prod contact: endpoints only ever read the database the running app
  is configured for; M3 itself continues to write nothing outside dev DBs.

## 5. Honest limitations

1. No filtering by category/status yet — the feed is newest-first, bounded;
   a real admin UI would add filters (deferred: no admin UI exists yet).
2. `source_id` on ingestion runs is returned as-is (nullable); a joined
   source name would require a second query for marginal value here.
3. The 503-on-pre-v4 behavior is a transition aid; once all deployments run
   v4+ it is dead code (kept for honest degradation, harmless).
