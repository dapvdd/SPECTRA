# SPECTRA Hardware Data Quality Audit

## 1. Purpose

This document records the Sprint 13 audit of the hardware dataset held in
`data/spectra.db`.

The audit covers CPU, GPU, and benchmark records, provenance coverage, and
hardware identity normalization. It records what was verified, what was
corrected, and what was deliberately left unchanged together with the
evidence for that decision.

The audit follows the principles in `NORMALIZATION_RULES.md` and
`HARDWARE_IDENTITY.md`. In particular, normalization changes representation
and not meaning, and SPECTRA never invents information absent from the
source.

---

## 2. Method

Every audit query ran against a SQLite connection opened in read-only mode
(`file:...?mode=ro`), so the inspection itself could not write to the
database.

The only write to the database was the single correction described in
section 10.

Baseline at the start of the audit:

- Database size: 880640 bytes
- Database modified: 2026-09-24 21:16:05

---

## 3. Dataset Inventory

| Table | Rows |
|---|---:|
| `hardware` | 5239 |
| `cpu_specifications` | 3360 |
| `gpu_specifications` | 1879 |
| `benchmark_results` | 1040 |
| `external_identifiers` | 3575 |
| `sources` | 3 |

Registered sources:

1. PassMark CPU benchmark catalog
2. Geekbench Browser, Geekbench 7 CPU
3. TechPowerUp GPU Database

---

## 4. The 0.025 W CPU TDP Investigation

### 4.1 Question

A CPU TDP of 0.025 W had been recorded as a suspected artifact. The audit
had to establish whether that value was a parsing defect or real data.

### 4.2 Finding

The value is real and is not an artifact.

Exactly one CPU carries it: `hardware.id` 3311,
`Intel Quark Microcontroller D1000`, manufacturer Intel, socket QFN40.

Provenance for the row:

- `external_identifiers.identifier_type`: `intel_cpu_id`
- `external_identifiers.external_id`: `86826`
- `external_identifiers.source_id`: 1 (PassMark CPU benchmark catalog)

The Intel Quark D1000 is a microcontroller in the Quark X1000 family, and
25 mW is its genuine published power figure. A `tdp_w` of 0.025 is that
figure expressed correctly in watts. Nothing in the stored row is
malformed: cores is 1, the value is positive, and no unit conversion was
applied on the way in.

### 4.3 Decision

The value was not modified.

Treating a small TDP as inherently suspect would mean assuming a minimum
plausible wattage. That threshold is not derivable from the data, it would
discard a correct sourced value, and it would classify genuine low-power
parts as missing. A microcontroller is not a general-purpose CPU, but the
row is correctly typed and correctly sourced for the catalog it came from,
so no reclassification is warranted either.

### 4.4 Why the value looked wrong

The low end of the CPU TDP distribution is entirely populated by real
low-power Intel parts, which is the strongest evidence that the import is
behaving correctly:

| id | Name | TDP W |
|---:|---|---:|
| 3311 | Intel Quark Microcontroller D1000 | 0.025 |
| 3298 | Intel Atom Processor Z500 | 0.65 |
| 3260 | Intel Atom Processor Z600 | 1.3 |
| 3288 | Intel Atom Processor Z515 | 1.4 |
| 3299 | Intel Atom Processor Z510 | 2.0 |

---

## 5. CPU Data Quality

### 5.1 Verified clean

No violations were found for any of the following, across all 3360 CPU
specification rows:

- `cores` is never zero or negative
- `threads` is never zero or negative
- `base_clock_ghz` is never zero or negative
- `boost_clock_ghz` is never zero or negative
- `process_node_nm` is never zero or negative
- `threads` is never lower than `cores`
- no orphaned specification rows, and no specification row attached to a
  non-CPU `hardware` row
- no CPU `hardware` row is missing its specification row
- no duplicate `(name, manufacturer, type)` group exists

NULL coverage is preserved as NULL rather than being defaulted:

- `tdp_w` is NULL for 288 of 3360 CPU rows
- CPU `hardware.release_date` is NULL for every CPU row

### 5.2 Recorded, not modified

Three AMD rows report a boost clock below the base clock:

| id | Name | Base GHz | Boost GHz |
|---:|---|---:|---:|
| 564 | 6376 | 2.3 | 2.0 |
| 572 | 6344 | 2.6 | 2.0 |
| 628 | 4280 | 2.8 | 2.2 |

All three names are bare model numbers, which is itself a source
limitation described in section 8.2.

The pattern is suggestive of a source column defect, but the correct
value cannot be derived without the original source extract, which is not
present in the repository. Inventing a replacement would violate the
no-invention principle, so the rows were left unchanged.

---

## 6. GPU Data Quality

### 6.1 Verified clean

No violations were found across all 1879 GPU specification rows:

- `memory_gb`, `core_clock_mhz`, `boost_clock_mhz`,
  `vram_bandwidth_gbps`, `tdp_w`, and `length_mm` are never zero or
  negative
- `boost_clock_mhz` is never below `core_clock_mhz`
- no orphaned rows, and no GPU specification attached to a non-GPU
  `hardware` row
- no GPU `hardware` row is missing its specification row

Observed ranges:

| Field | Min | Max | Non-null |
|---|---:|---:|---:|
| `tdp_w` | 4.0 | 1000.0 | 1675 |
| `memory_gb` | 1.0 | 128.0 | 1538 |
| `vram_bandwidth_gbps` | 6.4 | 6550.0 | 1538 |
| `length_mm` | 25.0 | 522.0 | 766 |

Manufacturer distribution is NVIDIA 876, AMD 722, Intel 175, ATI 106. The
legacy `ATI` brand is retained as its own value rather than being folded
into AMD, which preserves the source representation.

`memory_type` and `interface` retain their source vocabulary, including
`System Shared` and older `DDR2`/`DDR3` types. NULL is preserved for the
1030 rows with no `interface` value.

### 6.2 Recorded, not modified

`hardware.id` 5188 is named `B200 SXM 192 GB` but stores
`memory_gb` 96.0.

The name and the stored value disagree. The audit cannot determine which is
correct without the source extract, and it is not SPECTRA's place to
reconcile a marketing name against a specification field. The row was left
unchanged.

---

## 7. Benchmark Data Quality

### 7.1 Verified clean

Across all 1040 benchmark rows:

- `score` is never NULL and never zero or negative
- `benchmark_name`, `test_type`, and `unit` are never blank
- no benchmark row references a missing `hardware` row
- every benchmark row references an existing `sources` row
- all benchmarks belong to CPU hardware; no GPU has any benchmark

`benchmark_results` holds exactly two distinct measurements, both
`Geekbench 7` in `points`, from source 2:

| `test_type` | Rows | Min | Max |
|---|---:|---:|---:|
| `single-core` | 520 | 224.0 | 2723.0 |
| `multi-core` | 520 | 382.0 | 23305.0 |

The score ranges are consistent with Geekbench 7 for both test types.

### 7.2 Recorded, not modified

One hardware row holds three different `Geekbench 7 multi-core` scores:

`hardware.id` 20, `AMD Ryzen 7 7840U`

| id | Score |
|---:|---:|
| 574 | 10223.0 |
| 576 | 11656.0 |
| 990 | 8478.0 |

This is the only duplicate `(hardware_id, benchmark_name, test_type, unit,
source_id)` group in the table.

The three values differ, so they are not an exact-duplicate artifact that
can be collapsed without loss. Choosing among them would mean asserting
which submission is representative, which the data does not establish. All
three rows were left unchanged.

---

## 8. Hardware Identity Normalization

### 8.1 Corrected

Four CPU names contained a `U+200B ZERO WIDTH SPACE` character:

| id | Before | After |
|---:|---|---|
| 29 | `AMD Ryzen 7 7736U` + U+200B | `AMD Ryzen 7 7736U` |
| 74 | `AMD Ryzen 9 6900HS` + U+200B | `AMD Ryzen 9 6900HS` |
| 80 | `AMD Ryzen 7 6800U` + U+200B | `AMD Ryzen 7 6800U` |
| 85 | `AMD Ryzen 5 6600HS` + U+200B | `AMD Ryzen 5 6600HS` |

No other `hardware.name` value contains a character outside the printable
ASCII range, so the affected set is exactly these four rows.

Section 10 records the correction and its verification.

### 8.2 Recorded, not modified

46 CPU rows carry a bare model number as their name, for example `980`,
`6376`, `4340`, and `4234`, always with manufacturer AMD. Sockets such as
AM3, G34, C32, and FM2 indicate Athlon, Phenom, and Opteron parts whose
full product name the source catalog did not supply.

Restoring a full product name would require inventing text that the source
never provided. The rows were left unchanged.

The 14 rows named in section 5.2 are a subset of these.

### 8.3 Recorded, not modified

Some `external_identifiers.external_id` values pack more than one product
identifier into a single field, with inconsistent separators. Fourteen rows
contain a tab, a newline, or a double space, and two such values are shared
by two different hardware rows:

- `FP7:100-000000534 FP7r2:` + tab + `100-000000617` is stored for both
  `AMD Ryzen 7 7736U` and `AMD Ryzen 7 6800U`
- `FP7:100-000000546 FP7r2:` + tab + `100-000000562` is stored for three
  rows

11 `(source_id, identifier_type, external_id)` groups in total map to more
than one hardware row. This means `external_id` cannot be relied on as a
unique key for these source fields, which is consistent with the
`hardware_id` component of the existing uniqueness constraint.

Splitting these fields into one identifier per product would change the
provenance model rather than correct a value, so the rows were left
unchanged.

---

## 9. Provenance Coverage

### 9.1 Verified clean

- no `external_identifiers` row references a missing `hardware` row
- no `external_identifiers` row references a missing `sources` row
- no `external_identifiers` row has a blank `external_id` or
  `identifier_type`
- no `external_id` exceeds its 200-character column

`external_identifiers` holds only CPU identifiers, across four types from
source 1:

| `identifier_type` | Rows |
|---|---:|
| `intel_cpu_id` | 2675 |
| `product_id_tray` | 620 |
| `product_id_boxed` | 215 |
| `product_id_mpk` | 65 |

### 9.2 Recorded, not modified

Two coverage gaps exist. Both were left unchanged because closing them
would require either new provenance infrastructure or values the sources do
not provide.

**No GPU has an external identifier.** All 1879 GPU rows lack
`external_identifiers` coverage, even though source 3 is registered and is
the origin of the GPU dataset. Together with 78 CPU rows, 1957 of 5239
hardware rows have no external identifier. Some of the 78 CPUs do carry
benchmarks that were attached by name matching rather than by external
identifier.

**No benchmark has a `recorded_at` value.** All 1040 rows are NULL, so no
benchmark carries an access or observation date. Populating the column
would mean inventing a date, which is explicitly forbidden by
`NORMALIZATION_RULES.md` section 6.

---

## 10. Correction Applied

### 10.1 What changed

One correction was applied. Its motivation is that `U+200B` is a Unicode
format character: it is invisible in every interface, and it is not
Unicode whitespace, so it survives the whitespace collapsing that name
normalization performs. A name differing only by that character therefore
defeats exact-match identity resolution.

The defect was demonstrated before the change:

- `normalize_match_name` returned `amd ryzen 7 7736u` + U+200B for the
  stored name, and `amd ryzen 7 7736u` for the clean name, so the two did
  not compare equal
- `import_cpu` matches existing hardware on exact name equality, so
  re-importing these rows would have created duplicate hardware rather than
  updating the existing rows

Because the character carries no visible content, removing it changes the
representation and not the meaning of the name.

### 10.2 How it is applied

`backend/app/migrations/normalize_hardware_names.py` rewrites a stored name
only when it differs from its normalized form, which makes repeated runs
no-ops. It supports `--dry-run`.

```
python -m backend.app.migrations.normalize_hardware_names --dry-run
python -m backend.app.migrations.normalize_hardware_names
```

### 10.3 Safety measures

A backup was taken before the write, following the existing convention in
`data/backups/`:

`data/backups/spectra-pre-name-normalization-20260927-223031.db`, 880640
bytes, identical to the pre-correction database.

A full cell-level comparison of the live database against that backup was
performed after the write. The result was exactly four changed cells in the
whole database, being the four `hardware.name` values in the table in
section 8.1.

Every table row count was unchanged, and `cpu_specifications`,
`gpu_specifications`, `benchmark_results`, `external_identifiers`, and
`sources` had zero changed cells.

Post-correction invariants confirmed:

- no `hardware.name` contains an invisible character
- no `(name, manufacturer, type)` duplicate group was created; all four
  names were collision-free before the change
- the 0.025 W CPU TDP is still present
- 288 CPU rows and 204 GPU rows still hold a NULL `tdp_w`
- `benchmark_results` is unchanged at 1040 rows
- no GPU gained a benchmark

A second run reported 0 rows requiring normalization, confirming
idempotency against the live database.

### 10.4 Supporting code change

To stop the defect recurring, name normalization now removes Unicode
control and format characters, and wattage parsing was tightened. Both are
covered in section 11.

---

## 11. Objective Numeric Validation Rules

### 11.1 Wattage parsing

`parse_watt` previously matched the first digit run followed by a `w` under
`re.IGNORECASE`. That rule was not objective, and it produced wrong values
rather than missing values:

| Input | Old result | Correct result | New result |
|---|---|---|---|
| `-5 W` | 5.0 | missing | missing |
| `1e3 W` | 3.0 | missing | missing |
| `105 WW` | 105.0 | missing | missing |
| `Unspecified 1 waffle` | 1.0 | missing | missing |

The first two are the serious cases, because a signed or
scientific-notation value was silently reduced to a different, plausible
looking magnitude. A negative TDP and a 3 W TDP would both have been
stored as if they were real.

`parse_watt` now requires a plain non-negative decimal that is not part of
a longer numeric token, followed by a watt unit that ends at a word
boundary.

All well-formed inputs are unaffected, including `105 W`, `105W`,
`105 watts`, `65 W (TDP)`, `TDP 105W`, and the genuine sub-watt value
`0.025 W`. Input with no wattage, including `N/A`, `Unknown`, a bare `105`,
`65000 mW`, and a clock string, continues to return missing.

The rule is a unit and sign rule, not a magnitude threshold, so it adds no
arbitrary bounds to the dataset.

### 11.2 Validator bounds

`gpu_validator.validate_gpu` imposes fixed ranges: `memory_gb` 1 to 128,
`core_clock_mhz` and `boost_clock_mhz` 100 to 4000, and `tdp_w` 1 to 1500.

These bounds are not derived from the data and are not physically
necessary. The `memory_gb` ceiling of 128 is the clearest problem: the
dataset already contains a part named `B200 SXM 192 GB`, and a 192 GB part
would be rejected outright by the current rule.

These bounds were left unchanged. Tightening or removing them changes which
records an import accepts, and choosing new limits would mean inventing
thresholds. The concern is recorded here for a future decision.

No existing row violates any of these bounds, so nothing in the current
dataset is affected.

### 11.3 Consistency note

`cpu_validator.validate_cpu` accepts a manufacturer only if it is AMD or
Intel, while `benchmark_normalizer.detect_manufacturer` can also return
Apple, Qualcomm, Allwinner, ARM, or Unknown. The two paths disagree about
the accepted manufacturer set.

No row in the current dataset carries a manufacturer outside the validator
set, so there is no data impact today.

---

## 12. Build TDP Calculation and AI Context

### 12.1 TDP summation is safe

`calculateListedTdpSum` in `frontend/src/buildConfig.js` returns a value
only when both a CPU and a GPU listed TDP are present and positive. A
missing, zero, negative, non-finite, or non-numeric value yields no sum
rather than a partial or invented one. The sum is rounded for display only.

The AI system prompt states that a TDP sum is a manufacturer specification
figure and must not be presented as measured system draw or as a power
supply recommendation. No change was made to the build AI conversation.

### 12.2 Nulls and empty benchmarks are preserved

`toSpecificationsContext` writes a specification field whenever the value
is present, including an explicit `null`, so a missing specification
reaches the model as unknown rather than as absent or zero. Fields that are
`undefined` or non-scalar are omitted.

`pickBenchmarkRecords` returns an empty list when no benchmark array is
present, so a GPU with no benchmarks reaches the model as an empty
`benchmarks` array rather than as missing evidence.

The backend serializes the validated build with `model_dump(mode="json")`
and no `exclude_none`, so `null` survives into the JSON context.

This behavior was verified and already has test coverage in
`frontend/src/buildConfig.test.js`. No change was required.

---

## 13. Explicitly Out Of Scope

The following were not performed:

- No GPU benchmark ingestion. All 1879 GPU rows still have no benchmarks.
- No provenance redesign. The GPU identifier gap and the multi-identifier
  fields in section 8.3 were documented, not restructured.
- No reassignment of the 46 bare-number CPU names.
- No consolidation of the duplicate `AMD Ryzen 7 7840U` scores.
- No backfill of `recorded_at`, `release_date`, or any other NULL.
- No change to the build AI conversation, and no stateful conversation.
- No new numeric thresholds, and no performance, bottleneck, power supply,
  or recommendation features.

---

## 14. Summary

| Area | Result |
|---|---|
| CPU numeric integrity | Clean |
| GPU numeric integrity | Clean |
| Benchmark numeric integrity | Clean, one duplicate-score group recorded |
| Referential integrity | Clean across all tables |
| NULL semantics | Preserved throughout, no backfill |
| The 0.025 W TDP | Confirmed genuine, not modified |
| Invisible characters in names | 4 rows corrected, cause fixed in code |
| Wattage parsing | Two wrong-value defects fixed |
| Provenance coverage | Two gaps recorded, not closed |
| Database cells changed | 4 |
