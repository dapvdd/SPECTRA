# M3.1 Catalog Acquisition Implementation Plan (continuation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native, this session) — the mission execution policy mandates autonomous continuation.

**Goal:** Turn the 443 quarantined M3 candidates into a verified, manufacturer-evidence-backed catalog expansion across RAM/Storage/Motherboard/PSU, published to an isolated dev DB through the existing M3 evidence gate.

**Architecture:** Reuse Tasks 1–3 (candidate inventory, manifest/resolver/pipeline/errors, wiki_rest + citation adapters) unchanged. New: category research subagents produce VerifiedSKU manifests (per-field FieldEvidence with MPN + per-SKU URL + source_reference + match_method); a category runner resolves all 443 candidates against the manifests; `run_acquisition` publishes MATCHED records to a fresh dev DB; reports + tests + delivery docs close out.

**Tech Stack:** Python 3.13 / pytest (backend), existing publisher + evidence gate, webfetch-based human-citation research, no new services.

**Spec:** mission brief (this session) + `docs/m3/M3_DATA_CONTRACT.md`, `M3_IDENTITY_RULES.md`, `M3_SOURCE_REGISTRY.md`, `M3_SOURCE_FEASIBILITY.md`.

## Global Constraints

- Evidence gate is fail-closed: MATCHED ⇒ non-empty MPN + per-SKU URL + APPROVED FieldEvidence per populated field (source_reference locator + match_method ∈ manual-curation|spec-table-row|manufacturer-declaration + access_date). Wikipedia never backs SKU-specific fields.
- No data fabrication; a smaller verified set wins. Optional unknown fields stay NULL.
- Sources: Wikipedia (M3-1, clear, REST allowed with polite UA) + official manufacturer pages as human citations (M3-2, no crawling). Prohibited: PassMark, TechPowerUp, spec scrapers. No auth/anti-bot bypass.
- Publisher refuses `data/spectra.db`; publish only to a fresh `data/dev/m31_*.db`.
- No merge to main, no force-push, no deploy. Draft PR at the end.
- CI-parity suite must stay green: backend (2 deployment tests deselected per CI yml), frontend 681.

## Review Focus

1. **Variant-token mismatch (REPLACED inflation)** — candidate keys append variant to name-based key; resolve via variant token, not family alone. Test: category runner asserts MATCHED only on variant equality (Task 4 tests).
2. **MPN-less "verified" records** — gate blocks them; runner must never strip `mpn`. Test: publisher rejection path exercised in Task 6 idempotency/dry-run output.
3. **Duplicate canonical keys across families** — dedup quarantines, never merges. Test: existing `dedup_records` + new runner-level assert.
4. **Unverifiable families** — must land UNRESOLVED with notes, not invented data. Test: manifest validation rejects MATCHED without evidence (existing `validate_manifest`).
5. **Non-idempotent re-import** — re-run must report skipped_existing == published. Test: Task 6.

## Tasks

### Task 4: Category research — RAM manifests (subagent)
Produce `data/research/m31/manifest_ram.json` (VerifiedSKU entries per resolved family) + `data/research/m31/research_ram.md` (per-family classification notes, source URLs, access dates). Families: 14 (G.Skill, Corsair, Kingston, Crucial, TeamGroup, ADATA).

### Task 5: Category research — Storage manifests (subagent)
`data/research/m31/manifest_storage.json` + `research_storage.md`. 35 families (Samsung, WD, Crucial, Kingston, Seagate, ADATA, TeamGroup).

### Task 6: Category research — Motherboard + PSU manifests (subagents)
`manifest_motherboard.json` / `manifest_psu.json` + research notes. ~100 board families (ASUS/MSI/Gigabyte/ASRock), ~60 PSU families (Seasonic/Corsair/be quiet!/EVGA/Thermaltake/Cooler Master).

### Task 7: Category runner + candidate resolution (native)
Create `backend/app/catalog/acquisition/category_runner.py` + tests: loads manifest(s), resolves every inventory candidate (INVALID→MATCHED→REPLACED→UNRESOLVED), writes `data/research/m31/02_resolution_report.json` with per-candidate outcome + evidence + confidence. Commits with tests.

### Task 8: Publication rehearsal to isolated dev DB (native)
`data/dev/m31_acquisition.db` via `_clone_schema` + `upgrade` + source registration + `run_acquisition` (dry-run, then bounded batches); idempotency re-run; integrity checks (`PRAGMA integrity_check`, `foreign_key_check`); write `docs/m3/evidence/m31_run_log.json`.

### Task 9: Reports, tests, delivery (native)
`docs/m3/M31_ACQUISITION_REPORT.md`, `M31_DATA_QUALITY_REPORT.md`, `M31_RESIDUAL_RISKS.md`, `M31_RELEASE_READINESS.md`; source registry update; full CI-parity suites; push branch; draft PR with verdict.
