# M3 Identity Rules

**Date**: 2026-11-16
**Contract parent**: `M3_DATA_CONTRACT.md` §3
**Implementation**: `backend/app/identity/` (Phase 1, TDD)

## 1. Identity layers

| Layer | Definition | Where stored |
|---|---|---|
| Product family | Marketing family grouping ("Trident Z5 RGB", "990 PRO", "B650 Tomahawk") | `hardware.product_family` (v4) |
| Product model | The cataloged product ("G.Skill Trident Z5 RGB 32 GB (2×16 GB) DDR5-6000 CL30") | `hardware.name` |
| Exact SKU / MPN | Manufacturer part number ("F5-6000J3038F16GX2-TZ5RK") | `external_identifiers` (`identifier_type='mpn'`) |
| Canonical identity | Deterministic key (§3) | `hardware.canonical_key` (v4, unique partial index) |

## 2. Identity resolution rules

R1. **Manufacturer normalization** (deterministic map, case/punct-insensitive):
    common aliases collapse ("G.SKILL"/"GSKILL"/"g.skill" → "G.Skill";
    "Western Digital"/"WD" → "Western Digital"; "Samsung Semiconductor" →
    "Samsung"). The normalized form is the display form; the map is a
    checked-in table (`manufacturer_aliases.py`) with tests. Unknown
    manufacturers keep their input (trimmed); they never silently map.

R2. **Kit vs module (RAM)**: a kit (modules > 1) and a single module are
    distinct identities even when total capacity matches. The canonical key
    encodes `kit-{modules}x{per_module}` or `module-1x{capacity}`. Example:
    "32 GB (2×16 GB) DDR5-6000" kit ≠ "32 GB (1×32 GB) DDR5-6000" module.

R3. **Capacity variants (Storage)**: 1 TB and 2 TB variants of the same
    product line are distinct SKUs (distinct canonical keys). Speed-tier
    variants documented by the manufacturer (e.g. 990 PRO 2 TB vs 990 PRO
    2 TB "with heatsink") are distinct when the official name differs; heatsink
    presence is part of the model name, not a separate key component.

R4. **Revision variants (Motherboard)**: a documented hardware revision
    (e.g. "REV 1.01", "rev 2.0") with compatibility-relevant changes may
    require a separate identity. Policy in M3: revision is recorded in the
    name/notes when documented; a separate canonical key is created only when
    the revision changes a compatibility-bearing field (BIOS/chipset/memory
    support). Revision-unknown records stay `identity_status='provisional'`
    when any doubt exists.

R5. **Regional variants**: regional suffixes (e.g. "(EU)", "(US)") are part of
    the model name; two regional variants with identical specifications are
    distinct records only when the manufacturer distinguishes them by MPN.
    Otherwise they resolve to one record.

R6. **No uncertain merges**: when two source rows disagree on a
    compatibility-bearing field (socket, generation, capacity, wattage), they
    become **conflict records** (Phase 3 pipeline) — never an automatic merge,
    never a silent overwrite. A human resolves via SUPERSEDED lifecycle, not
    by editing in place.

R7. **MPN is a pointer, not an identity**: an MPN row in
    `external_identifiers` links a hardware record to its SKU; two records
    sharing an MPN is a duplicate *signal* feeding the conflict pipeline. The
    canonical key decides; MPN never overrides R2-R5.

## 3. Canonical key construction (normative)

```
key = f"{manufacturer_norm}|{type}|{family_or_model_norm}|{variant_key}"
```

- `manufacturer_norm`: R1 output.
- `type`: hardware.type exactly (RAM / STORAGE / MOTHERBOARD / PSU).
- `family_or_model_norm`: normalized product family when set, else the
  normalized full name minus variant suffixes.
- `variant_key`:
  - RAM: `kit-{modules}x{capacity//modules}-ddr{gen}{speed}` where
    modules>1, else `module-1x{capacity}-ddr{gen}{speed}`. Missing
    generation/speed components are omitted (never "unknown").
  - STORAGE: `{storage_type}-{capacity_gb}gb-{interface_norm}`.
  - MOTHERBOARD: `{form_factor}-{socket}-{chipset}` (+ `-rev{n}` only per R4).
  - PSU: `{wattage}w-{efficiency_token}-{modularity}` where modularity ∈
    (nonmod, mod, unknown→omitted).
- All components NFKC + lowercase + whitespace-collapsed; empty components
  omitted; key length capped at 300 (VARCHAR(300)).

Determinism tests (Phase 1) pin: same inputs → byte-identical key; alias
inputs (G.SKILL vs gskill) → same key; kit vs module → different keys;
1 TB vs 2 TB → different keys.

## 4. Lifecycle interaction

- Records enter with `identity_status='confirmed'` only when manufacturer,
  family/model, and all variant components are unambiguous from the source.
- `identity_status='provisional'` records can reach VALIDATED but not
  APPROVED (Phase 4 gate); they surface in the duplicate-candidate report.
- SUPERSEDED records point at replacements via `superseded_by_id`; the old
  record is never deleted (build/build_conversation references must survive —
  existing FKs are preserved).

## 5. Worked examples (test fixtures)

| Input rows | Identity outcome |
|---|---|
| "G.SKILL Trident Z5 RGB 32GB (2x16GB) DDR5-6000 CL30", manufacturer "G.SKILL" | family "Trident Z5 RGB"; variant `kit-2x16-ddr56000`; key `g.skill|ram|trident z5 rgb|kit-2x16-ddr56000` |
| "Corsair Vengeance 32GB (1x32GB) DDR5-5600", manufacturer "Corsair" | variant `module-1x32-ddr55600` — **different key** from any 2×16 kit |
| "Samsung 990 PRO 1TB NVMe" vs "Samsung 990 PRO 2TB NVMe" | keys differ by `{capacity_gb}gb` — distinct SKUs |
| "ASUS TUF Gaming B650-PLUS WIFI" rev 1.0 vs rev 1.01, no compatibility change | same key; revision noted in record notes |
| "Corsair RM850x 850W 80 Plus Gold" (fully modular) vs "Corsair RM850 850W 80 Plus Gold" (nonmodular) | keys differ by modularity component — distinct SKUs |
| Two CSV rows, same canonical key, PSU wattage 850 vs 750 | conflict pair → quarantine for human resolution |
