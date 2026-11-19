"""M3 Phase 2 — curated source adapters (RED-first contract tests).

Pins the two M3 adapters from docs/m3/M3_SOURCE_FEASIBILITY.md §4:
1. WikipediaCuratedAdapter  — curated rows citing Wikipedia article revisions
   (license clear: CC BY-SA 4.0; attribution recorded per value).
2. ManualOfficialCitationAdapter — curated rows citing official product pages
   (source license status stays 'unknown'; the *provenance row* is
   evidence_status='verified' because a human verified the value at access
   time; no network I/O happens at import time).

Contract: both are SourceAdapter subclasses (existing Stage 2 framework),
declare source identity + license metadata, perform ZERO network fetches,
and produce AcquiredValue records carrying full provenance.
"""
from __future__ import annotations

import pytest

from backend.app.scripts.m3_adapters import (
    MANUAL_OFFICIAL_CITATION,
    WIKIPEDIA_CURATED,
    ManualOfficialCitationAdapter,
    WikipediaCuratedAdapter,
)
from backend.app.scripts.source_acquisition import (
    AcquiredValue,
    SourceAdapter,
)


class TestAdapterDeclarations:
    def test_wikipedia_adapter_metadata(self):
        adapter = WikipediaCuratedAdapter()
        assert isinstance(adapter, SourceAdapter)
        assert adapter.source_name == "Wikipedia (English) — curated"
        assert "wikipedia.org" in adapter.source_url
        assert adapter.license_status == "clear"
        assert "CC BY-SA" in adapter.license_name

    def test_manual_adapter_metadata(self):
        adapter = ManualOfficialCitationAdapter()
        assert isinstance(adapter, SourceAdapter)
        assert adapter.license_status == "unknown"
        # Honest naming: the citation target, not a license claim.
        assert adapter.license_name == "site terms (no redistribution license published)"

    def test_source_id_constants(self):
        assert WIKIPEDIA_CURATED == "wikipedia-curated"
        assert MANUAL_OFFICIAL_CITATION == "manual-official-citation"


class TestZeroNetwork:
    def test_adapters_never_fetch(self):
        """The adapters are human-in-the-loop: map_record must work without
        any network access (it transforms prepared rows, never fetches)."""
        adapter = WikipediaCuratedAdapter()
        row = {
            "hardware_name": "G.Skill Trident Z5 RGB 32GB (2x16GB) DDR5-6000 CL30",
            "manufacturer": "G.Skill",
            "category": "RAM",
            "fields_json": '{"ddr_generation": "DDR5", "capacity_gb": 32, "speed_mhz": 6000, "modules": 2}',
            "citation_url": "https://en.wikipedia.org/wiki/DDR5_SDRAM",
            "citation_revision": "1378669134",
            "access_date": "2026-11-16",
        }
        # No fetch occurs; parse failures raise ValueError, nothing else.
        record = adapter.map_record(row)
        assert record["hardware_name"] == row["hardware_name"]
        assert record["citation_url"] == row["citation_url"]


class TestAcquiredValues:
    def test_wikipedia_values_carry_provenance(self):
        adapter = WikipediaCuratedAdapter()
        record = {
            "hardware_name": "Corsair Vengeance 32GB (1x32GB) DDR5-5600",
            "manufacturer": "Corsair",
            "category": "RAM",
            "fields": {"ddr_generation": "DDR5", "capacity_gb": 32},
            "citation_url": "https://en.wikipedia.org/wiki/DDR5_SDRAM",
            "citation_revision": "1378669134",
            "access_date": "2026-11-16",
        }
        values = adapter.acquire_values(record)
        assert len(values) == 2
        for value in values:
            assert isinstance(value, AcquiredValue)
            assert value.license_status == "clear"
            assert "CC BY-SA" in value.license_name
            assert value.source_url == record["citation_url"]
            assert value.source_reference.endswith("1378669134")
            # The human verification date is carried in source_publication_date
            # (AcquiredValue has no dedicated access_date; the enrichment
            # pipeline maps it into field_provenance.access_date).
            assert value.source_publication_date == "2026-11-16"
            assert value.retrieved_at  # fetch timestamp present

    def test_manual_values_keep_unknown_license(self):
        adapter = ManualOfficialCitationAdapter()
        record = {
            "hardware_name": "Corsair RM850x",
            "manufacturer": "Corsair",
            "category": "PSU",
            "fields": {"wattage": 850, "efficiency_rating": "80 Plus Gold"},
            "citation_url": "https://www.corsair.com/us/en/p/CP-9020200-NA",
            "access_date": "2026-11-16",
        }
        values = adapter.acquire_values(record)
        assert len(values) == 2
        for value in values:
            assert value.license_status == "unknown"
            assert value.source_url == record["citation_url"]


class TestFieldMapExtension:
    def test_field_map_covers_four_categories(self):
        from backend.app.scripts.enrichment_pipeline import (
            field_for_acquisition,
        )
        cases = [
            ("RAM", "ddr_generation", "ram_specifications", "ddr_generation"),
            ("RAM", "capacity_gb", "ram_specifications", "capacity_gb"),
            ("STORAGE", "interface", "storage_specifications", "interface"),
            ("MOTHERBOARD", "socket", "motherboard_specifications", "socket"),
            ("PSU", "wattage", "psu_specifications", "wattage"),
            ("PSU", "efficiency_rating", "psu_specifications", "efficiency_rating"),
        ]
        for hw_type, field, expected_table, expected_column in cases:
            result = field_for_acquisition(field, hw_type)
            assert result == (expected_table, expected_column), (hw_type, field)

    def test_unknown_field_still_rejected(self):
        from backend.app.scripts.enrichment_pipeline import (
            field_for_acquisition,
        )
        assert field_for_acquisition("not_a_field", "RAM") is None
        assert field_for_acquisition("wattage", "RAM") is None
