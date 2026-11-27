# M4 Residual Risks

**Version:** `M4-RISKS-v1.0`
**Branch:** `feat/m4-intelligence`
**Date:** 2026-11-26

Every item below is a **disclosed limitation**, not a hidden defect. Each
names what a user of the feature experiences, why it stands, and what
would resolve it. None of these were silently smoothed over by the engines —
each is surfaced in payloads (limitations, confidence, unknown states) or in
constraint echoes.

---

## R1. Multi-core anchor calibration drift (~24.7% at p90)

**What the user gets:** multi-core-derived stars sit lower at the top of the
range than a reader of the v1 methodology's example anchors would expect
(M3.3 measured multi-core p90 = 12311.2 vs the v1 doc example 16346.0,
≈ −24.7%).

**Why it stands:** M4 derives anchors from whatever population it is given
(`derive_anchors`, percentiles with linear interpolation) and never
hardcodes anchor values. The drift is a property of the measured M3.3
population, not an engine bug. The payload discloses provenance via
`reference_population`.

**What resolves it:** a recalibration study on a fresh benchmark import, or
an explicit anchor-override policy decision. Until then the drift is
documented (§2 of `M4_SCORING_METHODOLOGY.md`), not re-anchored.

## R2. No price data → VALUE is permanently UNKNOWN; budget never filters

**What the user gets:** the value scenario always renders
`score: null / unknown`; a `budget_max` constraint is echoed as `soft` with a
note that no price data exists — it never filters candidates.

**Why it stands:** the schema carries no price columns. Inventing prices or
filtering on absent data would fabricate precision — prohibited by the
mission's evidence gates.

**What resolves it:** a priced dataset (with `price_as_of` for staleness).
The value path is implemented and fixture-tested; it activates the moment
prices exist.

## R3. No GPU benchmark rows → GPU scores are spec-based and capped

**What the user gets:** GPU scenario scores (gaming/workstation/daily) are
spec-proxy derived, capped at 3.0 stars, confidence `medium`, with a visible
`spec_based` limitation. Balance in build intelligence treats a spec-only
GPU side as unknown.

**Why it stands:** the dataset contains no measured GPU benchmark rows;
spec proxies are a qualitative argument, disclosed as such.

**What resolves it:** importing GPU benchmark evidence (families already
exist in the feature layer; scoring activates automatically).

## R4. Spec-based reasoning caps by policy, not by measurement

**What the user gets:** any component without benchmark data tops out at
3.0/5.0 even if its specs are top-of-catalog. Cap violation is impossible by
construction (asserted in evaluation).

**Why it stands:** spec sheets do not measure workload performance; the cap
keeps estimated scores strictly below measured high scores.

**What resolves it:** measured benchmark coverage per family.

## R5. PSU reference is a formula, not a measurement

**What the user gets:** the build power reference is
`floor(total_tdp × 1.3 + 0.5)` W (reusing the M2.5
`PSU_TDP_REFERENCE_FRACTION = 0.3` arithmetic) from listed TDPs — no
measured system power exists. `power_limit_w` optimization advice is
advisory for the same reason; unknown-TDP components are labeled, never
guessed.

**Why it stands:** listed TDP is the only power evidence in the dataset.

**What resolves it:** measured platform power data.

## R6. Compatibility unknowns never exclude

**What the user gets:** a candidate whose compatibility state vs the
existing build is UNKNOWN (e.g., missing slot data) is *not* excluded from
recommendations; it appears with a note. Only a definitive INCOMPATIBLE
(engine-owned, M32-RULES-v2) excludes.

**Why it stands:** excluding on unknown data would silently hide valid
options; the mission mandates unknown ≠ incompatible.

**Cost if wrong:** a user might buy a part the engine could not verify —
mitigated by the note in the constraints echo and the build-intelligence
compatibility summary.

## R7. Optimizer is single-swap and bounded

**What the user gets:** at most 3 candidate swaps per slot, one component at
a time; no multi-swap co-optimization, no simulated global optimum.

**Why it stands:** bounded scope keeps suggestions explainable and
deterministic; joint-swap search would multiply speculative combinations on
sparse evidence.

**Cost if wrong:** the suggested sequence of single swaps may not reach the
globally best build. Disclosed in `M4_INTELLIGENCE_ARCHITECTURE.md` §6.

## R8. Snapshot fixture is read-only and must not regress CI

**What the user gets:** nothing directly (repo hygiene).

**Risk:** `data/spectra.db` must stay CI-fresh (migrations ≤ 1); the M3.3
518-CPU snapshot lives at `data/dev/m4_snapshot.db` as a read-only fixture.
Restoring it to `data/spectra.db` would break auth/observability tests that
pin migration state.

**Mitigation:** enforced by existing tests; documented here so the
placement is not reverted.

## R9. Frontend panels are build-verified, not DOM-tested

**What the user gets:** panels (ScenarioRatings, BuildIntelligencePanel,
v2 recommendation workspace) are wired additively; their display logic is
tested as pure modules (`node --test`, 11 tests), and the app builds and
lints clean — but there are no DOM/browser tests asserting the rendered
tree.

**What resolves it:** the browser acceptance pass planned as part of this
delivery (and/or future webapp-testing coverage).

## R10. AI digest inherits engine limitations

**What the user gets:** the chat digest repeats engine facts (scenario
scores, build intelligence, recommendations) verbatim with rules 43–45
forbidding the LLM from overriding states or inventing scores — so every
UNKNOWN above is equally visible (and equally limiting) in conversation.

**Why it stands:** the digest is a summarizer of authoritative engine
output, never a source.

## R11. Anchor provenance depends on the supplied population

**What the user gets:** scenario scores differ between the API route
(anchors derived from the live benchmarked population) and any consumer that
pins its own anchors (e.g., the AI digest, which derives anchors only from
the supplied benchmark context). Both are correct for their population;
cross-consumer star comparisons can differ.

**Why it stands:** anchors are defined as properties of the observed
population, not constants.

**What resolves it:** an explicit org-wide anchor policy if consumers need
identical scales.
