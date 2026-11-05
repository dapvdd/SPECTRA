"""Reusable, behavior-identical normalization primitives for SPECTRA ingestion.

These primitives are the shared foundation promoted out of the importer-local
normalizers (previously `backend/app/importers/benchmark_normalizer.py`) so
that new catalogs (RAM/SSD) and existing importers reuse one tested home
instead of duplicating the logic. The existing importer modules keep their
public API unchanged by delegating to this package.
"""

from backend.app.normalization.primitives import (
    parse_int,
    parse_watt,
    normalize_name,
    strip_invisible_characters,
)

__all__ = [
    "parse_int",
    "parse_watt",
    "normalize_name",
    "strip_invisible_characters",
]
