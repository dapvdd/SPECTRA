# SPECTRA Data Sources

## 1. Purpose

SPECTRA aggregates hardware specifications, benchmark results,
and other hardware-related data from multiple sources.

Data sources are treated as external inputs and must not be assumed
to be complete, current, or authoritative for every hardware category.

---

## 2. Source Principles

SPECTRA follows these principles:

### Data Provenance

Every externally sourced data point should be traceable to its source.

### Data Freshness

SPECTRA must distinguish between historical data and current data.

A dataset captured in a previous year must not automatically be
considered current.

### Source Independence

SPECTRA should not depend exclusively on a single external dataset.

### Raw Data Preservation

External data should be preserved before normalization or transformation
whenever practical.

### Validation Before Import

External data must be validated before being inserted into the
normalized SPECTRA database.

---

## 3. Initial Data Sources

### CPUWorld CPU Dataset

Repository:

https://github.com/felixsteinke/cpu-spec-dataset

Dataset:

`dataset/cpuworld-cpus.csv`

Purpose:

- Bootstrap CPU specification data
- Provide historical CPU coverage
- Test the SPECTRA data ingestion pipeline

Known limitation:

The dataset represents a historical snapshot and does not contain
the latest CPU generations.

For example, Intel coverage does not include newer generations such
as Intel Core Ultra, while AMD coverage is also limited to older
generations.

Therefore, this dataset must not be treated as the authoritative
current CPU database.

---

## 4. Data Lifecycle

External data follows this general lifecycle:

RAW DATA
    ↓
INGESTION
    ↓
PARSING
    ↓
NORMALIZATION
    ↓
VALIDATION
    ↓
SPECTRA DATABASE
    ↓
COMPARISON ENGINE

---

## 5. Source Metadata

SPECTRA should retain enough metadata to determine:

- where data originated
- when the data was accessed
- which dataset or source was used
- whether the data represents a historical snapshot
- which fields were transformed during ingestion

---

## 6. Future Sources

Potential future sources may include:

- Manufacturer specifications
- Hardware databases
- Benchmark databases
- Review websites
- Price sources
- Community-submitted data

Sources should be evaluated based on:

- coverage
- reliability
- freshness
- accessibility
- consistency
- licensing / usage rights

---

## 7. Current Strategy

CPUWorld is initially used as a bootstrap and ingestion-pipeline
testing source.

SPECTRA will progressively incorporate additional sources to improve
coverage and freshness.

No single source should be assumed to contain complete hardware data.