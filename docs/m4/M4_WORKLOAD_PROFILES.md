# M4 Workload Profiles

**Version:** `M4-PROFILES-v1.0`
**Module:** `backend/app/services/workload_profiles.py`
**Mirror (frontend):** `frontend/src/intelligenceDisplay.js`

---

## 1. Purpose

A workload profile is an immutable recipe that:

1. maps the four scenarios (`gaming`, `workstation`, `daily`, `value`) to
   weights summing to 1.0,
2. names the evidence families it relies on (`evidence_requirements`),
3. documents its assumptions — including what it does **not** claim,
4. declares which user preferences it supports.

## 2. The eight profiles

| Key | Label | Weights (g/w/d/v) | Supported preferences |
|---|---|---|---|
| esports_gaming | Esports gaming | 0.70 / — / 0.15 / 0.15 | resolution, budget_max, priority, existing_components |
| aaa_gaming | AAA gaming | 0.55 / 0.10 / 0.15 / 0.20 | resolution, budget_max, priority, existing_components |
| general_productivity | General productivity | 0.05 / 0.10 / 0.70 / 0.15 | budget_max, priority, power_limit_w, existing_components |
| software_development | Software development | 0.00 / 0.55 / 0.20 / 0.25 | budget_max, priority, power_limit_w, existing_components |
| video_editing | Video editing | 0.10 / 0.60 / 0.10 / 0.20 | budget_max, priority, power_limit_w, existing_components |
| rendering_3d | 3D rendering | 0.00 / 0.75 / 0.05 / 0.20 | budget_max, priority, power_limit_w, existing_components |
| virtualization_homelab | Virtualization & homelab | 0.00 / 0.60 / 0.25 / 0.15 | budget_max, priority, power_limit_w, existing_components |
| ai_ml_experimentation | AI/ML experimentation | 0.00 / 0.70 / 0.15 / 0.15 | budget_max, priority, power_limit_w, existing_components |

(Column order: gaming / workstation / daily / value.)

## 3. Evidence policy (per profile assumptions)

Every profile carries ≥ 2 documented assumptions, at least one of which is a
non-claim. Canonical examples (verbatim from the module):

- **esports_gaming** — "Uses CPU Geekbench 7 multi-core as the gaming proxy;
  no game-specific FPS measurements exist in this dataset." · "Does not
  claim measured FPS at any resolution." · "No GPU gaming benchmarks exist in
  this dataset, so GPU gaming suitability is spec-based and capped."
- **aaa_gaming** — "Never reports expected FPS at a resolution." · "Assumes
  higher VRAM/bandwidth helps at higher resolution — a qualitative spec
  argument, not a measured one."
- **rendering_3d** — "GPU render/compute claims are NOT made: no GPU compute
  benchmarks exist in this dataset."
- **ai_ml_experimentation** — "No GPU/VRAM compute benchmarks exist in this
  dataset: AI/ML GPU suitability is NOT scored."

## 4. Preferences

Validation is strict and deterministic:

- unknown preference → `ValueError`;
- preference not supported by the profile → `ValueError`
  (resolution is gaming-profile-only);
- `resolution` ∈ {1080p, 1440p, 4k}; `priority` ∈ {performance, balanced,
  efficiency};
- `budget_max` must be a non-negative number; `power_limit_w` a positive one.

`apply_preferences(profile, prefs)` returns a **new frozen profile**; base
profiles are never mutated.

**Priority reweighting** multiplies positive scenario weights by documented
multipliers, then renormalizes to 1.0 (drift folded onto the largest weight):

| Priority | gaming | workstation | daily |
|---|---|---|---|
| performance | ×1.15 | ×1.15 | ×0.85 |
| efficiency | ×0.85 | ×0.85 | ×1.15 |
| balanced | (no change) | | |

## 5. Resolution semantics

`resolution` on a gaming profile is **advisory context only**: the scenario
engine adds a limitation string, never a numeric adjustment (no GPU gaming
benchmark data exists to justify one).

## 6. Budget semantics

`budget_max` is accepted but never filters: this dataset has no price data,
so any budget filter would be fabricated precision. The v2 recommendation
echo classifies it `soft` with a note naming the absence of price data.

## 7. Default and errors

- `resolve_profile(None)` → `general_productivity`.
- Unknown key → `KeyError` (API maps to 422).

## 8. Tests

`backend/app/test_workload_profiles.py` (15 tests): exact key set, weight
normalization, assumption documentation, resolution support matrix, priority
bounds, frozen-ness, scenario-engine integration.
