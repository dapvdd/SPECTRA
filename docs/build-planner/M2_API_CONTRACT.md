# M2 API Contract — `POST /build/compatibility/check`

Branch `feat/build-planner-m2-compatibility` · 2026-11-11

Single read-only endpoint that evaluates the current build against the M2
rule set. **Never writes to the database** (asserted by
`test_no_database_writes`).

## Request

`POST /build/compatibility/check` · `Content-Type: application/json`

```json
{
  "cpu": 5381,
  "gpu": 5382,
  "ram": 5383,
  "storage": 5384,
  "motherboard": 5385,
  "psu": 5386
}
```

- Keys are **lowercase slot names**; every slot is optional (`int | null`).
- Partial builds are valid input — and a partial build is never declared
  fully compatible.
- Values are `hardware.id` integers. IDs are echoed back per rule.
- Unknown/extra keys are ignored by the Pydantic model.

## Responses

### `200 OK`

```json
{
  "state": "UNKNOWN",
  "explanation": "Compatibility could not be fully confirmed: ...",
  "rules_version": "M2-RULES-v1",
  "rule_results": [
    {
      "rule_id": "cpu-motherboard-socket",
      "component_hardware_ids": { "cpu": 5381, "motherboard": 5385 },
      "state": "COMPATIBLE",
      "explanation": "CPU socket LGA1700 matches motherboard socket LGA1700. BIOS support is not evaluated (no BIOS compatibility data).",
      "spec_fields": [
        "cpu_specifications.socket",
        "motherboard_specifications.socket"
      ],
      "missing_information": [],
      "provenance": [
        {
          "table_name": "cpu_specifications",
          "field_name": "socket",
          "evidenced_value": "LGA1700",
          "evidence_status": "verified",
          "source_url": "https://example.com/cpu"
        }
      ]
    }
  ]
}
```

Field notes:
- `state` — aggregate: `COMPATIBLE | INCOMPATIBLE | UNKNOWN` (see
  `M2_COMPATIBILITY_RULES.md` for semantics; `NOT_APPLICABLE` exists only at
  rule level and never becomes the aggregate).
- `rules_version` — stable ruleset ID, currently `M2-RULES-v1`.
- `rule_results[]` — one entry per *applicable* rule; rules whose components
  are absent do not appear.
- `component_hardware_ids` — echoes the evaluated slot→id pairs (unfilled
  slots read `null`).
- `missing_information[]` — dotted `table.field` names whose absence kept
  the rule UNKNOWN; empty for decided rules.
- `provenance[]` — `FieldProvenance` rows matching the consulted
  `(table, field)` pairs (`benchmark_result_id IS NULL`); may be empty.

### Error responses

| Status | When | Body |
|---|---|---|
| `404 Not Found` | A provided id has no `hardware` row; `detail` names the slot and id. | `{"detail": "No hardware record found for slot 'cpu' (id 99999)."}` |
| `422 Unprocessable Entity` | A provided id exists but its `type` doesn't match the slot's category (e.g. a GPU id in `ram`). | `{"detail": "Hardware id 2 for slot 'ram' is type 'GPU', expected 'RAM'."}` |
| `422 Unprocessable Entity` | Malformed body (non-integer id, wrong JSON shape). | FastAPI validation detail |

Note: Pydantic ignores unknown keys, so extra fields do **not** error.

## Applicability matrix

Which rule runs for which slot combination (rule appears in `rule_results`
only when applicable):

| Rule | Requires |
|---|---|
| `cpu-motherboard-socket` | cpu + motherboard |
| `ram-motherboard-generation` / `-capacity` / `-slots` | ram + motherboard |
| `storage-motherboard-interface` | storage + motherboard |
| `psu-build-wattage` | psu + (cpu or gpu) |
| `gpu-motherboard-slot` | gpu + motherboard |

## Client integration (frontend)

- `App.jsx` posts the six slot ids on every selection change (effect keyed on
  the JSON of slot ids, with `AbortController` cleanup — stale responses can
  never overwrite newer ones).
- `BuildCompatibilitySection` renders the aggregate chip plus per-rule rows
  (state badge, explanation, missing fields, provenance count).
- Transport failure renders an honest "unavailable" note and keeps state
  UNKNOWN — never a silent green.

## Guarantees

1. **Deterministic** — same input ⇒ byte-identical verdict
   (`test_deterministic_repeated_evaluation`).
2. **Read-only** — no inserts/updates/commits
   (`test_no_database_writes` counts rows before/after).
3. **UNKNOWN-first** — absent data yields UNKNOWN naming the field, never
   COMPATIBLE (`test_partial_build_is_not_compatible`,
   `test_empty_build_is_unknown`).
4. **Versioned** — `rules_version` travels with every response.
