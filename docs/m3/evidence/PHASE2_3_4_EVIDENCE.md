# M3 Evidence — Phases 2/3/4 (2026-11-16)

## Deliverables implemented (TDD RED → GREEN)
- **Phase 2 adapters** (`backend/app/scripts/m3_adapters.py` +
  `test_m3_adapters.py`, 8 tests): WikipediaCuratedAdapter (license `clear`,
  CC BY-SA 4.0, revision-carrying citations) + ManualOfficialCitationAdapter
  (license `unknown` recorded honestly, human-verified values,
  evidence_status='verified'). Zero network I/O by construction.
- **Phase 2 field map** (`enrichment_pipeline.py`): M3_FIELD_MAPS extends
  `field_for_acquisition` to RAM/STORAGE/MOTHERBOARD/PSU with the exact
  import-contract vocabularies; unknown fields still rejected. 34 existing
  pipeline tests pass unchanged (regression clean).
- **Phase 3 validation** (`backend/app/importers/m3_validation.py` +
  `test_m3_validation.py`, 20 tests): unit semantics (MT/s sanity for RAM,
  MB/s-vs-Gb/s bounds for storage, rated-watts floor for PSU, PCIe
  generation as vocabulary-not-compatibility), range checks, cross-field
  consistency (kit capacity divisibility, DIMM size sanity), critical vs
  optional missing-data classification, source conflict detection (same
  canonical_key + different facts → Conflict records, never merged),
  deterministic 0-100 quality scoring (completeness only).
- **Phase 4 lifecycle** (`backend/app/identity/lifecycle.py` +
  `test_lifecycle.py`, 9 tests): DISCOVERED→EXTRACTED→NORMALIZED→VALIDATED→
  APPROVED→PUBLISHED with QUARANTINED/REJECTED/SUPERSEDED terminals;
  no jump transitions; APPROVED requires explicit approver; machine-checkable
  PUBLICATION_REQUIREMENTS checklist.
- **Phase 4 publisher** (`backend/app/publishing/publisher.py` +
  `test_publisher.py`, 10 tests): deterministic dry-run (writes nothing),
  transactional batch commit, idempotent reimport (skipped_existing, no
  provenance duplication), lifecycle gate (non-APPROVED never publishes),
  provenance-required-per-field (fail-closed), ingestion_runs +
  publication_batches audit rows, production-path refusal.

## Verification commands
- `python -m pytest backend/app/importers/test_m3_validation.py backend/app/identity/test_lifecycle.py -q` → 37 passed
- `python -m pytest backend/app/scripts/test_m3_adapters.py backend/app/scripts/test_enrichment_pipeline.py backend/app/scripts/test_enrichment_pipeline_modes.py -q` → 47 passed
- `python -m pytest backend/app/publishing/test_publisher.py -q` → 10 passed
- Full backend (CI-parity): **1329 passed, 2 skipped, 2 deselected**

## Gate status
- Gate 2: two permitted adapters + deterministic manual-import workflow work
  end-to-end (map_record → acquire_values → pipeline field routing) — PASS
- Gate 3: invalid/conflicting/unsupported data cannot reach the approved set
  (validate_record fail-closed; provenance required for every populated
  field) — PASS (in-pipeline; exercised by publisher tests)
- Gate 4: no unreviewed publication (lifecycle gate), no duplicate records
  (canonical_key idempotency + provenance non-duplication) — PASS

## Safety
- Zero prod/staging writes; publisher refuses `data/spectra.db` path;
  adapters perform no network I/O; worktree-isolated commits only.
