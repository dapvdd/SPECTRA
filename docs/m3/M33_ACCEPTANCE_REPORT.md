# M3.3 Acceptance Report (Phase 7)

**Date**: 2026-11-25
**Target**: isolated rehearsal deployment on DavidLab
(`spectra-m33-rehearsal-backend/frontend`, images
`spectra-backend|m33-rc-5c2c7d9`, published at `100.113.157.0:8097`,
separate volume `spectra-m33-rehearsal-data` + network `spectra-m33-rehearsal`).
**Release identity served**: `{"version":"M3.3-rehearsal","git_sha":"5c2c7d9…","auth_enabled":false,"ai_provider":"unconfigured"}` (GET /api/release).

## 1. API functional acceptance — 18/18 PASS

Real HTTP against the deployed stack (script `m33_acceptance.py`, evidence
`/tmp/m33_acceptance_evidence.json` on david-lab):

| # | Check | Result |
|---|---|---|
| 1 | `GET /api/hardware?verified=1` total = **62** | PASS |
| 2 | Verified split = RAM 32 / STORAGE 10 / PSU 7 / MOTHERBOARD 13 | PASS |
| 3 | Lifecycle fields (`record_status`, `identity_status`) on every payload | PASS |
| 4 | All verified rows `PUBLISHED` + `confirmed` | PASS |
| 5 | `GET /api/hardware/facets?verified=1` → 200 | PASS |
| 6 | Default listing (no filter) total = **5442** (legacy untouched) | PASS |
| 7 | Motherboard detail carries real specs (socket/chipset/form_factor/ram_type/ram_slots/max_ram_gb) | PASS |
| 8 | Spec values real (B650-PLUS → socket `AM5`), no fabrication | PASS |
| 9 | Builder `POST /api/build/compatibility/check` → 200 | PASS |
| 10 | `rules_version` = **M32-RULES-v2** | PASS |
| 11 | Rules emitted for CPU+MB+RAM build (6 rules) | PASS |
| 12 | Every rule carries a `reason_code` | PASS |
| 13 | Every rule carries `provenance[]` references | PASS |
| 14 | R1 socket: Ryzen 7950X + B650-PLUS → COMPATIBLE / SOCKET_MATCH | PASS |
| 15 | R2 DDR: DDR5 RAM + DDR5 board → COMPATIBLE / DDR_GENERATION_MATCH | PASS |
| 16 | Aggregate `state` vocabulary = COMPATIBLE/INCOMPATIBLE/UNKNOWN/PARTIAL (build → UNKNOWN because CPU_GENERATION_UNKNOWN + RAM_SPEED_UNKNOWN are honest UNKNOWNs, never auto-promoted) | PASS |
| 17 | Partial build (RAM alone) → state != COMPATIBLE | PASS |
| 18 | PSU-only build → no fabricated wattage-adequacy rule | PASS |

Rule-level evidence (real API response, 7950X + B650-PLUS + DDR5-5600):

| rule_id | state | reason_code |
|---|---|---|
| cpu-motherboard-socket | COMPATIBLE | SOCKET_MATCH |
| ram-motherboard-generation | COMPATIBLE | DDR_GENERATION_MATCH |
| ram-motherboard-capacity | COMPATIBLE | RAM_CAPACITY_WITHIN_MAX |
| ram-motherboard-slots | COMPATIBLE | RAM_SLOTS_FIT |
| cpu-motherboard-generation | UNKNOWN | CPU_GENERATION_UNKNOWN |
| ram-motherboard-speed | UNKNOWN | RAM_SPEED_UNKNOWN |

## 2. Browser/visual acceptance (Playwright, headless Chromium 1440×900) — 10/10 PASS

Two passes (`m33_visual.py`, `m33_visual2.py`; screenshots in
`AppData\Local\Temp\opencode\m33_shots\`):

| Check | Result |
|---|---|
| SPA loads (`#app` renders nav Explore/Compare/Build/About) | PASS |
| Zero console errors / page errors on load | PASS |
| Explore page renders (3708 chars content) | PASS |
| Component vocabulary present (CPU/GPU/RAM/Hardware) | PASS |
| Catalog composition on page matches DB exactly: CPU 3501, GPU 1879, RAM 32, STORAGE 10, MOTHERBOARD 13, PSU 7 | PASS |
| Verified SKU names visible (Vengeance/B650/RMx/Athlon) | PASS |
| Build page renders | PASS |
| Build page slot vocabulary (CPU/Motherboard/RAM/GPU/PSU/Storage) | PASS |
| 27 catalog item nodes rendered | PASS |
| Screenshots captured: 01_home, 02_catalog, 03_builder, 04_explore, 05_build | PASS |

Network quirk: tailscale link occasionally stalls `networkidle`; tests use
`domcontentloaded` + explicit waits — not an app defect (server 200s
throughout).

## 3. Verdict

Functional + visual acceptance: **PASS** (28/28 checks). The deployed RC
serves the migrated, published catalog with M3.2 lifecycle fields, real
specs, rule provenance, reason codes, honest UNKNOWNs and no fabricated
rules — matching the M32-RULES-v2 contract.
