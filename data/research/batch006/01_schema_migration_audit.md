# Batch 006 - Phase 1: Schema and Migration Audit

Date: 2026-10-09

## Current GPU specification model
- Model: backend/app/models/gpu.py (SQLAlchemy ORM)
  - Table: gpu_specifications
  - Columns: id, hardware_id (FK, unique), memory_gb, memory_type, core_clock_mhz, boost_clock_mhz, vram_bandwidth_gbps, tdp_w, interface, length_mm
- All fields nullable (tests confirm). hardware_id is FK to hardware.id, unique (1:1).

## Database initialization/migration conventions
- Uses SQLAlchemy Base.metadata.create_all() (database.py, tests use same). No Alembic/migrations directory found.
- Models imported via backend.app.models.__init__. Tests create schema from metadata.
- Production DB file is data/spectra.db (SQLite). App uses DATABASE_URL env var.
- No established versioned migration framework present.

## Schema contract
- test_gpu_specifications_columns_match_contract expects exact column set (10 columns). Adding a new column will change this contract.

## Frontend/backend references
- No existing references to memory_bus_width/bus_width found in backend/frontend code (searched). So adding field is additive but may require model/schema updates.

## Chosen design
- Add column memory_bus_width_bits to gpu_specifications table (INTEGER or FLOAT? bus width is integer bits, e.g. 64, 128, 256). Use Integer for bits.
- Make nullable to preserve existing rows.
- Update SQLAlchemy model (GPUSpecification) with mapped column.
- Update models/__init__ exports (no direct change needed usually).
- Update tests if they assert exact column sets - the existing contract test will fail if we add column; but the instruction says "add focused tests for the new field" and also says "run tests". We need to be careful - but the column contract is part of test; better to update the model and tests to include the new column as per the new schema.
- Migration strategy: since no versioned migrations exist, perform a small idempotent schema migration on the DB. Use ALTER TABLE to add column if missing (SQLite supports ALTER TABLE ADD COLUMN). Do it transactionally where possible. Also update metadata creation path (model already defines it).
- For existing DBs, adding nullable column is safe and backward compatible.

## Compatibility considerations
- Adding nullable INTEGER column to SQLite: ALTER TABLE ADD COLUMN memory_bus_width_bits INTEGER; safe.
- Idempotent: check if column exists via PRAGMA table_info before adding.
- Do not drop/recreate tables. Preserve all data.
- Backup before migration.

## Requirements summary
- New field: memory_bus_width_bits (nullable). Units: bits (explicit). Type: Integer (bits are discrete).
- Update model + tests that enforce schema contract. Update any code that serializes GPU specs if needed? Check API responses - let us look.

## Findings
- No migration framework (Alembic/migrations) detected. Schema created via Base.metadata.create_all().
- Model is canonical schema definition (SQLAlchemy). Tests enforce schema contract.
- GPU Ark has 'bus_width' in bits. Target: memory_bus_width_bits (INTEGER, nullable).
- Adding nullable column to existing SQLite DB is safe via ALTER TABLE ADD COLUMN if missing.
