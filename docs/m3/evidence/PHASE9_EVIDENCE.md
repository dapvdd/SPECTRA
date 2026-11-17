# M3 Evidence — Phase 9 security & performance (2026-11-17)

## Review-driven findings (evidence first)

- **F-1 (Medium, fixed)**: `unit_checks('RAM', {'capacity_gb': 'abc'})` and
  `cross_field_checks('RAM', {'modules': '2', ...})` raised `TypeError`
  pre-fix (reproduced via direct Python calls before writing tests). One
  malformed record would abort a `publish_batch` transaction with an opaque
  traceback instead of being rejected with a reason — fail-closed violated.
- **F-2 (Low, pinned)**: ops endpoints SQL structure comes from module-level
  allow-lists; hostile `limit` values 422 at FastAPI validation; service
  helper refuses unknown tables structurally.
- **F-3 (None, pinned)**: M3 adapters do zero network I/O; pinned by AST
  scans + behavioral test with `socket.socket` refused.

## TDD cycle

- **RED**: `backend/app/test_m3_security.py` (18 tests) written first.
  First run: 8 failed / 10 passed. Failures = the 5 crash reproductions
  (malformed value + publisher batch) + 2 harness corrections (missing
  adapter import; `hardware_catalog_service.SessionLocal` is a separate
  module reference that must be patched alongside `main`/`source_service`).
  The injection probes, response-shape pins, AST pins, and (after the
  harness fix) query-count pins passed immediately — they pin existing
  correct behavior.
- **GREEN**: `backend/app/importers/m3_validation.py` — added
  `_type_check_failure` gate applied in `unit_checks` and both cross-field
  rules: only real int/float (bool explicitly excluded — it is an int
  subclass and would silently pass as 1) may enter comparisons; malformed
  values become blockers naming the field; `None` stays "absent".
  Result: 18 passed.
- **REGRESSION**: full backend with CI-parity flags —
  **1380 passed, 2 skipped, 2 deselected** (was 1362 before Phase 9; +18).

## Files

- `backend/app/test_m3_security.py` (new, 18 tests: injection probes,
  malformed values, publisher batch survival, zero-network pins, perf bounds)
- `backend/app/importers/m3_validation.py` (type gate; no behavior change
  for well-formed data — all 26 pre-existing validation tests still pass)
- `docs/m3/M3_SECURITY_REVIEW.md`, `docs/m3/M3_TEST_MATRIX.md`

## Verification transcript (key lines)

```
python -m pytest backend/app/test_m3_security.py -q        → 18 passed
python -m pytest backend -q --ignore=... --deselect=...    → 1380 passed, 2 skipped, 2 deselected
```

Pre-fix crash reproductions (recorded before the fix):

```
unit_checks('RAM', {'capacity_gb': 'abc'}) → TypeError: '<=' not supported
  between instances of 'int' and 'str'
cross_field_checks('RAM', {'modules': '2', 'capacity_gb': '32'}) → TypeError
  at capacity % modules
```

## Safety contract compliance

- Zero production contact: tests run on in-memory SQLite / tmp_path clones;
  the malformed-publisher test uses a tmp_path dev DB clone.
- No scanners installed; no intrusive probes; review = code inspection +
  in-process reproductions.
- CSP/security headers untouched; middleware tests green in the full run.
