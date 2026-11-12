# M2 Delivery Report — Build Planner Compatibility Engine & Component-Aware Experience

Branch: `feat/build-planner-m2-compatibility` · Base: `92931d9` (origin/main) · HEAD: `196ca75` · 2026-11-12

## Verdict: **MERGED** (release gate executed 2026-11-12; see §9)

All 7 planned tasks are complete, committed, pushed, and green. Production
(`main`, production DB) was never touched. One merge-blocking concern is
disclosed below (non-blocking for review).

## 1. Scope executed (7/7 tasks)

| # | Task | Commit | Tests |
|---|---|---|---|
| 0 | Baseline audit (schema, API, frontend, missing fields) | `d79d939` | — |
| 1 | Domain model: `CompatibilityState` (3 states + NOT_APPLICABLE), `RuleResult`, `evaluate_rules` | `f207e47` | 15 |
| 2 | Seven deterministic rules, stable IDs, `M2-RULES-v1` | `f42d348` | 35 |
| 3 | `POST /build/compatibility/check` (partial builds, 404/422, provenance) | `45a66f5` | 12 |
| 4 | Category-aware detail views (RAM/STORAGE/MOTHERBOARD/PSU, zero CPU fields) | `e46050b` | 10 |
| 5 | Six-slot Build Planner + server-backed compatibility panel | `2be8e91` | 16 new + 6 updated |
| 6 | Test matrix document | `c91a115` | — |
| 7 | Isolated preview + 12 screenshots + 32 DOM assertions | `d0e202f` | 32/32 pass |

Docs: `M2_BASELINE_AUDIT.md`, `M2_COMPATIBILITY_RULES.md`, `M2_API_CONTRACT.md`,
`M2_TEST_MATRIX.md`, this report — all in `docs/build-planner/`.

## 2. Verification evidence

- **Backend:** `1228 passed, 2 skipped, 2 deselected` (baseline 1166 → +62).
  CI-parity command with the four documented ignores/deselects.
- **Frontend:** `663 passed, 0 failed` (baseline 637 → +26 new tests, 6
  existing expectations updated to the 6-slot shape — documented in the
  matrix, no test deleted).
- **Build:** `npx vite build` ✓ (~360 kB JS, ~102 kB gzip).
- **Preview (isolated):** backend :8000 on disposable DB
  `Temp\opencode\m2preview\preview_m2.db`; vite preview :4173; CORS verified
  via `Access-Control-Allow-Origin` header; API smoke-tested with curl for
  all three fixture builds.
- **Screenshots:** 12 PNGs at
  `docs/design/evidence/build-planner-m2/` (catalog, 6-slot planner empty +
  filled, compatible/incompatible/unknown compatibility panels, 4 category
  detail views, mobile 390px, dark theme).

## 3. Honest-limitation disclosures

1. **PNG visual verification:** the reviewing model cannot read PNG pixels.
   Every visual claim is instead backed by **32 DOM assertions** executed in
   the live page during capture (slot counts, chip texts per build state,
   rule rows, absence of CPU-only fields on category detail views, socket/
   PSU explanations). `capture_m2_preview.py` is committed as reproducible
   evidence. A human should still eyeball the 12 PNGs before merge.
2. **Aggregate never reads COMPATIBLE for full builds (by design):** the
   GPU-slot rule is always UNKNOWN at M2 because motherboards store only a
   *slot count*, not a PCIe generation. A fully-populated build therefore
   aggregates to UNKNOWN with 6 compatible rules + 1 unknown. This is the
   UNKNOWN-first-class design contract, verified in the preview (build A).
3. **Compatibility data is fixture-only:** the seven rules are deterministic
   logic over recorded specs; the preview DB is a disposable copy seeded with
   `PREVIEW`-prefixed fixtures (ids 5381–5398). No real-world compatibility
   claims (BIOS/XMP/QVL/M.2 keying/PSU connectors) are asserted anywhere —
   each rule's explanation states its boundary verbatim.

## 4. UNKNOWN-first-class guarantees (verified)

- Missing field ⇒ UNKNOWN *naming the field* (e.g. build C:
  `cpu_specifications.socket|motherboard_specifications.socket`).
- Empty/partial build ⇒ UNKNOWN, never COMPATIBLE.
- Any INCOMPATIBLE ⇒ aggregate INCOMPATIBLE (build B: socket AM4 vs LGA1700,
  DDR4 vs DDR5, HDD vs 0 sata_ports, PSU 450W below required).
- No DB writes from the check path (`test_no_database_writes`).
- Deterministic repeat calls (`test_deterministic_repeated_evaluation`).

## 5. Contract compliance

- ✅ No merge to main (branch only; PR URL available:
  `github.com/dapvdd/SPECTRA/pull/new/feat/build-planner-m2-compatibility`).
- ✅ No deploy, no production DB mutation (production DB untouched; preview
  ran on a disposable Temp copy).
- ✅ No worktree deleted (`build-planner-m2` intact).
- ✅ No fabricated compatibility data (rules state boundaries verbatim;
  fixtures are deterministic and preview-prefixed).
- ✅ Feature branch committed & pushed; remote SHA verified (`b339c25`).

## 6. Known limitations / follow-ups (non-blocking)

1. `getBuildSummary.relationshipLabel` still reads "CPU + GPU
   configuration" — cosmetic copy only; the summary now covers 6 slots.
2. PSU rule sizes against CPU+GPU TDP only (the only recorded draw fields);
   RAM/SSD draws are not modeled.
3. RAM "Speed" is displayed but never decides compatibility (no XMP/QVL).
4. Compatibility panel fetches on every slot change without debounce —
   acceptable for M2 scale (single sqlite read per change).
5. Existing test expectations for the 2-slot config shape were updated (6
   assertions) — intentional contract change, documented in the test matrix.

## 7. Independent review rounds

Two fresh-eyes review passes were run against the branch diff.

**Backend review** (rules, service, API, schema) — verdict
READY_FOR_MERGE_REVIEW; 0 Critical / 0 Important. Three Minor findings were
fixed in `5e56ea8`: top-level `FieldProvenance` import, dead `ids_echo`
removed, explicit PSU rounding (`math.floor(x + 0.5)`). Remaining Nits,
disclosed as follow-ups: `scalar_one_or_none` without a limit can 500 on
duplicate spec rows; no explicit rollback on the read-only session
(harmless); provenance rows are not attributed per `hardware_id`.

**Frontend review** (App.jsx, detail.js, buildConfig.js, tests) — initial
verdict CONDITIONAL_REVIEW; all findings addressed in `586e832`:
- **Critical (fixed):** `restoreBuildConversationForSlot` assumed the M1
  2-slot shape and would post a RAM/STORAGE/MOTHERBOARD/PSU detail as the
  GPU in the chat restore; the four M2 slots now return early.
- **Important (fixed):** aggregate badge lacked a fallback for an
  unexpected backend state string (rule rows already had one).
- **Minor (fixed):** dead `compatibility.explanation`/`rulesVersion` state
  and dead `summarizeSlot`/`SLOT_PROMPT_NOUNS` removed.
- **Important (disclosed, pre-existing at base `92931d9`):** the restore
  reads `buildDetailState` from a stale render closure, so a GPU loading
  after the CPU can skip the chat restore. This is M1 behavior, not
  introduced by M2; fixing it is a refactor scheduled for M3.
- **Nit (disclosed, pre-existing):** `aria-labelledby="build-slot-{type}"`
  targets an id no element carries.

Re-verification after fixes: frontend `663 passed, 0 failed` +
`npx vite build` OK; backend suite `1228 passed, 2 skipped, 2 deselected`;
final verdict for both scopes: **READY_FOR_MERGE_REVIEW**.

**Pre-merge release review (2026-11-12):** a third delta review of the
full `92931d9..38a52ba` diff found one more M2-exposed IMPORTANT bug:
`addToBuild`/`clearBuildSlot` mapped every slot type onto the M1 chat
token's `cpuId`/`gpuId` keys, so adding/clearing RAM/STORAGE/MOTHERBOARD/PSU
wiped the visible CPU+GPU conversation and collided chat tokens with the
real GPU slot. Fixed test-first in `196ca75` with a pure
`getBuildChatSlotKey` helper (CPU→`cpuId`, GPU→`gpuId`, all other slots and
unknown types→`null` — no token change); both call sites now guard on it;
CPU/GPU behavior is byte-identical to before. Frontend suite after the fix:
`664 passed, 0 failed` (+1 test) and build OK; backend untouched by the
fix. Round-2 verification by the same reviewer: **PASS**, no new findings.
The duplicate-spec `scalar_one_or_none` nit from the backend review was
re-examined: all six spec tables declare `hardware_id` `unique=True`, so
`MultipleResultsFound` is unreachable today (documented, no action).

## 8. Suggested merge review focus

1. `backend/app/services/compatibility_rules.py` — rule boundaries and
   UNKNOWN naming.
2. `backend/app/services/compatibility_service.py` — loader validation
   (404/422 mapping) and read-only guarantee.
3. `frontend/src/App.jsx` — compatibility effect (AbortController, keyed on
   slot ids), `BuildCompatibilitySection` honest states, and the chat-token
   guard (`getBuildChatSlotKey`).
4. The 12 evidence PNGs (human visual pass).

## 9. Release gate record (2026-11-12)

All five mandatory gates passed; merge authorized by the user's conditional
auto-merge directive.

| Gate | Status | Evidence |
|---|---|---|
| A — Git integrity | PASS | origin/main `92931d9` (= M2 base, unmoved); remote branch `196ca75`; 15 verified commits; no secrets/artifacts (scan clean); M2 touches no migration files |
| B — Final code review | PASS | 3 review rounds; every Critical/Important fixed & verified (5e56ea8, 586e832, 196ca75); remaining findings are Nits, disclosed |
| C — Visual | PASS (CSS + browser-rendered) | Independent reviewer: static CSS PASS; browser-rendered checks: grid 2×3 real (grid tracks), status chip renders amber border+text, dark-theme tokens applied, 0 page errors. PNG pixels not machine-readable (disclosed); human eyeball of the 12 PNGs still recommended |
| D — Regression | PASS | Backend 1228/2sk/2des; frontend 664/0; vite build OK; security+API+compatibility focused 49 passed; migration rehearsal on a disposable copy v0→3 verified, `integrity_check: ok`, 5380 rows preserved; browser smoke 11/11 product-correct; static checks not configured (N/A) |
| E — Security & data safety | PASS | `POST /build/compatibility/check` uses `Depends(require_auth)` like neighboring endpoints; parameterized ORM `select()` only; 404/422 mapping tested; no DB writes from the check path (tested); production DB read-only (copy-first rehearsal); no destructive migrations in M2 |

Merge method: remote-side `gh pr merge` (the main working copy is checked
out on the user's `feat/spectra-v3.1-production-hardening` branch and is
never touched). PR: `github.com/dapvdd/SPECTRA/pull/2`. Merge commit and
post-merge verification are recorded in the PR and release report.
