# M3 Evidence — Phase 8 ops visibility (2026-11-17)

## TDD cycle
- RED: `TestOpsVisibility` (4 tests) in `test_source_provenance_api.py` +
  2 tests in `test_auth_security.py::TestProtectedRoutesWhenAuthOn` — first
  run: endpoints missing (404) / 401 assertions unmet.
- GREEN:
  - `schemas/provenance.py`: `IngestionRunResponse`,
    `PublicationBatchResponse` (column-for-column with migration v4 DDL).
  - `services/source_service.py`: `OpsTableUnavailableError`;
    `_ops_rows` (table+column allow-lists, deterministic ORDER BY, bounded
    limit, existence probe → fail-closed 503 upstream);
    `list_ingestion_runs` / `list_publication_batches`.
  - `main.py`: `/ops/ingestion-runs`, `/ops/publication-batches` with
    `limit: int = Query(ge=1, le=100)` and
    `_user_id: int | None = Depends(require_auth)`.
- One expectation fix during GREEN: `limit=500` → 422 (FastAPI validation
  rejects rather than clamps); test pins 422 + default full read.

## Verification
- `test_source_provenance_api.py`: 25 passed.
- `test_auth_security.py`: 21 passed (ops endpoints 401 unauthenticated when
  auth ON; authenticated reads reach the handler — 503 on the pre-v4
  in-memory schema, asserted).
- Full backend (CI-parity): **1362 passed, 2 skipped, 2 deselected**.
- Middleware (rate limit, metrics, security headers) applies automatically;
  no CSP/header changes; no new dependencies.

## Files
- backend/app/schemas/provenance.py (+2 response models)
- backend/app/services/source_service.py (ops visibility readers)
- backend/app/main.py (+2 endpoints)
- backend/app/test_source_provenance_api.py (+4 tests)
- backend/app/test_auth_security.py (+2 tests)
- docs/m3/M3_OPS_VISIBILITY.md
