"""M3 Phase 5 — pilot catalog seed generator (RED-first contract tests).

Builds the verified pilot dataset for the isolated dev DB:
- 100 RAM + 100 Storage + 100 Motherboard + 100 PSU curated records,
  every value citing a real, human-checkable source (Wikipedia CC BY-SA 4.0
  article revisions or official product pages),
- every record passes validate_record (fail-closed) and carries per-field
  provenance before publication,
- batches 10 → 25 → 50 → 100 per category via publish_batch.

The generator produces records ONLY from the curated seed table below
(family/model names + the specification values a curator verified against
the cited articles). It never invents values: every spec value in the seed
table is either (a) a JEDEC/documentary fact stated on the cited Wikipedia
page (generation vocabularies, voltage classes, interface vocabularies,
form factors, 80 Plus tiers) or (b) an official-product-page value.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.pilot_seed import (  # noqa: E402
    PILOT_TARGETS,
    build_pilot_records,
    iter_batches,
)


class TestPilotTargets:
    def test_targets(self):
        assert PILOT_TARGETS == {"RAM": 100, "STORAGE": 100,
                                 "MOTHERBOARD": 100, "PSU": 100}


class TestGeneratedRecords:
    @pytest.fixture(scope="class")
    def records(self):
        return build_pilot_records()

    def test_100_per_category(self, records):
        for category in ("RAM", "STORAGE", "MOTHERBOARD", "PSU"):
            assert len(records[category]) == 100, category

    def test_every_record_has_identity_and_approval(self, records):
        for category, batch in records.items():
            for record in batch:
                assert record["category"] == category
                assert record["record_status"] == "APPROVED"
                assert record["approved_by"] == "m3-curator"
                assert record["canonical_key"]
                assert record["product_family"]
                assert record["identity_status"] == "confirmed"

    def test_every_populated_field_has_provenance(self, records):
        for category, batch in records.items():
            for record in batch:
                for field_name in record["spec"]:
                    assert field_name in record["provenance"], (
                        category, record["name"], field_name)

    def test_citations_are_real_documents(self, records):
        """Every citation URL points at the cited corpus (wikipedia.org or a
        known manufacturer domain). No fabricated TLDs."""
        for batch in records.values():
            for record in batch:
                for prov in record["provenance"].values():
                    url = prov["source_url"]
                    assert url.startswith("https://"), url
                    assert ("wikipedia.org" in url
                            or "corsair.com" in url
                            or "gskill.com" in url
                            or "samsung.com" in url
                            or "asus.com" in url
                            or "msi.com" in url
                            or "gigabyte.com" in url
                            or "asrock.com" in url
                            or "seasonic.com" in url
                            or "kingston.com" in url
                            or "crucial.com" in url
                            or "westerndigital.com" in url
                            or "seagate.com" in url
                            or "bequiet.com" in url
                            or "evga.com" in url
                            or "teamgroupinc.com" in url
                            or "adata.com" in url
                            or "thermaltake.com" in url
                            or "coolermaster.com" in url), url

    def test_ram_kit_vs_module_distinct(self, records):
        keys = {r["canonical_key"] for r in records["RAM"]}
        # Both a 2x16 kit and a 1x32 module of the same family line exist.
        assert any("kit-2x16" in k for k in keys)
        assert any("module-1x32" in k for k in keys)

    def test_all_keys_unique_globally(self, records):
        keys = [r["canonical_key"] for batch in records.values() for r in batch]
        assert len(keys) == len(set(keys))

    def test_records_pass_fail_closed_validation(self, records):
        from backend.app.importers.m3_validation import validate_record

        for category, batch in records.items():
            for record in batch:
                outcome = validate_record(
                    category, {**record["spec"], "name": record["name"],
                               "manufacturer": record["manufacturer"]})
                assert outcome.passed, (category, record["name"],
                                        outcome.blockers)


class TestBatchProgression:
    def test_iter_batches_progression(self):
        records = build_pilot_records()
        sizes = [10, 25, 50, 100]
        batches = list(iter_batches(records, sizes))
        # 4 categories × 4 sizes = 16 batches; cumulative coverage per
        # category: 10, 25, 50, 100 (cumulative, not overlapping).
        assert len(batches) == 16
        ram_sizes = [len(b) for b in batches if b[0]["category"] == "RAM"]
        assert ram_sizes == [10, 15, 25, 50]  # deltas: 10, 25-10, 50-25, 100-50
        # Cumulative == target
        total = 0
        for batch in batches:
            total += len([r for r in batch if r["category"] == "RAM"])
        assert total == 100
