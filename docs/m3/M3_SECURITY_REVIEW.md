# M3 Security & Performance Review (Phase 9)

**Date**: 2026-11-17
**Scope**: the M3 additions only — ops visibility endpoints, validation rules,
publisher gate, curated adapters, catalog/provenance query surfaces
**Method**: evidence-based passive review per the security playbook — inspect
input boundaries, auth, injection sinks, and outbound-call surfaces; no
scanners, no intrusive probes, no production contact. Every finding below is
backed by a reproduction (test) or code citation.

## 1. Review boundaries

- Trust boundaries: HTTP request → FastAPI validation → service layer →
  SQLite (dev DBs only); curated CSV rows → adapters → validation → publisher.
- Assets: catalog integrity (no fabricated specs), ops audit trails, the
  existing auth/ownership model, security headers/CSP.
- Out of scope (untouched, unchanged): auth internals, rate limiter,
  CORS config, middleware stack — verified unchanged by the full regression.

## 2. Findings and resolutions

### F-1 (Medium, fixed) — Malformed spec value crashed validation instead of rejecting

- **Location**: `backend/app/importers/m3_validation.py` — `unit_checks`
  (range comparison) and `_rule_ram_kit_consistency` / `_rule_mobo_slots_vs_max_ram`
  (cross-field modulo/division).
- **Evidence (pre-fix reproduction)**:
  `unit_checks('RAM', {'capacity_gb': 'abc'})` →
  `TypeError: '<=' not supported between instances of 'int' and 'str'`;
  `cross_field_checks('RAM', {'modules': '2', ...})` → `TypeError` at the
  `%` operator.
- **Impact**: the publisher's per-record gate calls these functions inside
  `publish_batch`; one malformed row aborted the whole batch transaction with
  an opaque traceback (rollback did fire, but the run died instead of
  rejecting the bad row) — violating the fail-closed contract that a bad
  record is *rejected with a reason*, not a crash.
- **Fix**: `_type_check_failure` gate — only real `int`/`float` (excluding
  `bool`, which is an `int` subclass and would silently pass as 1) may enter
  range/cross-field comparisons; anything else becomes an explicit blocker
  naming the field and the offending value. `None` stays "field absent".
- **Verification**: `TestMalformedSpecValues` (7 tests) +
  `TestPublisherMalformedInput::test_malformed_record_rejected_batch_survives`
  — a batch containing one malformed and one valid record publishes the valid
  one and rejects the malformed one with a `wattage` reason; the transaction
  survives.

### F-2 (Low, accepted with pin) — Ops endpoints SQL surface

- **Location**: `backend/app/services/source_service.py` `_ops_rows`.
- **Evidence**: table and column names come from module-level allow-list
  constants (`_INGESTION_RUN_COLUMNS`, `_PUBLICATION_BATCH_COLUMNS`, and a
  two-entry table allow-list); the only request-derived value, `limit`, is
  FastAPI-validated (`ge=1, le=100` → 422 outside) and bound as a SQL
  parameter (`LIMIT :limit`).
- **Probes**: `TestOpsInjectionProbes` — hostile `limit` strings
  (`1 OR 1=1`, `1; DROP TABLE ...`, `abc`) all 422; the service helper refuses
  unknown tables structurally (`OpsTableUnavailableError`); response shape is
  pinned so no parameter widens it; tables survive the probes.
- **Residual risk**: none identified in the M3 surface. Pre-v4 databases get
  an honest 503 (covered in Phase 8).

### F-3 (None, pinned) — SSRF / outbound network I/O in M3 adapters

- **Location**: `backend/app/scripts/m3_adapters.py` (both curated adapters).
- **Evidence**: the module imports only `json` + the local source-acquisition
  framework; `map_record`/`acquire_values` transform prepared rows and store
  citation URLs without fetching them. No `requests`/`httpx`/`urllib`/`socket`
  anywhere in the module (AST-verified).
- **Pin**: `TestAdaptersZeroNetworkIO` — three tests: (a) AST scan forbids
  network-library imports in the adapter module, (b) AST scan forbids
  `open`/`urlopen`/`socket`/... call sinks, (c) behavioral proof that
  `map_record`+`acquire_values` succeed with `socket.socket` replaced by a
  constructor that raises (network disabled at the C level). If anyone later
  adds a "helpful" fetch, the suite fails loudly.

### F-4 (None observed) — Auth, headers, middleware on new endpoints

- The ops endpoints use the existing `require_auth` dependency (401 matrix in
  `test_auth_security.py`, Phase 8). Rate limiting, metrics, and security
  headers are app-level middleware and apply automatically; CSP and header
  values are byte-unchanged (`middleware/test_security_headers.py` passes in
  the full run). No cookies, no HTML rendering, no file serving, no
  redirects, no WebSockets were added by M3 — the corresponding FastAPI rule
  classes are not applicable.

### F-5 (None observed) — Secrets handling

- M3 adds no secrets. The publisher writes an approver identity string into
  `publication_batches.approved_by`; the ops endpoints expose it (it is
  operational metadata, documented in M3_OPS_VISIBILITY.md §4). No tokens,
  credentials, or internal paths appear in any M3 response.

## 3. Performance review (pilot scale, deterministic bounds)

`TestQueryPerformanceEnvelope` seeds an in-memory DB with **420 catalog rows**
(pilot scale: 400 records + headroom) and pins query counts via the SQLAlchemy
`before_cursor_execute` listener — structural bounds, not wall-clock (CI
timing is too noisy for pass/fail; latency was spot-checked informally and is
not asserted):

| Surface | Pinned bound | Rationale |
|---|---|---|
| `GET /hardware?limit=100` | exactly 2 queries (COUNT + page SELECT) | constant regardless of 420-row catalog; X-Total-Count = 420 verified |
| `GET /hardware` with type+q+manufacturer filters | exactly 2 queries | filtered scan stays bounded, no N+1 |
| `GET /hardware/{id}/provenance` (RAM, 30 provenance rows) | ≤ 12 queries | the Phase 7 eager-load constant; independent of provenance row count |

## 4. Honest limitations

1. Wall-clock latency is not asserted anywhere — by design (nondeterministic
   in CI). The structural bounds above are the enforceable contract.
2. The type gate accepts any int/float within range; extreme-but-numeric
   garbage (e.g. `capacity_gb = 1e300`) is caught by the sanity ranges, and
   out-of-range rejections name the suspected unit confusion.
3. `q` uses `ilike` with a `%`-wrapped pattern; user-supplied `%`/`_`
   wildcards in `q` act as SQL LIKE wildcards (search-only impact, no data
   exposure; pre-existing Phase 1.3 behavior, unchanged by M3, documented
   rather than changed to preserve byte-identical default behavior).
4. No dependency/version audit was performed (no new dependencies were added
   by M3; existing pins are maintained by the owner).
