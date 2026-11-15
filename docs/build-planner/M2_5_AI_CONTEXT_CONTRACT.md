# M2.5 AI Context Contract — Build Chat Compatibility Digest

Branch `feat/spectra-m2.5-unified-build-experience` · 2026-11-13
Code: `backend/app/schemas/build_chat.py` (models + bounds),
`backend/app/services/build_chat_service.py` (`_CHAT_PROMPT` rule 14,
`build_prompt_payload`), `frontend/src/buildChat.js`
(`buildBuildChatCompatibilityDigest`), `frontend/src/App.jsx` (wiring).

## Purpose

M2's `BuildContext` carried only cpu/gpu ids + names. The assistant could not
see the four new slots and could not see the compatibility verdict at all — so
it could confidently call an incompatible build fine. M2.5 adds one **bounded,
verified, pass-through** compatibility summary to the context.

Design stance: the digest is a **mirror of SPECTRA's own verdicts**. The client
never derives, scores, or extends a rule; the assistant is forbidden from
extending them further. Anything not in the context stays unknown.

## Shape

`BuildContext` gains one optional field — `compatibility: BuildCompatibilityDigest | null`:

```
compatibility: {
  aggregate_state: "COMPATIBLE" | "INCOMPATIBLE" | "UNKNOWN",   // report-level verdict
  rule_results: [                                               // ≤ MAX_COMPATIBILITY_RULE_RESULTS (7)
    { rule_id: str ≤100, state: "COMPATIBLE"|"INCOMPATIBLE"|"UNKNOWN",
      explanation: str ≤ MAX_COMPATIBILITY_RULE_EXPLANATION_LENGTH (600) }
  ],
  unresolved: [ str ≤ MAX_COMPATIBILITY_UNRESOLVED_ITEM_LENGTH (300) ],  // ≤ MAX_COMPATIBILITY_UNRESOLVED_ITEMS (7)
  slots: { "<slot-name>": <hardware id> }                       // ≤ MAX_COMPATIBILITY_SLOTS (6), ids > 0
}
```

Bounds (backend constants in `schemas/build_chat.py`, mirrored as
`BUILD_CHAT_COMPATIBILITY_*` in `buildChat.js`):

| Constant | Value | Reason |
|---|---|---|
| `MAX_COMPATIBILITY_RULE_RESULTS` | 7 | The M2 rule set has exactly seven rules; a client cannot inflate the prompt beyond one entry per rule. |
| `MAX_COMPATIBILITY_RULE_EXPLANATION_LENGTH` | 600 | Explanations are SPECTRA-authored sentences; 600 chars covers the longest PSU branch. |
| `MAX_COMPATIBILITY_UNRESOLVED_ITEMS` / `_LENGTH` | 7 / 300 | Missing-data entries (`rule_id: table.field, …`) per unresolved rule. |
| `MAX_COMPATIBILITY_SLOTS` | 6 | Six-slot identity only — no records, no spec payloads. |

Everything is `extra="forbid"`: an unknown key in the digest is a validation
error, not silently-accepted context.

## Semantics

### What the client puts in

`buildBuildChatCompatibilityDigest(compatibility, slotIds)`:

- **Withheld entirely** while the check is loading or failed (`isLoading` /
  `error`) — the assistant is never handed a stale or partial verdict.
- Rules whose state is `NOT_APPLICABLE` are **omitted**, not mislabeled — it is
  not a compatibility verdict. (Unknown state strings fall through validation.)
- `unresolved` is built from UNKNOWN rules: `missing_information` when present
  (`"rule_id: psu_specifications.pcie_8pin_count, …"`), else the rule's own
  explanation, both truncated to the item bound.
- `slots` carries only usable positive-integer ids, capped at six entries.
- A non-verdict `aggregate_state` normalizes to `"UNKNOWN"` — never invents a
  green.

### How it travels

`buildChatPayload(cpuDetail, gpuDetail, userContext, question, benchmarksBySlot,
messages, compatibilityDigest)` — the digest is the **7th parameter**; when
non-null it is set as `build.compatibility`.

`build_prompt_payload` serializes with `model_dump(mode="json")` and **no
`exclude_none`**:

- A null spec value stays an explicit `null` — "no stored value" (prompt rule
  13). Dropping the key would read as *unknown-ness* instead of *absent data*.
- When no digest was supplied, the key serializes as
  `"compatibility": null` — telling the assistant **a check was not supplied**
  rather than letting absence imply *compatible*. Four backend tests pin this
  invariant.

### Prompt rules (1–42)

Rules 1–13 and 15–42 are unchanged in meaning and renumbered around the new
**rule 14**, which the prompt is updated to state:

> 14. The build may include a compatibility summary produced by SPECTRA under
> `build.compatibility`. When it is present, treat its `aggregate_state` and
> `rule_results` as authoritative SPECTRA facts. If the aggregate state is
> INCOMPATIBLE, or any rule result is INCOMPATIBLE, name the failing checks and
> **never describe the build as "ready to use" or "ready to build"**; state
> plainly that the build has an incompatibility. When the compatibility summary
> is absent or null, say that a compatibility check has not been supplied rather
> than assuming the build is compatible.

Supporting existing rules keep their force: 4/8/27/28 (TDP is never draw and
never a PSU recommendation), 11 (no unclaimed compatibility), 13 (null ≠ zero).

## Backend contract

- Route `POST /build/chat` keeps `Depends(require_auth)`; conversation routes
  (`/build/conversations*`) keep their auth + ownership scoping. **No
  auth/ownership boundary changed in M2.5.**
- Digest fields are validated server-side (bounds above); an over-sized digest
  from a malicious client is a 422, not a prompt-inflation vector.
- The digest rides only inside the request body. The response shape
  (`answer`/`evidence`/`analysis`) is unchanged, and the analysis remains
  forbidden from stating wattage, power figures, or compatibility guarantees
  (rules 37–39).

## Frontend wiring (App.jsx)

- The digest is derived from the **same** `buildCompatibility` state the
  Compatibility panel renders, paired with `buildSlotIds`. In M2.5 Task 6 the
  derived value is computed in render (`EMPTY_BUILD_COMPATIBILITY` fallback) so
  stale rule results can never display — or reach the digest — after slots
  change, and an **empty build short-circuits the POST** (`hasSelectedBuildComponent`),
  meaning chat on an empty build sees `compatibility: null` and says a check was
  not supplied. The digest is passed to `askBuildChat` → `buildChatPayload`.
- Chat identity is unchanged: `getBuildChatToken` still keys on
  `cpuId:gpuId:use_case:resolution`; the digest does not join the token (a
  changed compatibility verdict rides in with the next question's payload).
  `restoreBuildConversationForSlot` resolves the CPU/GPU pair through
  `resolveBuildChatRestore` on a live ref mirror (Task 6, F6).

## Guarantee summary

1. **Verified-only** — every digest field is a SPECTRA-computed fact passed
   through unchanged; nothing derived or extended client- or model-side.
2. **Never ignore INCOMPATIBLE** — rule 14 forbids "ready to use"/"ready to
   build" wording whenever the aggregate or any rule reads INCOMPATIBLE.
3. **Never fabricate** — absent data stays unknown (rules 2, 12, 13, 26, 40);
   `compatibility: null` is stated as "no check supplied", never as green.
4. **Bounded** — 7 rules / 600-char explanations / 7 unresolved items / 6 slot
   ids; the prompt cannot be inflated through this channel.
5. **Graceful** — provider absence still returns 503 without breaking the
   planner; the digest is additive to a request that already validated.
