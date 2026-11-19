# M3 PRD — Catalog Expansion & Data Dominance

**Date**: 2026-11-16
**Status**: Active (implementation contract)
**Parent mission**: SPECTRA M3 (§0-§16 of the mission directive)

## 1. Problem

SPECTRA's catalog is CPU/GPU-dominated: 5 380 of 5 389 production hardware
rows (99.83 %, verified in `M3_BASELINE_AUDIT.md` §2) are CPU or GPU. The four
Build Planner categories added in M2.5 (RAM, Storage, Motherboard, PSU) hold
only 9 demo rows in production and zero production-quality data. A six-slot
build planner without a real six-category catalog cannot serve users.

## 2. Goal

Deliver a reproducible, legally usable, provenance-backed catalog expansion
pipeline plus a verified real-world pilot dataset (stretch target 400 records,
100/category) for RAM/Storage/Motherboard/PSU — ready for independent merge
review, without touching production or existing staging.

## 3. Non-goals

- Production deployment or production/staging database writes.
- Merging to main; opening a non-draft PR.
- Scraping restricted sources (PassMark, TechPowerUp) or bypassing any
  access control.
- Automatic production ingestion scheduling.
- Case-clearance compatibility (no case/dimensional data exists).

## 4. Requirements (contract-level)

R1. Every published record carries field-level provenance to a registered
    source with a documented license status; `unknown`/`restricted` evidence
    is quarantined, never published.
R2. Identity is deterministic and documented: kit ≠ module, capacity variants
    are distinct SKUs, revisions may require separate identity, MPNs live in
    `external_identifiers`. Uncertain identities are never auto-merged.
R3. Validation is fail-closed: invalid, conflicting, or unsupported data
    cannot enter the approved publication set.
R4. Publication is transactional, idempotent, dry-run-able, batch-rollback-able,
    and audited; no record becomes PUBLISHED merely because a parser ran.
R5. Compatibility conclusions never silently expand beyond the M2.5 rule
    contract; UNKNOWN stays first-class; no false positives from imported data.
R6. The Neural Luxury design system and existing security headers/CSP are
    preserved; no new external runtime dependencies for browsing.
R7. SQLite schema compatibility with v3 is preserved; additions are additive
    migration v4+ with copy-first rehearsal.
R8. Unit semantics are explicit: MB/s vs Gb/s, MHz vs MT/s, TDP vs measured
    power, PCIe generation vs physical connector — never conflated.

## 5. Phases (map to mission §2-§13)

| Phase | Deliverable focus | Gate |
|---|---|---|
| 0 | Baseline audit + source feasibility + registry | ≥1 viable legal path per category, or documented block |
| 1 | Data contract + identity rules + schema additions (TDD) | Schema/identity/duplicate/migration-rehearsal tests pass |
| 2 | Source adapters (declarative, provenance-carrying) | ≥1 adapter or documented manual-import workflow end-to-end |
| 3 | Normalization & validation rules | Invalid data cannot reach the approved set |
| 4 | Quarantine & publication lifecycle | No unreviewed publication; no duplicate imports |
| 5 | Real-world catalog pilot (bounded batches 10→25→50→100) | Every published pilot record meets identity+provenance rules |
| 6 | Compatibility integration regression | No false-positive compatibility conclusions |
| 7 | Catalog UX | Desktop/mobile acceptance workflows pass |
| 8 | Data operations visibility | Pipeline observable, auditable, recoverable |
| 9 | Performance & security | No Critical/Important findings remain |
| 10 | Regression + independent reviews (7 scopes) | All mandatory checks pass |
| 11 | Release candidate (draft PR, rollback plan) | Deliverables complete; production untouched |

## 6. Success criteria

- `docs/m3/` contains all 14 required deliverables with evidence under
  `docs/m3/evidence/`.
- A pilot dataset exists in an isolated dev DB where every record passes
  identity + provenance + validation rules; reimport is idempotent.
- TDD evidence (RED → GREEN → REGRESSION) exists for every functional change.
- Draft PR opened from `feat/m3-catalog-expansion` with full evidence bundle.
- Final report uses only the allowed verdicts.

## 7. Risks & honest limits

- No bulk `clear`-licensed source exists for the 4 new categories today; the
  pilot is curated-by-hand with official citations, so the numeric target may
  not be met — a smaller verified dataset plus an explicit gap report is the
  contract-compliant outcome.
- LLM assistance may be used only as an extraction aid, never as the final
  authority for hardware facts; every fact needs a source document.
- Production (5 389 rows) must remain byte-identical except for nothing —
  M3 performs zero production writes.
