# M3.1 Residual Risks

**Date**: 2026-11-23. Risks that remain after M3.1 Tasks 1–9, with grading and mitigations.

## R1 — Vendor page drift invalidates cited values (Medium)
Manufacturer pages change without notice; a cited page may drop or change a spec after access_date.
*Mitigation*: per-field evidence rows freeze the read value + locator + access date; re-verification is a manifest re-read + idempotent re-import (conflict gate rejects differing values rather than overwriting).
*Cost if wrong*: a spec value on a live page diverges from the catalog; conflict gate keeps the published row untouched (R2) so the risk is staleness, not corruption.

## R2 — 394 candidates remain unresolved (Accepted)
Vendor JS-rendering/WAF/retirement blocked per-SKU verification for ~89% of candidates (Samsung/Seagate/Crucial/Seasonic/be quiet!/Cooler Master/Thermaltake/EVGA/ASUS/MSI/Gigabyte/ASRock/G.Skill/TeamGroup/ADATA/Kingston-legacy).
*Mitigation*: honest UNRESOLVED classification with per-family access notes; the backlog is machine-actionable the moment per-SKU evidence becomes obtainable (manifest + runner + publisher are proven end-to-end).
*Cost if wrong*: none — fail-closed means the catalog under-reports rather than fabricates.

## R3 —Corsair-heavy verified set skews planner recommendations (Medium)
The 49 verified SKUs are 32 Corsair RAM + 7 Corsair PSU + 10 WD/Kingston storage. Build Planner recommendations are weighted toward these vendors until more families verify.
*Mitigation*: recommendation ranking already treats absent data as unknown; no family-level substitution was performed.
*Cost if wrong*: users see narrower brand coverage; no incorrect claims.

## R4 — M3-2 human-citation workflow scales poorly (Accepted)
Human-read citations (controller webfetch, one page at a time) do not scale to hundreds of JS-rendered vendor catalogs; automated fetching of M3-2 remains prohibited.
*Mitigation*: per-family access evidence documents exactly which sources block automation; future registry rows (e.g. manufacturer JSON APIs with explicit permission) can enter through the SourceLicenseGate.
*Cost if wrong*: catalog growth stalls until new sources are approved — an intentional trade.

## R5 — Checkpoint/DB coupling (Low)
Progress checkpoints are keyed to manifests, not databases; a rebuilt DB with stale checkpoints suppresses publication (observed in Task 8 rehearsal).
*Mitigation*: rehearsal script deletes checkpoints + DB together; ledger ruling recorded; `run_log.json` captures the symptom.
*Cost if wrong*: a future re-publish silently publishes 0 rows with skipped_existing = 0 (visible in the summary counts, not silent data loss).

## R6 — RMx SHIFT connector fields NULL (Low)
`pcie_8pin_count` / `pcie_12vhpwr` stay NULL on verified PSU records because per-SKU connector counts are not published on the cited pages.
*Mitigation*: Build Planner treats NULL connector counts as unknown (existing behavior); family-level claimed counts were deliberately NOT inherited.
*Cost if wrong*: planner cannot use these records for 12VHPWR-aware builds until the counts are verified.

## R7 — Sandisk SN850X page is vendor-of-record for WD (Low)
WD's own westerndigital.com pages were JS-rendered; SN850X evidence comes from Sandisk (WD's parent brand) product pages with per-SKU `?sku=` selectors.
*Mitigation*: Sandisk is the manufacturer of WD_BLACK SSDs; per-SKU URLs + MPNs are exact.
*Cost if wrong*: none beyond provenance naming; MPN is the anchor.

## Not risks (explicitly)

- No production/staging writes occurred; `data/spectra.db` was never touched (publisher refuses it structurally).
- No force-push, no merge to main; draft PR only.
- PassMark/TechPowerUp were never fetched or cited.
- No data fabrication: every MATCHED value traces to a named document row at a recorded access date.
