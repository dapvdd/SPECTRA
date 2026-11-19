"""M3 Phase 5 — pilot catalog seed generator (contract tests).

The honest pilot model (M3 remediation):
- Vendor family pages and Wikipedia support family/technology facts only.
  evidence_status='verified' requires an MPN field or per-SKU URL.
- Records without SKU-level evidence are identity_status='unconfirmed',
  record_status='QUARANTINED' — they are included in the pilot for audit
  purposes but cannot enter the PUBLISHED set without re-review.
- The total pilot set may be fewer than 400 (honest count); no fabrications
  are created to preserve the 400 target.
- Every record (quarantined or approved) passes validate_record (fail-closed
  on spec integrity), carries per-field provenance, and has a canonical_key.
- Batches 10 → 25 → 50 → 100 per category via publish_batch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.pilot_seed import (  # noqa: E402
    build_pilot_records,
    iter_batches,
)
from backend.app.identity.lifecycle import APPROVED, QUARANTINED


class TestPilotTargets:
    def test_targets(self):
        assert PILOT_TARGETS == {"RAM": 100, "STORAGE": 100,
                                 "MOTHERBOARD": 100, "PSU": 100}


class TestPilotTargets:
    def test_targets_defined(self):
        # PILOT_TARGETS may now reflect honest count, not necessarily 400 total.
        # The key contract is that build_pilot_records respects these caps.
        from backend.app.catalog.pilot_seed import PILOT_TARGETS
        assert set(PILOT_TARGETS.keys()) == {"RAM", "STORAGE", "MOTHERBOARD", "PSU"}


class TestGeneratedRecords:
    @pytest.fixture(scope="class")
    def records(self):
        return build_pilot_records()

    def test_every_record_has_canonical_key(self, records):
        for category, batch in records.items():
            for record in batch:
                assert record["category"] == category
                assert record["canonical_key"]

    def test_every_record_has_provenance_for_spec_fields(self, records):
        for category, batch in records.items():
            for record in batch:
                for field_name in record["spec"]:
                    assert field_name in record["provenance"], (
                        f"{category}/{record['name']}: spec field {field_name!r} "
                        "has no provenance entry"
                    )

    def test_quarantined_records_are_correctly_stamped(self, records):
        """Any record without SKU-level verified provenance must be QUARANTINED
        with identity_status='unconfirmed'."""
        for category, batch in records.items():
            for record in batch:
                has_verified = any(
                    isinstance(p, dict) and p.get("evidence_status") == "verified"
                    for p in record["provenance"].values()
                )
                if not has_verified:
                    assert record["record_status"] == QUARANTINED, (
                        f"{category}/{record['name']}: no SKU-level verified "
                        f"provenance but record_status={record['record_status']!r}; "
                        "expected QUARANTINED"
                    )
                    assert record["identity_status"] == "unconfirmed"
                    assert record["approved_by"] is None

    def test_approved_records_are_correctly_stamped(self, records):
        """An APPROVED record must have identity_status='confirmed',
        approved_by non-empty, and at least one verified SKU-level provenance."""
        for category, batch in records.items():
            for record in batch:
                if record["record_status"] == APPROVED:
                    assert record["identity_status"] == "confirmed"
                    assert record["approved_by"]
                    has_verified = any(
                        isinstance(p, dict) and p.get("evidence_status") == "verified"
                        for p in record["provenance"].values()
                    )
                    assert has_verified, (
                        f"{category}/{record['name']}: APPROVED but no "
                        "SKU-level verified provenance"
                    )

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
        """Every record (quarantined or approved) passes spec-level
        validate_record — the evidence gate may add blockers only when a
        'verified' claim lacks SKU backing, which cannot happen here
        (pilot_seed no longer claims 'verified' without per-SKU evidence)."""
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
