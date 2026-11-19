# M3 Evidence — Phase 7 UX (2026-11-17)

## TDD cycle

### Backend (provenance API coverage)
- RED: `backend/app/test_source_provenance_api.py` gained
  `TestBuildPlannerCategoryProvenance` (5 tests) written first — failed with
  `ProvenanceValidationError: unknown provenance table: 'psu_specifications'`
  (write path) and empty `fields` (read path).
- GREEN:
  - `services/provenance_service.py` + `services/base_import_provenance.py`:
    VALID_FIELDS extended with the four category tables (alignment test pins
    the maps together).
  - `services/source_service.py`: SPEC_FIELD_ORDER extended;
    `_SPEC_TABLE_TO_RELATIONSHIP` map added; `get_hardware_provenance`
    eager-loads 6 relationships; `_TYPE_TABLES` routes each type;
    `_spec_value` resolves through the map.
- Query-bound test updated 8 → 12 (constant; still does not scale with rows).
- Result: backend **1356 passed, 2 skipped, 2 deselected** (CI-parity).

### Frontend (transparency UI)
- RED: 6 new tests in `frontend/src/provenance.test.js` — first run failed
  with `does not provide an export named 'getHardwareSourceMeta'`.
- GREEN:
  - `provenance.js`: SPEC_SOURCE_KEYS + MOTHERBOARD/RAM/STORAGE/PSU maps
    (labels mirror detail.js view models exactly);
    `getHardwareSourceMeta` (defensive: malformed fields skipped, dates must
    match YYYY-MM-DD, max valid access_date across verified records,
    constant attribution notice).
  - `App.jsx`: `SourceTransparencyFooter` (completeness %, last verified,
    attribution; renders nothing when provenance absent) wired into
    CpuDetailView / GpuHardwareDetail / GenericCategoryDetailView.
  - `App.css`: `.source-transparency-footer` using existing Neural Luxury
    tokens only.
- One test-expectation fix during GREEN: a single malformed access date
  yields `lastVerifiedOn: null` (honest absence); the test now pins both
  the skip-malformed-keep-valid case and the all-malformed case.
- Result: frontend **680 passed** (`node --test src/*.test.js`).

## Verification
- `python -m pytest backend -q <CI-parity>`: 1356 passed, 2 skipped, 2 deselected.
- `node --test src/*.test.js`: 680 pass / 0 fail.
- `npx oxlint src`: 4 warnings, all pre-existing (untouched effects/hooks);
  0 new.
- `npx vite build`: ✓ built (374.60 kB js / 123.95 kB css).
- No CSP/security-header changes; no new runtime dependencies
  (node_modules reinstalled from lockfile only).

## Files
- backend/app/services/{source_service,provenance_service,base_import_provenance}.py
- backend/app/test_source_provenance_api.py (+5 tests, query-bound updated)
- frontend/src/provenance.js (+4 category maps, getHardwareSourceMeta)
- frontend/src/provenance.test.js (+6 tests)
- frontend/src/App.jsx (SourceTransparencyFooter + 3 detail views)
- frontend/src/App.css (footer styles)
- docs/m3/M3_UX_IMPLEMENTATION.md
