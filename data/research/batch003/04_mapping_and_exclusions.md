# Batch 003 — Mapping and Exclusions

## 1. Matching method (deterministic, no fuzzy matching)

For every CPU row whose target field is NULL:

1. **Normalize the CPU name** deterministically: lowercase; drop a trailing `@ <clock>`;
   drop parenthetical notes; remove the word `processor`; remove all non-alphanumeric
   characters; strip a leading `intel`/`amd`/`ati`.
   e.g. `Intel Core i5-12400F Processor` → `corei512400f`;
   `AMD Ryzen 5 5600` → `ryzen55600`.
2. **Build the same key** from the source row's combined branding + model
   (e.g. `Core i5 | 12400F` → `corei512400f`; `Ryzen 5 | 5600` → `ryzen55600`).
3. **Exact key match** to a source row. No subsequence, token, or fuzzy matching.
4. **Architecture = the source article's subject** (platform codename convention set by
   Batch 001). A model listed in the Kaby Lake article is a Kaby Lake CPU.
5. **Ambiguity guards:**
   - a key present in **more than one** architecture article → excluded (`multi_arch`),
   - a key matching **more than one hardware row** → excluded (`collision`),
   - `release_date`: only a single, full `Month D, YYYY` / `YYYY-MM-DD` value is accepted;
     quarter-only (`Q4'23`), year-only (`2017`) and range evidence is ignored,
   - `process_node_nm`: only for AMD rows whose source-confirmed architecture maps to a
     single documented node.

No value is invented, interpolated, or derived from a name pattern; every value is copied
from a source record.

## 2. Proposed values

| Field | Table | Proposed | Confidence |
|---|---|---:|---|
| `architecture` | hardware | **517** | high |
| `release_date` | hardware | **64** | high |
| `process_node_nm` | cpu_specifications | **16** | medium (family-level) |
| **Total** | | **597** | |

Architecture proposals by value:

| Architecture | Rows |
|---|---:|
| Coffee Lake | 106 |
| Alder Lake | 76 |
| Kaby Lake | 76 |
| Comet Lake | 74 |
| Skylake | 60 |
| Raptor Lake | 52 |
| Rocket Lake | 33 |
| Zen+ | 16 |
| Ice Lake | 12 |
| Broadwell | 7 |
| Tiger Lake | 2 |
| Whiskey Lake | 2 |
| Cannon Lake | 1 |

Manufacturer split of the 517 architecture fills: Intel 500, AMD 17.

Process-node proposals are all AMD Zen+-family APUs/CPUs (e.g. `Ryzen 3 3200G`,
`Ryzen 5 3400G`, `Athlon 300GE`), mapped to **12 nm** via the source article's
`Technology node` and Batch 001's AMD node convention. An independent check confirms the
existing AMD nodes in the database are consistent (values 5/7/12/14 only).

## 3. Exclusions

| Category | Count | Reason |
|---|---:|---|
| Collision (key → >1 hardware row) | 1 key / 2 rows | `pentiumg4560` matches both `1668 Intel Pentium Processor G4560` and `3350 Intel Pentium G4560 @ 3.50GHz`; ambiguous, both preserved |
| Multi-architecture key | 0 | none observed among database-matching keys |
| `boost_clock_ghz` | 1,076 NULL | source extraction unreliable (187 agree / 96 disagree on validation) — not imported |
| `tdp_w` | 277 NULL | source extraction unreliable (369 agree / 8 disagree) — not imported |
| `process_node_nm` (Intel) | 338 NULL | already predominantly populated; not a source-supported per-model gap |
| `process_node_nm` (non-Zen AMD) | 625 NULL | no reliable source mapping for pre-Zen/older parts |
| `release_date` | 3,248 NULL | only full-date evidence accepted; quarter/year-only rows ignored |

The full per-value list (including the two excluded collision rows) is in
`03_evidence_table.csv`; the apply-ready, guarded subset is in
`05_database_patch.json`.

## 4. Terminology and semantics recorded

- **Architecture naming**: platform/marketing codename is used (e.g. `Rocket Lake`, not
  the core `Cypress Cove`), matching the existing database convention.
- **AMD process node**: chiplet/CCD/primary node (Zen 14, Zen+ 12, Zen 2/3 7, Zen 4 5),
  matching Batch 001. I/O-die differences are not representable in the single column.
- **Release date**: retail/full launch date only; ambiguous quarter evidence left NULL.
- **Hybrid Intel parts**: no clock/power value imported, so P/E-core ambiguity does not
  arise.

## 5. Source reliability validation

- Intel architecture proposals cross-checked against the populated `process_node_nm`:
  **390 agree, 0 disagree** (Sandy Bridge 32, Ivy/Haswell 22, Broadwell/Skylake/Kaby/
  Coffee/Comet/Rocket/Whiskey 14, Alder/Raptor/Ice/Tiger/Cannon 10, Nehalem 45,
  Westmere 32).
- Release-date proposals cross-checked against existing values: **0 disagreements**.
- Source mislabel found and corrected before import: `wiki_Zen_2B` is the **Zen+**
  article, not Zen 2 (see `02_source_and_licence_audit.md` §3).
