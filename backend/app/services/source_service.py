"""Read-only source-transparency service (Batch 015).

Exposes the provenance that already exists in ``field_provenance`` together
with the ``sources`` registry, without writing anything. It deliberately
reuses the existing relationships:

- specification provenance is keyed by ``hardware_id`` with a NULL
  ``benchmark_result_id``;
- benchmark provenance is keyed by ``benchmark_result_id``;
- the source registry supplies publisher/licence/attribution metadata.

Queries are batched (``selectinload`` / grouped aggregates) so a hardware
detail or benchmark lookup never triggers an N+1 query. When a source row
predates the Batch 015 metadata columns the register is used as a read-only
fallback, so a missing value is reported as unknown rather than invented.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.app.database import SessionLocal
from backend.app.models import (
    BenchmarkResult,
    FieldProvenance,
    Hardware,
    Source,
)
from backend.app.source_registry import registered_metadata

# Ordered specification fields per provenance table. The order is fixed so the
# API response is deterministic and easy to assert in tests.
SPEC_FIELD_ORDER: dict[str, tuple[str, ...]] = {
    "hardware": ("release_date", "architecture"),
    "cpu_specifications": (
        "cores",
        "threads",
        "base_clock_ghz",
        "boost_clock_ghz",
        "tdp_w",
        "process_node_nm",
        "socket",
    ),
    "gpu_specifications": (
        "memory_gb",
        "memory_type",
        "core_clock_mhz",
        "boost_clock_mhz",
        "vram_bandwidth_gbps",
        "memory_bus_width_bits",
        "tdp_w",
        "interface",
        "length_mm",
    ),
}

_SOURCE_FIELDS = (
    "publisher",
    "description",
    "license_name",
    "license_url",
    "license_status",
    "terms_notes",
    "attribution",
    "retrieved_on",
)

_FIELD_STATUS_ORDER = ("verified", "uncertain", "excluded", "unmatched")


class ProvenanceLookupError(ValueError):
    """Raised when a requested hardware/benchmark/source id is unknown."""


def _source_dict(source: Source | None) -> dict | None:
    if source is None:
        return None
    entry = registered_metadata(source.id, source.name) or {}

    def value(field: str):
        current = getattr(source, field, None)
        if current is not None:
            return current
        return entry.get(field)

    data = {
        "id": source.id,
        "name": source.name,
        "url": source.url,
    }
    for field in _SOURCE_FIELDS:
        data[field] = value(field)
    return data


def _record_dict(record: FieldProvenance, source: dict | None) -> dict:
    source = source or {}
    return {
        "id": record.id,
        "source_id": record.source_id,
        "source_name": source.get("name"),
        "publisher": source.get("publisher"),
        "source_url": record.source_url,
        "table_name": record.table_name,
        "field_name": record.field_name,
        "evidenced_value": record.evidenced_value,
        "evidence_status": record.evidence_status,
        "confidence": record.confidence,
        "access_date": record.access_date,
        "source_reference": record.source_reference,
        "match_method": record.match_method,
        "batch_no": record.batch_no,
        "recorded_at": record.recorded_at,
        "license_name": record.license_name or source.get("license_name"),
        "license_status": source.get("license_status"),
        "license_notes": record.license_notes,
        "attribution": record.attribution or source.get("attribution"),
    }


def _field_status(records: list[dict], has_value: bool) -> str:
    """Deterministic field-level status from its serialized records."""
    if not records:
        return "unattributed" if has_value else "unavailable"
    for candidate in _FIELD_STATUS_ORDER:
        if any(item["evidence_status"] == candidate for item in records):
            return candidate
    return "unavailable"


def _spec_value(hardware: Hardware, table_name: str, field_name: str):
    if table_name == "hardware":
        return getattr(hardware, field_name, None)
    specification = (
        hardware.cpu_specification
        if table_name == "cpu_specifications"
        else hardware.gpu_specification
    )
    if specification is None:
        return None
    return getattr(specification, field_name, None)


def list_sources() -> list[dict]:
    """Return every registered source with its provenance usage counts."""
    with SessionLocal() as session:
        usage_rows = session.execute(
            select(
                FieldProvenance.source_id,
                func.count(FieldProvenance.id),
                func.count(func.distinct(FieldProvenance.hardware_id)),
                func.count(func.distinct(FieldProvenance.benchmark_result_id)),
            ).group_by(FieldProvenance.source_id)
        ).all()
        usage = {
            row[0]: {
                "provenance_records": int(row[1] or 0),
                "hardware_records": int(row[2] or 0),
                "benchmark_records": int(row[3] or 0),
            }
            for row in usage_rows
        }

        sources = session.scalars(select(Source).order_by(Source.id)).all()
        results = []
        for source in sources:
            data = _source_dict(source)
            data["usage"] = usage.get(
                source.id,
                {
                    "provenance_records": 0,
                    "hardware_records": 0,
                    "benchmark_records": 0,
                },
            )
            results.append(data)
        return results


def get_source(source_id: int) -> dict:
    with SessionLocal() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise ProvenanceLookupError(f"Source not found: {source_id}")

        usage_row = session.execute(
            select(
                func.count(FieldProvenance.id),
                func.count(func.distinct(FieldProvenance.hardware_id)),
                func.count(func.distinct(FieldProvenance.benchmark_result_id)),
            ).where(FieldProvenance.source_id == source_id)
        ).one()

        data = _source_dict(source)
        data["usage"] = {
            "provenance_records": int(usage_row[0] or 0),
            "hardware_records": int(usage_row[1] or 0),
            "benchmark_records": int(usage_row[2] or 0),
        }
        return data


def get_hardware_provenance(hardware_id: int) -> dict:
    """Return specification and benchmark provenance for one hardware item."""
    with SessionLocal() as session:
        hardware = session.scalar(
            select(Hardware)
            .options(
                selectinload(Hardware.cpu_specification),
                selectinload(Hardware.gpu_specification),
            )
            .where(Hardware.id == hardware_id)
        )
        if hardware is None:
            raise ProvenanceLookupError(f"Hardware not found: {hardware_id}")

        spec_records = session.scalars(
            select(FieldProvenance)
            .options(selectinload(FieldProvenance.source))
            .where(
                FieldProvenance.hardware_id == hardware_id,
                FieldProvenance.benchmark_result_id.is_(None),
            )
            .order_by(FieldProvenance.id)
        ).all()

        records_by_field: dict[tuple[str, str], list[dict]] = {}
        for record in spec_records:
            records_by_field.setdefault(
                (record.table_name, record.field_name), []
            ).append(_record_dict(record, _source_dict(record.source)))

        tables = ["hardware"]
        if hardware.type == "CPU":
            tables.append("cpu_specifications")
        elif hardware.type == "GPU":
            tables.append("gpu_specifications")

        fields = []
        summary = {
            "total_fields": 0,
            "verified_fields": 0,
            "uncertain_fields": 0,
            "excluded_fields": 0,
            "unmatched_fields": 0,
            "unattributed_fields": 0,
            "unavailable_fields": 0,
        }
        for table_name in tables:
            for field_name in SPEC_FIELD_ORDER[table_name]:
                value = _spec_value(hardware, table_name, field_name)
                has_value = value is not None and value != ""
                records = sorted(
                    records_by_field.get((table_name, field_name), []),
                    key=lambda item: item["id"],
                )
                status = _field_status(records, has_value)

                fields.append(
                    {
                        "table_name": table_name,
                        "field_name": field_name,
                        "has_value": has_value,
                        "status": status,
                        "records": records,
                    }
                )
                summary["total_fields"] += 1
                summary[f"{status}_fields"] += 1

        benchmark_rows = session.execute(
            select(FieldProvenance, BenchmarkResult)
            .join(
                BenchmarkResult,
                FieldProvenance.benchmark_result_id == BenchmarkResult.id,
            )
            .options(selectinload(FieldProvenance.source))
            .where(FieldProvenance.hardware_id == hardware_id)
            .order_by(FieldProvenance.benchmark_result_id, FieldProvenance.id)
        ).all()

        benchmark_groups: dict[int, dict] = {}
        for record, benchmark in benchmark_rows:
            group = benchmark_groups.get(benchmark.id)
            if group is None:
                group = {
                    "benchmark_result_id": benchmark.id,
                    "benchmark_name": benchmark.benchmark_name,
                    "unit": benchmark.unit,
                    "test_type": benchmark.test_type,
                    "score": benchmark.score,
                    "records": [],
                }
                benchmark_groups[benchmark.id] = group
            group["records"].append(
                _record_dict(record, _source_dict(record.source))
            )

        return {
            "hardware_id": hardware.id,
            "hardware_name": hardware.name,
            "hardware_type": hardware.type,
            "fields": fields,
            "benchmarks": list(benchmark_groups.values()),
            "summary": {
                key: summary[key]
                for key in (
                    "total_fields",
                    "verified_fields",
                    "uncertain_fields",
                    "excluded_fields",
                    "unmatched_fields",
                    "unattributed_fields",
                    "unavailable_fields",
                )
            },
        }


def get_benchmark_provenance(benchmark_result_id: int) -> dict:
    with SessionLocal() as session:
        benchmark = session.scalar(
            select(BenchmarkResult)
            .options(
                selectinload(BenchmarkResult.source),
                selectinload(BenchmarkResult.field_provenance).selectinload(
                    FieldProvenance.source
                ),
            )
            .where(BenchmarkResult.id == benchmark_result_id)
        )
        if benchmark is None:
            raise ProvenanceLookupError(
                f"Benchmark not found: {benchmark_result_id}"
            )

        records = [
            _record_dict(record, _source_dict(record.source))
            for record in sorted(
                benchmark.field_provenance, key=lambda item: item.id
            )
        ]

        return {
            "benchmark_result_id": benchmark.id,
            "hardware_id": benchmark.hardware_id,
            "benchmark_name": benchmark.benchmark_name,
            "unit": benchmark.unit,
            "test_type": benchmark.test_type,
            "score": benchmark.score,
            "source": _source_dict(benchmark.source),
            "records": records,
        }
