# M3 UX Implementation — Source Transparency for the Build Planner Categories (Phase 7)

**Date**: 2026-11-17
**Scope**: provenance API coverage for RAM/STORAGE/MOTHERBOARD/PSU + category
detail transparency UI (completeness, last-verified date, attribution notice)
**Design system**: Neural Luxury preserved (existing tokens, hairline borders,
readout typography). No new dependencies; no CSP/security-header changes.

## 1. What was missing

The Batch 015 source-transparency stack only covered CPU/GPU:

- `source_service.SPEC_FIELD_ORDER` enumerated only `cpu_specifications` /
  `gpu_specifications`, so `/hardware/{id}/provenance` returned **no fields at
  all** for the four M2 categories (the response had `fields: []`).
- `provenance_service.VALID_FIELDS` (and its mirror
  `base_import_provenance.VALID_FIELDS`) rejected the four new spec tables, so
  even an enriched row could not carry provenance through the write path.
- `frontend/src/provenance.js` `SPEC_SOURCE_KEYS` mapped only CPU/GPU detail
  labels, so per-spec source disclosures never rendered on category pages.
- No completeness / last-verified / attribution surface existed anywhere.

## 2. Backend changes

### `services/source_service.py`
- `SPEC_FIELD_ORDER` extended with the four category tables (exact column
  lists from migration v3).
- New `_SPEC_TABLE_TO_RELATIONSHIP` map; `get_hardware_provenance` now eager
  loads all six spec relationships (constant query count, still bounded —
  asserted by the updated `test_query_count_is_bounded...` ≤ 12 statements).
- `_TYPE_TABLES` routes each `hardware.type` to `["hardware", <spec table>]`;
  unknown types degrade to `["hardware"]` (fail-soft, honest).
- `_spec_value` resolves the spec row through the relationship map.

### `services/provenance_service.py` + `services/base_import_provenance.py`
- Both `VALID_FIELDS` maps extended with the four tables. This is the single
  source of truth for writable provenance (table, column) pairs; the
  alignment test `test_valid_fields_match_provenance_service` pins the two
  maps together.

### `models/provenance.py`
- No change needed: `VALID_TABLES` (DB CHECK constraint) already contained the
  four tables since migration v3; only the service-layer allow-list lagged.

## 3. Frontend changes

### `provenance.js`
- `SPEC_SOURCE_KEYS` gains `MOTHERBOARD`, `RAM`, `STORAGE`, `PSU` maps whose
  keys mirror the labels in `detail.js` view models exactly
  (e.g. `"Rated Wattage" → ["psu_specifications", "wattage"]`,
  `"Sequential Read" → ["storage_specifications", "read_mb_s"]`).
  Both PSU spellings (`Rated Wattage` view-model label) are mapped.
- New `getHardwareSourceMeta(provenance)`: defensive, pure — returns
  `{ hasProvenance, totalFields, verifiedFields, unattributedFields,
  lastVerifiedOn, attribution }`. Malformed fields are skipped; access dates
  must match `YYYY-MM-DD` or are ignored; `lastVerifiedOn` is the max valid
  date across verified records; the attribution notice is the constant
  `"Specs verified against sources including Wikipedia (CC BY-SA 4.0)."`.

### `App.jsx`
- New `SourceTransparencyFooter` component: SOURCE TRANSPARENCY section with
  three rows — verified-fields completeness ("N of M shown fields carry a
  recorded source (P%)"), last-verified date, attribution. Renders nothing
  when provenance failed to load (supplementary, never blocking).
- Wired into all three detail views: `CpuDetailView`, `GpuHardwareDetail`,
  `GenericCategoryDetailView` (RAM/STORAGE/MOTHERBOARD/PSU).

### `App.css`
- `.source-transparency-footer` styled with existing tokens only
  (`--border-subtle`, `--surface-raised`, `--radius-md`), matching the
  Batch 015 `.benchmark-sources` visual register.

## 4. Tests (TDD)

### RED
- Backend: `TestBuildPlannerCategoryProvenance` (5 tests) — PSU/RAM field
  enumerations, honest unattributed/unavailable statuses, routing for
  STORAGE/MOTHERBOARD, summary consistency. First run: `unknown provenance
  table` + missing fields.
- Frontend: 6 new tests — label→field resolution per category,
  `getHardwareSourceMeta` contract + malformed-date/junk handling. First run:
  `does not provide an export named 'getHardwareSourceMeta'`.

### GREEN
- Backend 1356 passed, 2 skipped, 2 deselected (CI-parity flags) — includes
  the 5 new tests and the query-bound adjustment (8 → 12 statements after
  widening eager loads; still constant, does not scale with rows).
- Frontend 680 passed (`node --test src/*.test.js`), including 14 provenance
  tests.
- `npx oxlint src`: 4 warnings, all pre-existing (`set-state-in-effect` in
  untouched effects/hooks); no new warnings.
- `npx vite build`: succeeds (374.60 kB js / 123.95 kB css, unchanged form).

## 5. Honest limitations

1. The completeness percentage counts API-returned fields (has_value or not);
   it is a transparency readout, not a data-quality score (that is
   `m3_validation.quality_score`, surfaced in the admin endpoints, Phase 8).
2. `lastVerifiedOn` reflects recorded `access_date`s on verified records;
   records with malformed/missing dates cannot contribute (by design —
   nothing is invented).
3. The attribution notice is static; per-record attribution remains visible
   in the per-spec disclosures and the `/sources` registry.
