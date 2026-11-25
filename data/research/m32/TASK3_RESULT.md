# M3.2 Task 3 — Catalog Expansion (383 UNRESOLVED revisit)

Date: 2026-11-24 · Branch: feat/m32-compatibility-intelligence · Worktree: C:\Users\user\spectra-m32

## Result

**0 additional verified SKUs.** Every manufacturer product page in the
remaining unresolved categories (RAM 128 / STORAGE 109 / PSU 106 /
MOTHERBOARD 87 UNRESOLVED) is blocked for human-citation-grade extraction:

- Crucial: 404 on product URLs (mx500 slug, products/ssd/mx500), captcha
  marker on root — no renderable product page reachable.
- Samsung: 404 on /us/ product + semiconductor support URLs, Akamai marker
  on root.
- Seagate: HTTP 429 (rate limit) on product + root; 404 on alternate
  data-sheet URL form.
- Kingston: HTTP 403 (NV2 product page).
- Seasonic: HTTP 403. be quiet!: HTTP 403.
- ADATA / TeamGroup / Thermaltake / CoolerMaster: 404 on guessed product
  URL forms (no reachable product page).
- Corsair / Western Digital / G.Skill / EVGA: HTTP 200 but JS-shell /
  Cloudflare-challenge pages (captcha + challenge-platform markers; spec
  keywords appear only inside JS bundle text, not renderable content).
  These cannot back FieldEvidence: the M3 evidence gate requires a
  human-readable spec-table row at a per-SKU URL, and a JS bundle is not
  verifiable content.

## Actions taken

1. One polite fetch per product-page URL form per manufacturer (plan
   Task 3.1); two rounds for Crucial/Samsung/Seagate (product + support +
   data-sheet forms); one base-domain probe each to distinguish WAF from
   dead-slug. No bulk crawling, no retries beyond documented attempts.
2. 3-layer verification + quarantine + dedup + transactional publication
   unchanged (plan Task 3.3) — no gaps found because no new sources were
   admitted.
3. No verified status changed on plausible names or inferred specs
   (plan Task 3.4) — no candidate promoted.

## Policy outcome

Mission fallback clause (same as Task 1): the actual verified set is what
it is — 13 verified motherboards, no verified RAM/STORAGE/PSU additions.
UNRESOLVED candidates keep their reasons in
`data/research/m32/02_resolution_report_motherboard.json`; no fabricated
entries, no status inflation. Builder coverage proceeds with the verified
motherboard set plus the existing M3.1 approved pilot data.
