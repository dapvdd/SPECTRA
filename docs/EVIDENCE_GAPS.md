# EVIDENCE_GAPS — Hardware Decision Intelligence

**Status:** current snapshot from `docs/fan/completeness_audit.json`
**Scope:** known data gaps and their impact on the suitability / evidence /
recommendation features.

Nothing below is estimated. Every figure is drawn from the read-only
completeness audit over `data/spectra.db` and the source registry. Where a
field is unknown it is stated as unknown, never filled in.

---

## 1. Benchmark coverage

| Hardware | Total records | With a benchmark | Coverage |
|---|---|---|---|
| CPU | 3,501 | 518 | 14.8% |
| GPU | 1,879 | 0 | 0.0% |

**Benchmark distribution (all Geekbench 7):**

| Test type | Count |
|---|---|
| `multi-core` | 520 |
| `single-core` | 520 |

There are **zero GPU benchmark rows** in this dataset. GPU suitability for
`gaming` is therefore spec-based only (capped, reduced confidence), and `ai_ml`
is unrated for both CPU and GPU because there is no VRAM / CUDA / OpenCL
benchmark evidence.

## 2. Spec completeness (key fields non-null)

| Hardware | Total | Complete | Complete % |
|---|---|---|---|
| CPU | 3,501 | 2,659 | 75.9% |
| GPU | 1,879 | 1,339 | 71.3% |

CPU key fields: `cores`, `threads`, `base_clock_ghz`, `socket`, `tdp_w`.
GPU key fields: `memory_gb`, `memory_type`, `core_clock_mhz`,
`memory_bus_width_bits`, `tdp_w`.

## 3. No-evidence tier

`no_evidence_tier` (hardware with neither spec nor benchmarks nor provenance):
**0 CPU, 0 GPU.** Every row in the catalog carries at least some spec or
provenance evidence, so the "no evidence" unrated state is not expected to
surface for existing data.

## 4. Fields without provenance (by category)

Specification and benchmark fields are individually provenanced across 546
(PassMark CPU) … 1,081,600 (Geekbench Browser) provenance records. Not every
row carries a verified `field_provenance` record. The evidence-quality signal
`provenance` is only satisfied by a `verified` record; rows without one are
scored lower on that signal and their ratings carry a "no verified provenance"
caveat. Precise per-field provenance coverage is queryable via the provenance
API (`/hardware/{id}/provenance`).

## 5. Why AI/ML cannot be rated

`ai_ml` maps to **no supported benchmark family** in this dataset. Rating AI/ML
suitability requires GPU performance / VRAM evidence (for example CUDA or
OpenCL benchmark data), and there are zero GPU benchmark rows. Consequently:

- every `ai_ml` rating returns `unrated` with
  `insufficient_data:no_gpu_benchmarks`;
- evidence quality for `ai_ml` is never `high`.

## 6. Scoring / feature gaps

- **GPU gaming** — spec-based only; capped at 3 stars; lowered confidence.
- **CPU gaming / workstation** — benchmark-driven for the 518 benchmarked CPUs.
- **`budget_max`** — accepted by the recommend API but has no effect: there is
  no priced field in this dataset. Deferred until a licensed pricing source is
  integrated (see roadmap 3.4).
- **Comparison pre-population from recommendations** — the Hardware Fit modal's
  "Compare" affordance is wired but full pre-population of the comparison view
  from a recommended candidate is a deferred polish item.

## 7. Remaining data-collection priorities (ranked by impact)

1. **Licensed GPU benchmark source** — closes the 0% GPU gap, enables rated
   `gaming` / `ai_ml`. Highest impact; gated on a clear-license source.
2. **CPU benchmark expansion** — raise 14.8% → higher coverage so more CPUs are
   benchmark-driven rather than spec-based.
3. **Verified provenance on remaining rows** — raise the `provenance` signal
   so more ratings reach `high` evidence confidence.
4. **Pricing source** — unlock `budget_max` filtering.

## 8. Licensing notes

| Source | License status | License |
|---|---|---|
| Geekbench Browser — Geekbench 7 CPU | `unknown` | — (browser.geekbench.com) |
| PassMark CPU benchmark catalog | `restricted` | — (cpubenchmark.net) |
| TechPowerUp GPU Database | `restricted` | — (techpowerup.com/gpu-specs) |
| GPU Ark GPU specs & benchmarks | `clear` | CC BY 4.0 |
| Wikipedia (English) | `clear` | CC BY-SA 4.0 |
| Intel ARK / AMD specs snapshots | `unknown` | — |

Restricted or unknown-license sources are used as **reference-only**; they are
never bulk-reused. GPU benchmark integration (priority 1 above) must come from
a source that passes the four gates: license clear, provenance, accessibility,
reproducibility — as required by the roadmap.
