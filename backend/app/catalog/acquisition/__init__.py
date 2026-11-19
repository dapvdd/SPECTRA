"""M3.1 catalog acquisition package (Task 2).

Reusable acquisition architecture for the M3.1 verified-data expansion:

- ``manifest``   — VerifiedSKU / FieldEvidence / CandidateRecord schema,
                   fail-closed validation, JSON roundtrip;
- ``resolver``   — deterministic MATCHED/REPLACED/UNRESOLVED/INVALID
                   classification of inventory candidates;
- ``pipeline``   — dedup + conflict quarantine + bounded batches +
                   checkpointing + idempotent publish through the existing
                   M3 publisher;
- ``errors``     — source error classification + deterministic backoff.
"""
from backend.app.catalog.acquisition.errors import (
    ERROR_KINDS,
    SourceError,
    classify_exception,
    retry_delay,
)
from backend.app.catalog.acquisition.manifest import (
    CandidateRecord,
    FieldEvidence,
    VerifiedSKU,
    load_manifest,
    new_manifest,
    save_manifest,
    validate_manifest,
)
from backend.app.catalog.acquisition.pipeline import run_acquisition

__all__ = [
    "ERROR_KINDS",
    "CandidateRecord",
    "FieldEvidence",
    "SourceError",
    "VerifiedSKU",
    "classify_exception",
    "load_manifest",
    "new_manifest",
    "retry_delay",
    "run_acquisition",
    "save_manifest",
    "validate_manifest",
]
