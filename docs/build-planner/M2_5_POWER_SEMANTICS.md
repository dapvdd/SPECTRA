# M2.5 Power Semantics — PSU Rule v2 (Two-Tier TDP Reference)

Version: **`M2.5-RULES-v1`** · Branch `feat/spectra-m2.5-unified-build-experience` · 2026-11-13
Supersedes: the R6 section of `M2_COMPATIBILITY_RULES.md` (rules R1–R5 and R7 are
unchanged). Code: `backend/app/services/compatibility_rules.py`
(`rule_psu_build_wattage`), constant `PSU_TDP_REFERENCE_FRACTION = 0.3`.

## The problem this fixes

The M2 PSU rule computed `required = floor(total_draw × 1.3 + 0.5)` from summed
CPU/GPU `tdp_w` and returned **COMPATIBLE** when `wattage ≥ required`, with the
explanation *"PSU 450 W covers 45.0 W draw … plus 30% headroom"*. That claim was
unsafe in three ways:

1. A listed TDP is a manufacturer thermal rating, **not a measurement of system
   power draw** (RAM, storage, motherboard, fans, and transient spikes are not in
   the sum at all).
2. A sum of TDP ratings plus an arbitrary fraction is **not a validated PSU
   requirement** — real sizing depends on transient behaviour, efficiency curves,
   and connector needs, none of which SPECTRA stores.
3. Treating it as decisive let a fully-populated build aggregate to COMPATIBLE
   from TDP arithmetic alone.

## The two-tier policy (M2.5-RULES-v1)

TDP arithmetic produces exactly one thing: a **documented reference** —
`reference = floor(total_listed_tdp × (1 + 0.3) + 0.5)` — with exactly two
decisive uses:

| Condition | State | Wording intent |
|---|---|---|
| `wattage < reference` | **INCOMPATIBLE** | Hard headroom-floor constraint. "PSU 450 W is below the documented reference floor of 488 W (sum of listed TDPs 375 W — CPU 125 W listed TDP, GPU 250 W listed TDP — plus 30% reference headroom; listed TDP values are not measured power consumption)." |
| `wattage ≥ reference` | **UNKNOWN** (advisory) | Non-authoritative estimate. "PSU 850 W meets the **non-authoritative** reference of 423 W (sum of listed TDPs 325.0 W — CPU 125.0 W listed TDP, GPU 200.0 W listed TDP — plus 30%), but listed TDP values are not measured power consumption and connector requirements are unknown, so compatibility cannot be confirmed." |

Edge inputs (unchanged from M2 in shape, reworded):

| Input | State |
|---|---|
| `psu.wattage` missing | UNKNOWN, names `psu_specifications.wattage` |
| A present CPU/GPU lacks `tdp_w` | UNKNOWN, names the missing `*_specifications.tdp_w` |
| PSU selected, no CPU and no GPU | NOT_APPLICABLE — "nothing to size against" |

## Consequences

- **A full build can never aggregate to COMPATIBLE from power arithmetic.** This
  was already true for a different reason (the GPU-slot rule stays UNKNOWN —
  motherboards store a slot count, not a PCIe generation); the PSU tier removes
  the last path a TDP sum had to drive the aggregate green.
- **A dangerously small PSU is still caught.** `wattage < reference` remains a
  hard INCOMPATIBLE, so the floor constraint keeps its teeth while the green
  checkmark above it is gone.
- **Connector adequacy is never silently skipped.** Both branches declare
  `psu_specifications.pcie_8pin_count`, `psu_specifications.pcie_12vhpwr`, and
  GPU connector requirements in `missing_information` — the fields exist in the
  PSU schema, but GPU connector needs do not, so the comparison is never evaluated.

## Wording invariant

User-facing text for this rule may never use measured-power vocabulary: the words
**"draw"** and **"covers"** are banned from both explanation branches, and the
UNKNOWN branch must carry the literal label **"non-authoritative"** plus
"listed TDP". Verified by `test_unknown_explanation_is_non_authoritative_and_tdp_labeled`
and `test_incompatible_explanation_labels_tdp_reference`
(`backend/app/services/test_compatibility_rules.py`). The ban extends to the
internal rule-registry description
(`test_registry_descriptions_avoid_measured_power_language`).

Frontend mirror: `buildCompatibility.js` renders the same two-tier meaning with
the same restraint (`"It is not a measured system draw and not a PSU
manufacturer requirement."`), and Task 4's `LISTED_TDP_NOTICE` is the single
authoritative disclaimer for the Intelligence panel — see `M2_5_UX_DECISIONS.md`.

## What is deliberately still not evaluated

- ❌ Actual system power draw (no measurement data exists)
- ❌ PSU connector adequacy (GPU connector needs unrecorded)
- ❌ Transient/spike behaviour, efficiency curves, PSU age or rail quality
- ❌ Recommended wattage for a future upgrade path

## Worked example (preview fixture build A, verified in evidence)

CPU 125 W listed TDP + GPU 200 W listed TDP = 325 W sum → reference
`floor(325 × 1.3 + 0.5) = 423 W`. A 850 W PSU → **UNKNOWN** with the
non-authoritative label and connector gaps; a 450 W PSU against a 598 W
reference would be **INCOMPATIBLE**. Aggregate of the six-slot build: UNKNOWN —
the designed honest outcome, captured in `dom-checks.json` and discussed in the
delivery report's limitations.
