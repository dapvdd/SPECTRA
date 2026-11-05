"""Tests for the Stage 2 source-acquisition framework (SourceAdapter).

Pins the adapter contract + quarantine rules so every acquired value carries
verifiable provenance and unclear-permission evidence is quarantined rather
than silently published.
"""

from __future__ import annotations

import pytest

import backend.app.scripts.source_acquisition as sa
from backend.app.scripts.source_acquisition import (
    AcquiredValue,
    CsvSourceAdapter,
    SourceLicenseGate,
    build_acquired_value,
    register_adapter,
    acquire,
)


class _StubAdapter(CsvSourceAdapter):
    """A real adapter subclass pointing at a tiny in-memory dataset."""

    source_name = "Stub Benchmarks"
    source_url = "https://stub.example/bench.csv"
    license_status = "clear"
    license_name = "CC0-1.0"
    required_columns = ("cpu_name", "benchmark", "score")

    def map_record(self, row: dict[str, str]) -> dict:
        return {
            "cpu_name": row.get("cpu_name", "").strip(),
            "benchmark": row.get("benchmark", "").strip(),
            "score": row.get("score"),  # raw string; normalization is separate
        }

    def normalize_field_value(self, field: str, value: object) -> tuple[object, str]:
        if field == "score":
            try:
                return float(value), "points"
            except (TypeError, ValueError):
                return None, "points"
        return value, ""


def test_adapter_defines_required_metadata():
    adapter = _StubAdapter([{"cpu_name": "Ryzen 7", "benchmark": "GB6", "score": "100"}])
    assert adapter.source_name
    assert adapter.source_url
    assert adapter.license_status == "clear"
    assert adapter.license_name == "CC0-1.0"


def test_build_acquired_value_records_full_provenance():
    adapter = _StubAdapter([])
    value = build_acquired_value(
        adapter,
        hardware_name="AMD Ryzen 7 7700X",
        field="cores",
        raw_value="8",
        normalized_value="8",
        unit="cores",
        source_pointer="row 12",
    )
    assert value.hardware_name == "AMD Ryzen 7 7700X"
    assert value.field == "cores"
    assert value.raw_value == "8"
    assert value.normalized_value == "8"
    assert value.source_id == adapter.source_name
    assert value.source_url == adapter.source_url
    assert value.license_status == "clear"
    assert value.retrieved_at is not None
    assert value.validation_status == "proposed"
    assert value.confidence == "high"


def test_acquire_yields_one_value_per_record_field():
    adapter = _StubAdapter(
        [{"cpu_name": "AMD Ryzen 7 7700X", "benchmark": "GB6", "score": "12400"}]
    )
    acquired = acquire(adapter, field="score")
    assert len(acquired) == 1
    assert acquired[0].normalized_value == 12400.0
    assert acquired[0].unit == "points"


def test_clear_license_passes_gate():
    gate = SourceLicenseGate()
    adapter = _StubAdapter([])
    assert gate.verdict(adapter).allow is True


def test_restricted_license_is_quarantined():
    gate = SourceLicenseGate()

    class _Restricted(_StubAdapter):
        license_status = "restricted"

    assert gate.verdict(_Restricted([])).allow is False
    assert gate.verdict(_Restricted([])).reason


def test_unknown_license_is_quarantined_not_published():
    gate = SourceLicenseGate()

    class _Unknown(_StubAdapter):
        license_status = "unknown"

    verdict = gate.verdict(_Unknown([]))
    assert verdict.allow is False
    assert "quarantine" in verdict.action


def test_registry_roundtrip():
    adapter = _StubAdapter([])
    register_adapter("stub", lambda: adapter)
    assert sa.ADAPTER_REGISTRY["stub"] is not None


class _GpuArkAdapterForTest(sa.GpuArkAdapter):
    """Inherits the real mapping but loads from in-memory rows."""

    def __init__(self, rows):
        super().__init__(rows)


def test_gpuark_adapter_maps_real_columns_and_units():
    adapter = _GpuArkAdapterForTest(
        [
            {
                "name": "NVIDIA RTX 4090",
                "base_clock": "2235 MHz",
                "boost_clock": "2520 MHz",
                "ram": "24 GB",
                "ram_type": "GDDR6X",
                "bus_width": "384 bit",
                "tdp": "450 W",
                "cores": "16384",
                "sm_count": "128",
                "arch_name": "Ada Lovelace",
            }
        ]
    )
    mapped = adapter.map_record(adapter._rows[0])
    assert mapped["hardware_name"] == "NVIDIA RTX 4090"
    assert mapped["hardware_kind"] == "gpu"
    assert mapped["base_clock_mhz"] == "2235 MHz"
    assert mapped["memory_type"] == "GDDR6X"

    vals = {v.field: v for v in sa.acquire(adapter, field="tdp_w")}
    assert len(vals) == 1
    assert vals["tdp_w"].normalized_value == "450 W"
    assert vals["tdp_w"].unit == "W"
    assert vals["tdp_w"].license_status == "clear"

    empty = sa.acquire(adapter, field="boost_clock_mhz")[0]
    assert empty.normalized_value is not None  # present value survives
    # unknown value stays None, never invented
    assert empty.unit == "MHz"


def test_gpuark_missing_value_is_none_not_invented():
    adapter = _GpuArkAdapterForTest(
        [{"name": "Unknown GPU", "base_clock": "", "boost_clock": "", "ram": ""}]
    )
    acquired = sa.acquire(adapter, field="base_clock_mhz")
    assert acquired[0].normalized_value is None


# ---------------------------------------------------------------------------
# Sentinel-value regression tests — these values must become None, never
# written as fabricated hardware specifications.
# https://github.com/dapvdd/SPECTRA/issues/TBD-sentinel-data-quality
# ---------------------------------------------------------------------------

_SENTINEL_ROW = {
    "name": "NVIDIA RTX 4090",
    "base_clock": "", "boost_clock": "",
    "ram": "", "ram_type": "",
    "bus_width": "", "tdp": "",
    "cores": "", "sm_count": "",
    "arch_name": "",
}


class TestGpuArkSentinelNormalization:
    """RED → GREEN: GpuArkAdapter must treat missing-value sentinels as None.

    The raw GPU Ark CSV contains literal sentinel strings for unknown specs.
    These MUST NOT be written to the database as fabricated values.
    """

    @pytest.mark.parametrize("sentinel", [
        # Case-sensitive strings found in the CSV
        "unknown",
        "Unknown",
        "UNKNOWN",
        # Case-variations and near-miss strings
        "n/a",
        "N/A",
        "NA",
        "na",
        "none",
        "None",
        "NONE",
        # Numeric-placeholder / dash variants
        "-",
        "—",       # em-dash
        "–",       # en-dash
        # Explicit null label
        "null",
        "Null",
        "NULL",
    ], ids=lambda s: repr(s))
    def test_sentinel_tdp_returns_none(self, sentinel):
        """Every sentinel string for tdp_w must normalize to None, not persist."""
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "tdp": sentinel}]
        )
        acquired = sa.acquire(adapter, field="tdp_w")
        assert acquired[0].normalized_value is None, (
            f"normalize_field_value returned {acquired[0].normalized_value!r} "
            f"for sentinel {sentinel!r}; expected None — this value must not "
            "be written to the database as a fabricated specification"
        )

    @pytest.mark.parametrize("sentinel", [
        "unknown", "n/a", "-", "none", "null", ""
    ])
    def test_sentinel_base_clock_returns_none(self, sentinel):
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "base_clock": sentinel}]
        )
        acquired = sa.acquire(adapter, field="base_clock_mhz")
        assert acquired[0].normalized_value is None, (
            f"base_clock sentinel {sentinel!r} returned "
            f"{acquired[0].normalized_value!r}; expected None"
        )

    @pytest.mark.parametrize("sentinel", [
        "unknown", "n/a", "-", "none", "null", ""
    ])
    def test_sentinel_boost_clock_returns_none(self, sentinel):
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "boost_clock": sentinel}]
        )
        acquired = sa.acquire(adapter, field="boost_clock_mhz")
        assert acquired[0].normalized_value is None, (
            f"boost_clock sentinel {sentinel!r} returned "
            f"{acquired[0].normalized_value!r}; expected None"
        )

    @pytest.mark.parametrize("sentinel", [
        "unknown", "n/a", "-", "none", "null", ""
    ])
    def test_sentinel_memory_size_returns_none(self, sentinel):
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "ram": sentinel}]
        )
        acquired = sa.acquire(adapter, field="memory_size_gb")
        assert acquired[0].normalized_value is None, (
            f"memory_size sentinel {sentinel!r} returned "
            f"{acquired[0].normalized_value!r}; expected None"
        )

    @pytest.mark.parametrize("sentinel", [
        "unknown", "n/a", "-", "none", "null", ""
    ])
    def test_sentinel_tdp_unit_preserved(self, sentinel):
        """Unit (W) must be returned even when value is None."""
        adapter = _GpuArkAdapterForTest([{**_SENTINEL_ROW, "tdp": sentinel}])
        acquired = sa.acquire(adapter, field="tdp_w")
        assert acquired[0].unit == "W", (
            f"unit must be 'W' regardless of sentinel value, got {acquired[0].unit!r}"
        )

    def test_known_valid_value_survives_normalization(self):
        """Valid numeric values must NOT be rejected by the sentinel filter."""
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "tdp": "450 W", "base_clock": "2235 MHz"}]
        )
        tdp_vals = sa.acquire(adapter, field="tdp_w")
        assert tdp_vals[0].normalized_value == "450 W"
        bc_vals = sa.acquire(adapter, field="base_clock_mhz")
        assert bc_vals[0].normalized_value == "2235 MHz"

    def test_whitespace_only_value_is_none(self):
        """Strings that are only whitespace must be treated as empty → None."""
        adapter = _GpuArkAdapterForTest(
            [{**_SENTINEL_ROW, "tdp": "   ", "base_clock": "\t"}]
        )
        tdp = sa.acquire(adapter, field="tdp_w")
        assert tdp[0].normalized_value is None
        bc = sa.acquire(adapter, field="base_clock_mhz")
        assert bc[0].normalized_value is None
