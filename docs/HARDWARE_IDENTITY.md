# SPECTRA Hardware Identity

## 1. Purpose

SPECTRA separates the internal identity of a hardware product from
external identifiers and display names provided by data sources.

A hardware entity must have one stable SPECTRA identity while being
able to reference multiple external representations.

---

## 2. Identity Layers

### SPECTRA Internal Identity

The SPECTRA database assigns its own internal identifier.

This identifier is the primary identity used by the application.

It must not depend on an external dataset.

### Canonical Name

A normalized human-readable hardware name used by SPECTRA.

Examples:

- AMD Ryzen 5 5600
- Intel Core i5-12400F

Trademark symbols and source-specific naming suffixes may be removed
during normalization.

### External Identity

External datasets may provide their own identifiers.

Examples:

- Intel CpuId
- AMD Product ID
- Source-specific CPU identifiers

External identifiers must be preserved because they provide stronger
identity references than display names alone.

---

## 3. Identity Principle

SPECTRA must not assume that two records are different hardware merely
because their names differ.

Examples:

- AMD Ryzen™ 5 5600
- AMD Ryzen 5 5600
- Ryzen 5 5600

may refer to the same hardware.

Conversely, similar names must not automatically be treated as the
same hardware without sufficient evidence.

---

## 4. Source Mapping

A hardware entity may have multiple external identifiers.

Conceptually:

Hardware
    |
    +-- Source: AMD
    |      +-- Product ID
    |
    +-- Source: Intel
    |      +-- CpuId
    |
    +-- Source: Other Dataset
           +-- Source-specific identifier

This allows multiple sources to describe the same hardware without
duplicating the core hardware entity.

---

## 5. Identity Resolution

Identity resolution may use multiple signals:

- External identifier
- Manufacturer
- Canonical name
- Model number
- Socket
- Core count
- Thread count
- Release date
- Other source-specific attributes

Name matching alone should not be considered sufficient for
high-confidence identity resolution.

---

## 6. Internal vs External Identity

The following concepts must remain separate:

- SPECTRA internal ID
- Canonical hardware name
- External source identifier
- Raw source name

This separation allows source data to change without changing the
identity of the SPECTRA hardware entity.