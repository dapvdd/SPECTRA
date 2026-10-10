"""Deterministic base-import provenance reconstruction support (Batch 009).

Pure, side-effect-free helpers used by the Batch 009 reconstruction scripts
and their tests.

The rule that guides every decision:

    A source being plausible is not proof that a particular database value
    came from that source.

Consequences implemented here:

- A stored (table, field) value is claimed ``verified`` against a base-import
  dataset only when the stored value equals the normalized source value in
  exactly one of the documented source datasets.
- A value that is present in two or more distinct datasets is ``uncertain``:
  the source identity is ambiguous at value level and must never be stored as
  verified.
- A value that matches no dataset is ``unmatched`` and is kept in the
  reconciliation artifacts, never auto-persisted.

The module does not read source files and does not touch the database; it
operates on already-normalized source values so that the classification logic
can be unit-tested deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

# Evidence statuses that the existing ``field_provenance`` schema supports.
VERIFIED = "verified"
UNCERTAIN = "uncertain"

# ``excluded`` / ``unmatched`` are also supported by the schema but are never
# written for base-import reconstruction without explicit evidence of a
# deliberate exclusion decision or an unmatchable source entity.

# Field identity for every (table, column) that base-import provenance is
# allowed to record against, matching provenance_service.VALID_FIELDS.
VALID_FIELDS = {
    "hardware": frozenset({"release_date", "architecture"}),
    "cpu_specifications": frozenset({
        "cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w",
        "process_node_nm", "socket",
    }),
    "gpu_specifications": frozenset({
        "memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
        "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface",
        "length_mm",
    }),
}


@dataclass(frozen=True)
class CellDecision:
    """Outcome of classifying one populated database cell."""

    status: str
    dataset: str | None
    matching_row_count: int = 0
    matching_datasets: tuple[str, ...] = ()


def classify_cell(
    value,
    source_values_by_dataset: Mapping[str, object],
) -> CellDecision:
    """Classify a stored value against per-dataset collections of values.

    ``source_values_by_dataset`` maps a base-import dataset identifier to the
    collection of normalized source values for that (entity, field). Determine
    the exact-consistency status:

    - ``verified``      value is found in exactly one dataset
    - ``uncertain``     value is found in two or more datasets
    - ``unmatched``     value is found in no dataset
    - ``empty``         no source values are available at all
    """
    if value is None:
        return CellDecision("empty", None, 0, ())

    matching = [
        (dataset, sum(1 for source_value in values if source_value == value))
        for dataset, values in source_values_by_dataset.items()
        if value in values
    ]

    if not source_values_by_dataset:
        return CellDecision("empty", None, 0, ())

    if not matching:
        return CellDecision("unmatched", None, 0, tuple(sorted(source_values_by_dataset)))

    if len(matching) > 1:
        total_rows = sum(count for _, count in matching)
        return CellDecision(
            UNCERTAIN,
            None,
            total_rows,
            tuple(sorted(dataset for dataset, _ in matching)),
        )

    dataset, count = matching[0]
    return CellDecision(VERIFIED, dataset, count, (dataset,))


def build_source_value_map(
    normalized_rows_by_dataset: Mapping[str, object],
    field: str,
) -> dict[str, list]:
    """Collect normalized non-None values for ``field`` per dataset.

    ``normalized_rows_by_dataset`` maps dataset id -> iterable of normalized
    row dictionaries (each produced by the same normalizers the original
    import used, with drift-tolerant column resolution). Values are kept as an
    ordered list so that multiple source rows carrying the same value are
    counted (used to derive confidence).
    """
    result: dict[str, list] = {}
    for dataset, rows in normalized_rows_by_dataset.items():
        values = [
            row.get(field)
            for row in (rows or ())
            if row.get(field) is not None
        ]
        if values:
            result[dataset] = values
    return result