# SPECTRA Normalization Rules

## 1. Purpose

External hardware datasets use different formats, naming conventions,
units, and representations.

SPECTRA normalizes external records before inserting them into the
normalized database.

---

## 2. Raw Data Preservation

Raw source data should be preserved before normalization whenever
practical.

Normalization must not destroy the original source representation.

Flow:

RAW DATA
    ↓
PARSER
    ↓
NORMALIZER
    ↓
VALIDATOR
    ↓
DATABASE

---

## 3. Name Normalization

Normalization may include:

- Removing trademark symbols such as ™ and ®
- Removing unnecessary whitespace
- Normalizing repeated whitespace
- Standardizing manufacturer naming
- Removing known source-specific descriptive suffixes when safe

Example:

`AMD Ryzen™ 5 7520C`

becomes:

`AMD Ryzen 5 7520C`

The original raw value must remain recoverable.

---

## 4. Numeric Normalization

External numeric fields may contain units or descriptive prefixes.

Examples:

`2.4GHz`
`3.70 GHz`
`15W`
`165 W`

SPECTRA should convert these into normalized numeric values.

Examples:

`2.4GHz` → `2.4 GHz`

`15W` → `15 W`

---

## 5. Clock Normalization

Clock values should be represented numerically in GHz.

Valid examples:

- `2.4GHz` → `2.4`
- `3.70 GHz` → `3.70`

Malformed values must not be silently accepted.

Example:

`2.001.0 GHz`

must be flagged for validation rather than converted through
guesswork.

---

## 6. Missing Values

Empty source fields must be represented as missing data.

An empty value must not automatically become:

- `0`
- `False`
- an invented date
- an invented specification

Missing data should remain distinguishable from a genuine zero value.

---

## 7. Date Normalization

Different source formats may be normalized into a consistent internal
representation.

Quarter-based dates such as:

`Q1 2021`

must retain their reduced precision rather than being assigned an
arbitrary exact date.

---

## 8. Validation

Normalized records should be validated before database insertion.

Validation should detect:

- malformed numeric values
- impossible core/thread values
- invalid dates
- missing required identity fields
- duplicate external identifiers
- inconsistent source records

Invalid records should be rejected or quarantined for review rather
than silently modified.

---

## 9. Source Provenance

Every imported record must remain traceable to its original source.

The normalized record must retain enough information to identify:

- source
- source record
- access or dataset date
- original identifier when available

---

## 10. Principle

Normalization changes representation, not meaning.

SPECTRA must never invent information that is absent from the source.