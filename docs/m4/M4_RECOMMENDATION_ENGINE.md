# M4 Recommendation Engine

**Version:** `M4-REC-v2.0`
**Module:** additive layer in `backend/app/services/recommendation_service.py`
(`recommend_intelligent`; v1 `recommend`/`recommend_response` untouched)
**Routes:** `GET/POST /hardware/recommend/v2` (additive)

---

## 1. Pipeline

```
constraints (RecommendationConstraints)
   │
   ├─ resolve_profile(profile_key)         (M4-PROFILES-v1.0)
   ├─ load candidates (type-filtered, eager relations)
   ├─ features_from_hardware(row)          (M4-FEATURES-v1)
   ├─ evidence gate: coverage>0 or benchmark_families
   │     else → excluded[reason_code=insufficient_data:no_evidence]
   ├─ socket exclusion (rule_cpu_motherboard_socket, M32-RULES-v2 verbatim)
   │     INCOMPATIBLE → excluded[SOCKET_MISMATCH]; UNKNOWN → note, never excluded
   ├─ power advisory (listed TDP > limit → excluded[POWER_LIMIT_EXCEEDED];
   │     unknown TDP → note, never excluded)
   ├─ score_scenarios() per candidate      (M4-SCORING-v2.0)
   ├─ effective score = Σ(score·w)/Σ(w) over the profile's scenarios
   │     (score=None scenarios drop out of numerator and denominator)
   └─ sort: (-effective, -coverage, hardware_id)   ← deterministic tie-break
```

## 2. Payload

```jsonc
{
  "candidates": [{ "rank", "hardware_id", "hardware_name",
                   "scenario_scores", "stars", "confidence",
                   "rank_explanation", "trade_offs", "evidence" }],
  "alternatives": [ ...next 5 by the same ranking... ],
  "excluded": [{ "hardware_id", "hardware_name", "reason_code", "reason" }],
  "constraints_echo": { "<constraint>": { "value", "classification", "notes" } },
  "profile": { "key", "label", "assumptions", "scenario_weights" },
  "ranking_version": "M4-REC-v2.0",
  "deterministic": true
}
```

Reason codes (closed set): `SOCKET_MISMATCH`,
`POWER_LIMIT_EXCEEDED`, `insufficient_data:no_evidence`.

## 3. Constraint classification vocabulary

| Classification | Meaning |
|---|---|
| `hard` | filters candidates when violated (type, profile, socket w/ data) |
| `soft` | shapes ranking; never silently filters (budget, resolution, power, priority) |
| `unknown` | cannot be evaluated from current data; disclosed in notes |
| `estimated` | derived under a documented policy (advisory) |

**Budget is soft and never filters:** the dataset has no price columns; the
echo note names this explicitly. **Power is advisory:** exclusion only with
documented listed-TDP evidence; unknown TDP is labeled, never guessed.

## 4. Exclusion ledger

Every exclusion is itemized with hardware id, name, stable reason code, and a
human-readable reason. Socket evaluation reuses the M32-RULES-v2 rule
function directly (no duplicated logic) and UNKNOWN states produce echo
notes — not exclusions (mission: compatibility unknowns never exclude).

## 5. Rank explanation & trade-offs

`rank_explanation` lists: the effective weighted score, each scored scenario
(`score (confidence[, spec-based])`), each unknown scenario with its first
limitation, and benchmark freshness when present. `trade_offs` names
efficiency (score/W from listed TDP), listed TDP, and the value-unknown gap.

## 6. Alternatives

`alternatives` = the next 5 candidates after `limit`, same deterministic
ranking, ranks continue past `limit`.

## 7. Determinism & stability (evaluated)

- Two runs are byte-identical (`test_m4_evaluation.py`).
- Adding an unrelated low-evidence CPU does not reorder the existing top-5
  (the new row lacks evidence and is gate-excluded) — tested.
- Workload-specific inversions are representable (multi-core-heavy vs
  single-core-heavy fixture pair) and follow from profile weights.

## 8. v1 preservation

v1 `recommend()` / `recommend_response()` signatures, filtering, and payload
shape are unchanged (regression-tested in
`test_recommendation_intelligent.py::test_v1_recommend_response_unchanged`).
`budget_max` remains accepted-but-inert in v1 (documented v1 contract).

## 9. Tests

`backend/app/test_recommendation_intelligent.py` (14): constraint defaults,
soft-budget echo, determinism + id tie-break, socket exclusion/unknown,
ledger codes, profile echo, payload shape, confidence aggregation
(scored scenarios only), power advisory, GET/POST API, 422s, v1 shape.
