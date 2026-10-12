# Batch 015 — Independent audit

Method: `audit_batch015.py` opens the pre-change backup and the live database
**read-only** and compares them. It writes `_audit_result.json` and exits
non-zero on any failure. Result: **PASS (29/29 checks)**.

- Pre-change backup SHA-256: `401a3974586265804ed55f07a998adfafbc3dd7eb46f2f226e3a32e3eabd9035`
- Post-change live SHA-256: `9aee08794eeaf0ddabcaaed3b0462e8116aa5f1a339414dd12244e1ecd7b0160`
- `PRAGMA integrity_check`: ok
- `PRAGMA foreign_key_check`: 0 violations

## Checks

**Content is unchanged (8).** Every row of `hardware`, `cpu_specifications`,
`gpu_specifications`, `benchmark_results`, `external_identifiers`,
`field_provenance`, `build_conversations` and `build_messages` is identical
before and after. Counts: 5,380 / 3,501 / 1,879 / 1,040 / 3,575 / 36,946 / 5 /
10.

**Source identity preserved (1).** `sources(id, name, url)` is unchanged; 9 rows
before and after. Nothing renamed, remapped or deleted.

**Schema is additive only (10).** The eight unchanged tables keep identical
columns. `sources` gained exactly the eight expected nullable columns, and no
others.

**Integrity (2).** `integrity_check = ok`; zero foreign-key violations.

**Licence metadata (3).** All nine sources have a `license_status` drawn from
`{clear, unknown, restricted, unresolved}`, and **all four** distinctions are
present:
`1 restricted · 2 unknown · 3 restricted · 4 clear · 5 clear · 6 unknown ·
7 unresolved · 8 unknown · 9 unknown`.

**Provenance integrity (2).** Zero provenance rows reference a missing source;
the provenance count is unchanged at 36,946.

**API surface (2).** The four new routes are registered, and
`BenchmarkResultResponse` fields are exactly
`{id, hardware_id, benchmark_name, score, unit, test_type, source, recorded_at}`
— the pre-existing benchmark contract is unchanged.

## Why the database hash changed

The SHA-256 necessarily differs: the live database gained eight columns and 55
populated metadata values across the nine `sources` rows. That is the *only*
change; every content table is byte-identical row-by-row.

## Test and build evidence

- Backend: `pytest backend` → **661 passed** (was 642; +16 source-provenance API
  tests, +3 migration/seed tests).
- Frontend: `node --test "src/*.test.js"` → **544 passed** (was 537; +7
  provenance view-model tests).
- Lint: `oxlint` → **1 warning**, the pre-existing
  `react(set-state-in-effect)` in `App.jsx` (`setVisibleCount` effect). No new
  warnings.
- Production build: `vite build` → success.

## Limitations / risks (stated honestly)

- This is a data-transparency audit, **not a legal review**. `license_status`
  records the repository's best evidence; it is not legal advice.
- The audit verifies equality against **this** backup
  (`data/backups/spectra.db.batch015-20261012T062934Z.bak`), not against an
  external source of truth.
- No browser (Playwright/axe) or Docker end-to-end validation was executed for
  this batch; UI behaviour is covered by pure view-model tests and the
  production build only.
- Source 7 and the `unknown` sources remain unresolved by design; the batch
  makes that visible rather than guessing.
