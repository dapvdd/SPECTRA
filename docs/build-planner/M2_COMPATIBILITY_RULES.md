# M2 Compatibility Rules — Build Planner

Version: **`M2-RULES-v1`** · Branch `feat/build-planner-m2-compatibility` · 2026-11-11

Deterministic, read-only rule engine over the six Build Planner categories.
Every rule is a pure function over plain spec dicts; missing data yields
**UNKNOWN naming the missing field** — it is never treated as compatibility.

## Core semantics

| State | Meaning |
|---|---|
| `COMPATIBLE` | All fields required by the rule exist and the check passed. |
| `INCOMPATIBLE` | All fields exist and the check failed (hard conflict). |
| `UNKNOWN` | A required field is missing, or the schema cannot express the check. |
| `NOT_APPLICABLE` | The rule's components are absent, or the hardware isn't of the kind the rule covers (e.g. non-PCIe GPU). Does not block COMPATIBLE. |

Aggregation (`evaluate_rules`):
1. Any `INCOMPATIBLE` → **INCOMPATIBLE** (most safety-relevant outcome wins).
2. Else any `UNKNOWN` → **UNKNOWN** (unresolved required checks).
3. Else → **COMPATIBLE** (all applicable checks confirmed).
4. No applicable rules at all → **UNKNOWN** (an empty build proves nothing).

## Rule registry (stable IDs)

### R1 · `cpu-motherboard-socket`
- **Compares:** `cpu_specifications.socket` ↔ `motherboard_specifications.socket`
- **Logic:** exact string match → COMPATIBLE; mismatch → INCOMPATIBLE; either missing → UNKNOWN.
- **Boundary:** a socket match **does not claim BIOS support** (no BIOS data exists) — the explanation states this verbatim.

### R2 · `ram-motherboard-generation`
- **Compares:** `ram_specifications.ddr_generation` ↔ `motherboard_specifications.ram_type`
- **Logic:** exact match → COMPATIBLE; mismatch (e.g. DDR4 vs DDR5) → INCOMPATIBLE; either missing → UNKNOWN.
- **Boundary:** nominal speed above board spec is **not evaluated** (no XMP/QVL data); speed never decides.

### R3 · `ram-motherboard-capacity`
- **Compares:** `ram_specifications.capacity_gb` ≤ `motherboard_specifications.max_ram_gb`
- **Logic:** within/at max → COMPATIBLE; over → INCOMPATIBLE; either missing → UNKNOWN.

### R4 · `ram-motherboard-slots`
- **Compares:** `ram_specifications.modules` ≤ `motherboard_specifications.ram_slots`
- **Logic:** fits → COMPATIBLE; exceeds → INCOMPATIBLE; either missing → UNKNOWN.

### R5 · `storage-motherboard-interface`
- **Compares:** `storage_specifications.storage_type` vs `motherboard_specifications.m2_slots` / `sata_ports`
- **Logic:**
  - NVMe: `m2_slots > 0` → COMPATIBLE; `= 0` → INCOMPATIBLE; not recorded → UNKNOWN.
  - SATA SSD/HDD: `sata_ports > 0` → COMPATIBLE; `= 0` → INCOMPATIBLE; not recorded → UNKNOWN.
- **Boundary:** per-slot M.2 keying/protocol is **not modeled**; M.2-borne SATA is not claimed either way.

### R6 · `psu-build-wattage`
- **Compares:** `psu_specifications.wattage` vs (CPU TDP + GPU TDP) × 1.30
- **Logic:** `wattage ≥ required` → COMPATIBLE; below → INCOMPATIBLE; missing wattage or any present-component TDP → UNKNOWN.
- **Policy:** headroom is a documented **30% of summed TDP** (`PSU_HEADROOM_FRACTION = 0.3`) — an explicit, simple policy, not a fabricated load curve.
- **Boundary:** PSU connector requirements are **not evaluated** (GPU connector data absent). With a PSU but no CPU/GPU selected → NOT_APPLICABLE.

### R7 · `gpu-motherboard-slot`
- **Compares:** `gpu_specifications.interface` vs `motherboard_specifications.pcie_slots`
- **Logic:**
  - `pcie_slots = 0` → INCOMPATIBLE.
  - `pcie_slots > 0` → **UNKNOWN**: slot count alone cannot confirm generation/clearance fit.
  - Interface missing or non-PCIe (e.g. Apple MPX) → NOT_APPLICABLE.
- **Boundary:** the motherboard schema records only the *number* of PCIe slots, so generation matching stays UNKNOWN. **This is why a fully-populated build never aggregates to COMPATIBLE at M2** — that is the designed honest outcome, not a bug.

## Explicit non-claims (verified by tests)

The engine never asserts anything the data cannot prove:
- ❌ BIOS support for a socket match
- ❌ XMP / QVL / memory speed validation
- ❌ M.2 keying or per-slot protocol
- ❌ PSU connector adequacy (8-pin / 12VHPWR vs GPU needs)
- ❌ PCIe generation or signal/clearance fit
- ❌ Case clearance, cooling, or physical fitment

## Provenance

Each rule result lists the spec fields it consulted (`spec_fields`, as
`table.field`). The API attaches the matching `FieldProvenance` rows
(`benchmark_result_id IS NULL`) as provenance references; a reference
requires a `Source` record (NOT NULL). The engine itself performs **zero
database writes** (asserted by `test_no_database_writes`).

## Data requirements per rule

| Rule | Required fields (all must exist, else UNKNOWN) |
|---|---|
| R1 | `cpu.socket`, `motherboard.socket` |
| R2 | `ram.ddr_generation`, `motherboard.ram_type` |
| R3 | `ram.capacity_gb`, `motherboard.max_ram_gb` |
| R4 | `ram.modules`, `motherboard.ram_slots` |
| R5 | `storage.storage_type` + (`m2_slots` for NVMe / `sata_ports` for SATA) |
| R6 | `psu.wattage` + `tdp_w` of every present CPU/GPU |
| R7 | `gpu.interface`, `motherboard.pcie_slots` |
