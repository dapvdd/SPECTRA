# M3.1 Data Quality Report

**Date**: 2026-11-23. Companion: `M31_ACQUISITION_REPORT.md`, `M31_RESIDUAL_RISKS.md`.

## Quality gates passed

| Gate | Result |
|---|---|
| `validate_manifest` (fail-closed) on all 3 manifests | no blockers |
| Publisher evidence gate (Layer 1/2/3) on 49 published records | 0 rejections |
| `detect_conflicts` / dedup quarantine | 0 conflicts, 0 quarantine |
| Idempotent re-run | skipped_existing 49, published 0 |
| PRAGMA integrity_check / foreign_key_check | ok / 0 violations |
| Optional-unknown-fields-NULL | enforced (no family-level inheritance into verified specs) |

## Per-category data quality

- **RAM (32 MATCHED / 11 REPLACED / 85 UNRESOLVED)** — all verified SKUs are Corsair with page-transcribed spec values; claimed-vs-page diffs reconciled to official values and noted per SKU (e.g. Dominator Titanium candidates consolidated to Dominator Platinum RGB pages). The 11 REPLACED are same-family variant differences (documented, not merged silently).
- **STORAGE (10 MATCHED / 99 UNRESOLVED)** — verified values transcribed from Sandisk product pages and Kingston PDF datasheets (revision-dated). SN850X claimed read speeds reconciled to per-capacity page values (2TB 6600 vs claimed 7300). Write speeds recorded only where the document states them.
- **PSU (7 MATCHED / 99 UNRESOLVED)** — verified from corsair.com per-SKU pages. Connector-count fields (`pcie_8pin_count`, `pcie_12vhpwr`) deliberately NULL in verified specs: the SHIFT pages do not publish per-SKU connector counts, and the inventory's claimed counts (family-level guesses) were not carried over.
- **MOTHERBOARD (0 / 100 UNRESOLVED)** — no verified data; honest empty result.

## Known limitations (graded, not hidden)

1. **Coverage is Corsair/WD/Kingston-weighted** (49/443 = 11.1% of candidates; 100% of the planner-relevant pilot families for RAM Corsair). The remaining 394 candidates stay in the quarantine backlog with documented per-family access evidence.
2. **`provenance_entities` counts 49 hardware rows**; field_provenance rows total 270 (RAM records carry 5–6 field rows each; STORAGE/PSU 4–5).
3. **Checkpoints are manifest-keyed, not DB-keyed** — deleting the dev DB requires deleting `*.progress.json` before re-publishing (ledger ruling, Task 8). The rehearsal script + run log document this.
4. **REPLACED confidence 0.5** — same-family, different-variant supersedence is a family-level assertion, never a per-SKU verification; nothing publishes from it.

## Verification trail

Every published value traces: `field_provenance` row → source_url → source_reference locator (named table row) → match_method → access_date → curator APPROVED. Sample query:

```sql
SELECT p.field_name, p.evidenced_value, p.source_url, p.source_reference,
       p.match_method, p.access_date
FROM field_provenance p
WHERE p.table_name = 'ram_specifications' LIMIT 5;
```
