# Batch 006 - Phase 4: Preflight and Migration Test

- Model updated (backend/app/models/gpu.py) with memory_bus_width_bits (Integer, nullable).
- Test schema contract updated.
- Migration applied to live DB: added column if missing (idempotent). 
- Validated patch on temp copy: all entries reference valid GPU hardware/spec rows, target field is NULL-only, values are valid positive ints. 
- No framework introduced; used ALTER TABLE ADD COLUMN (SQLite). Safe and reversible in practice.
- Compatibility: Base.metadata.create_all() will create new DBs with column; existing code paths unaffected.
