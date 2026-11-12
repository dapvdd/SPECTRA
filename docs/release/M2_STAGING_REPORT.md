# SPECTRA M2 Staging — Access & Lifecycle + Final Report

Date: 2026-11-12 · Operator: autonomous release agent · Verdict: **STAGING_READY_FOR_USER_REVIEW**

The SPECTRA Build Planner M2 release (merge commit `abb2548`, identical tree to reviewed
`4293cdf`) is deployed as an **isolated staging environment** on DavidLab, fully accepted
(functional + browser), with zero production impact proven at every phase gate.

---

## 1. Review access (human)

| | |
|---|---|
| **Staging URL** | **http://100.113.157.0:8095/** |
| Reachable from | any device on the tailnet (Tailscale-only binding; not public internet) |
| Release SHA | `abb2548` (main; tree identical to M2 reviewed head `4293cdf`) |
| Schema | v3 (`planner-component-categories`; prod remains v2) |
| Frontend | `spectra-m2-staging-frontend-1` (nginx, :8095→8080) |
| Backend | `spectra-m2-staging-backend-1` (healthy) |

Staging-only demo fixtures are labeled `STAGING-FIXTURE …` (source "STAGING-ONLY Fixture
Source", provenance `uncertain`). They are **not** production hardware records; all 5,380
real production catalog rows are present alongside them untouched.

## 2. Lifecycle commands (on david-lab, staging-scoped only)

```bash
# status
docker compose -f /home/david/releases/spectra-m2-staging/compose.json ps
# stop
docker compose -f /home/david/releases/spectra-m2-staging/compose.json stop
# start again
docker compose -f /home/david/releases/spectra-m2-staging/compose.json start
# full cleanup (staging-scoped; NEVER global docker prune) — only when user approves
docker compose -f /home/david/releases/spectra-m2-staging/compose.json down -v
rm -rf /home/david/releases/spectra-m2-staging
```

Staging was **not** auto-deleted; it stays running for user review.

## 3. Isolation matrix (proven live)

| Dimension | Production | Staging |
|---|---|---|
| Compose project | `spectra` @ `/home/david/releases/spectra-75eba50-ops` | `spectra-m2-staging` @ `/home/david/releases/spectra-m2-staging` |
| Containers | `spectra-frontend` `fb2f3aa8bb46`, `spectra-backend` `8bb67a872fdd` (unchanged all run) | `spectra-m2-staging-frontend-1` `cd985517b513`, `spectra-m2-staging-backend-1` `5d9a67a93ffe` |
| Images | `:75eba50b1f09052f40409f6066a2ac030344d1a0` | `:m2-staging-abb2548` (`bf4b9ed223fa` / `676ccda409ec`) |
| Network | `spectra_default` | own compose-scoped network |
| DB storage | volume `spectra-sqlite-data` | bind mount `…/spectra-m2-staging/data` |
| Port | `100.113.157.0:8080` | `100.113.157.0:8095` (8081 known taken) |
| Schema | v2 (`tracked-version-2`) | v3 (`tracked-version-3`) |

No `latest` tags, no privileged containers, no Docker socket, no host networking, no
public 0.0.0.0 binding, no prod secrets copied (GEMINI key omitted), no shared
names/volumes/networks/ports.

## 4. Database copy & migration (Gate C)

- Snapshot: SQLite backup API in a throwaway container, prod volume mounted **read-only**;
  prod journal `delete` (no WAL) → consistent snapshot.
- Logical equivalence prod=copy proven by ordered content hashes (hardware
  `4b1c41ca…`, cpu `ed42ba55…`, gpu `3ee4c8a8…`, provenance `03d05b0d…`, 6 build
  conversations). File SHA differs from prod only because the backup API rewrites the
  SQLite header.
- Migration v3 `planner-component-categories` applied to the **copy only**, verified
  (`status=verified, version=3`), integrity ok. After migration: hardware 5380, cpu 3501,
  gpu 1879, ram/storage/motherboard/psu 0 (new tables), provenance 39440, sources 10,
  build_conversations 6, users 0.
- Prod DB re-checked **byte-identical** after migration: `7d1dca46cd19503944e82ec874902c830e94587f72b19b36c33a0f67e5c0310a`.

## 5. Phase F — functional acceptance: 50/50 PASS + zero DB writes

Catalog: all 6 categories visible with correct totals (CPU 3501, GPU 1879, RAM 3,
STORAGE 2, MOTHERBOARD 2, PSU 2 — the latter three are `STAGING-FIXTURE` rows only);
invalid category → 422.

Detail endpoints: each category returns only its own spec fields — RAM detail shows
DDR5/32GB and **no Cores/Threads/Socket**; storage shows NVMe/1TB with no
`ddr_generation`; motherboard FCLGA1700/DDR5; PSU 750W 80 Plus Gold; GPU/CPU prod rows
correct.

Compatibility API (`POST /api/build/compatibility/check`, rules `M2-RULES-v1`):

| Scenario | Aggregate | Key rule |
|---|---|---|
| Full build (prod i9-13900K + HD 7970 + 4 fixtures) | UNKNOWN | 6 rules COMPATIBLE, `gpu-motherboard-slot` UNKNOWN (design-correct: PCIe generation unmodeled) |
| Same build without GPU | **COMPATIBLE** | all applicable rules pass |
| AMD AM4 CPU vs FCLGA1700 board | INCOMPATIBLE | `cpu-motherboard-socket` INCOMPATIBLE, explanation names both sockets |
| DDR4 kit in DDR5 board | INCOMPATIBLE | `ram-motherboard-generation` INCOMPATIBLE |
| 450W PSU vs 375W draw (250W GPU + 125W CPU, 30% headroom → 488W required) | INCOMPATIBLE | `psu-build-wattage` INCOMPATIBLE |
| 750W PSU + 900W Tesla GPU | INCOMPATIBLE | `psu-build-wattage` INCOMPATIBLE |
| Motherboard only / empty build | UNKNOWN | zero rules, honest "cannot confirm" |
| Unknown id / wrong category | 404 / 422 | offending slot named |
| Identical request twice | deterministic | byte-identical response |

No unintended writes: all table counts identical before/after the whole acceptance run
(hardware 5389, cpu 3501, gpu 1879, ram 3, storage 2, mobo 2, psu 2, sources 11,
provenance 39503, conversations 6).

## 6. Phase G — browser acceptance: 30/30 DOM checks, 0 fatal JS errors

14 screenshots committed under `docs/design/evidence/m2-staging/`:
homepage, hardware catalog, RAM catalog, RAM/Storage/Motherboard/PSU detail, six-slot
planner, filled planner, compatibility UNKNOWN, compatibility INCOMPATIBLE, mobile
(390×844), dark, light.

Verified via DOM/computed assertions: six labeled slots, add/replace flows for all six
slots, aggregate chip "Compatibility unknown" (6 rules compatible, GPU rule unknown) and
"Incompatible" with socket-mismatch explanation, no horizontal overflow on mobile,
`prefers-color-scheme` respected (`data-theme=dark`/`light`), keyboard Tab reaches
buttons/inputs, slot cards carry `aria-labelledby`.

**Visual-review limitation (disclosed):** the reviewing model cannot read PNG pixels.
Visual claims are backed by DOM and computed-style assertions only; a human should
eyeball the 14 PNGs for pixel-level polish. Gate G therefore passes on behavioral
evidence, not pixel approval.

## 7. Phase H — production non-interference: PASS

After the entire test campaign, production showed:

- Same container IDs (`fb2f3aa8bb46`, `8bb67a872fdd`), images `75eba50b…`, "Up 2 days"
  uninterrupted.
- Same volume (`spectra-sqlite-data`), same port binding (`100.113.157.0:8080` only),
  same compose project/working dir.
- `/api/health` healthy; `/api/ready` still `tracked-version-2` — **prod schema
  untouched by the v3 migration**.
- Prod DB sha256 byte-identical `7d1dca46cd19503944e82ec874902c830e94587f72b19b36c33a0f67e5c0310a`
  (measured again after all tests).
- No prod file, env, Nginx, auth, firewall, or Tailscale change was attempted at any point.

## 8. Known limitations

1. **PNG pixels not human-verified by the agent** — see §6 disclosure.
2. Staging fixtures are minimal (3 RAM / 2 storage / 2 motherboards / 2 PSU) — enough to
   exercise all rules and journeys, not a representative catalog.
3. Staging auth users table is empty (prod parity); register/login flows were not part of
   the M2 acceptance scope.
4. The GPU-slot rule is UNKNOWN by design at M2 (motherboards store slot counts, not PCIe
   generations); a full-build aggregate can therefore never read COMPATIBLE while a GPU
   is selected — verified as intended behavior, not a defect.
5. Staging DB was snapshotted from prod on 2026-11-12; prod data changed since then will
   not appear in staging.

## 9. Verdict

**STAGING_READY_FOR_USER_REVIEW**

- URL reachable and healthy from the review network (verified repeatedly, including from
  a non-host machine over Tailscale).
- Gates A–H all PASS; functional 50/50; browser 30/30; prod non-interference proven
  byte-level at three separate checkpoints (post-snapshot, post-migration, post-campaign).
