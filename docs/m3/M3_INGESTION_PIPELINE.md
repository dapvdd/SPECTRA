# M3 Ingestion Pipeline (Phases 2 & 4 — normative reference)

**Date**: 2026-11-16
**Implementation**: `backend/app/scripts/m3_adapters.py`,
`backend/app/scripts/enrichment_pipeline.py` (field-map extension),
`backend/app/identity/lifecycle.py`, `backend/app/publishing/publisher.py`

## 1. Pipeline stages

```
Curated CSV / prepared rows
        │  (human-verified citations; zero network I/O)
        ▼
SourceAdapter (WikipediaCuratedAdapter | ManualOfficialCitationAdapter)
        │  AcquiredValue[] — per-value provenance
        ▼
validate_acquisitions / m3_validation.validate_record   [fail-closed]
        │
        ▼
Lifecycle: DISCOVERED → EXTRACTED → NORMALIZED → VALIDATED → APPROVED
        │  (explicit approver required; no jump transitions)
        ▼
publish_batch (transactional, idempotent, dry-run-able)
        │
        ▼
PUBLISHED  (or QUARANTINED / REJECTED / SUPERSEDED)
```

## 2. Adapter declarations (mission §4 contract)

| Declaration | WikipediaCuratedAdapter | ManualOfficialCitationAdapter |
|---|---|---|
| Source identifier | `wikipedia-curated` | `manual-official-citation` |
| Publisher | Wikimedia contributors | per-record vendor |
| Allowed access mechanism | Human curation; citations stored (REST API allowed for future automation, polite UA) | Human reads the official page; URL stored as citation; **no crawling** |
| License/access policy | CC BY-SA 4.0 — `clear` | site terms — `unknown` (honest) |
| Supported categories | RAM, Storage, Motherboard, PSU | RAM, Storage, Motherboard, PSU |
| Parser version | `m3_adapters.py` module (git-tracked) | same |
| Fetch timestamp | `retrieved_at` per AcquiredValue (UTC ISO) | same |
| Source document identifier | citation URL + revision id | citation URL |
| Source URL | per-record `citation_url` | per-record `citation_url` |
| Response metadata | revision id, access date | access date |
| Raw source checksum | n/a (no fetch; the citation is the identifier) | n/a |
| Extraction confidence | `high` (human-verified) | `high` (human-verified) |

## 3. LLM usage boundary

No LLM participates in any extraction path in M3. The adapters transform
human-prepared rows; every hardware fact carries a human-verified citation.
(If an LLM extraction assistant is added later, it may only propose values;
the human verification step remains mandatory and the provenance columns do
not change meaning.)

## 4. Acquisition requirements (mission §4) — status

| Requirement | Status |
|---|---|
| Bounded concurrency | n/a (no network I/O in M3 adapters) |
| Configurable rate limits | n/a (same); mandatory for any future automated adapter |
| Exponential backoff / retry ceilings / timeouts | n/a (same) |
| Structured logs | pipeline uses backend logging config; runs audited in `ingestion_runs` |
| No secret logging | publisher logs contain no credentials (only paths/counts) |
| No anti-bot bypass / no unauthorized crawling | structural: adapters fetch nothing |
| Respect source restrictions | SourceLicenseGate semantics inherited; PassMark/TechPowerUp never touched |
| Deterministic extraction | adapters are pure functions over prepared rows |
| Every field linked to evidence | enforced by publisher (a populated field without provenance aborts the batch) |

## 5. Publication contract (mission §6)

- **Lifecycle gate**: only APPROVED records publish; every other state is
  rejected with a recorded reason.
- **Requirements checklist** (`PUBLICATION_REQUIREMENTS`): valid identity,
  verifiable source, required category fields, passing validation, no
  blocking conflict, explicit approval, publication batch — all must hold.
- **Dry-run**: `dry_run_batch` reports `would_publish` +
  `provenance_rows_planned` and writes nothing (deterministic).
- **Transactional**: one `BEGIN…COMMIT` per batch; failure rolls back all
  staged records and marks the run `rolled_back`.
- **Idempotent**: re-publishing the same canonical keys reports
  `skipped_existing` and never duplicates records or provenance rows.
- **Audit**: every run writes `ingestion_runs`; every publication writes
  `publication_batches` (batch_no, approver, counts, timestamps).
- **Rollback**: batch records live in `publication_batches`; per-batch
  rollback is a documented delete-by-batch_no on a dev copy (rollback of a
  *published* batch on any shared database requires explicit approval —
  consistent with the safety contract).
- **Referenced-record safety**: SUPERSEDED (never hard delete) keeps
  build/build_conversation FK references valid.

## 6. Test evidence

- `backend/app/scripts/test_m3_adapters.py` — 8 tests (declarations, zero
  network, provenance carry).
- `backend/app/publishing/test_publisher.py` — 10 tests (dry-run, lifecycle
  gate, idempotency, transactionality, audit rows).
- `backend/app/identity/test_lifecycle.py` — 9 tests (transition table).
- Full backend: 1342 passed (CI-parity flags).
