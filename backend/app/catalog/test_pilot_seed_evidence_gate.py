"""M3 remediation — RED regression tests: SKU-level evidence gate.

These tests define the evidence contract that pilot_seed.py and
m3_validation.py must satisfy. A family-level citation (vendor family page
or Wikipedia technology article) CANNOT establish SKU-level verification.
Only a per-SKU URL (product-specific page, product.aspx?pn=..., model page)
or a present MPN field backs a 'verified' evidence_status.

The pilot generator must not stamp 'verified' on generated family×tier
combinations without SKU-level evidence.
"""
from __future__ import annotations

import pytest

from backend.app.catalog.pilot_seed import build_pilot_records
from backend.app.importers.m3_validation import (
    _FAMILY_LEVEL_ROOTS,
    _SKU_URL_SIGNATURES,
)

_MPN_FIELDS = ("mpn", "part_number")


def _has_sku_reference(record: dict, prov: dict) -> bool:
    """Mirror the evidence-gate Layer 2 rule (MPN or per-SKU URL)."""
    if any(str(record.get(f) or "").strip() for f in _MPN_FIELDS):
        return True
    url = prov.get("source_url", "")
    return any(sig in url.lower() for sig in _SKU_URL_SIGNATURES)


def _verified_prov_complete(prov: dict) -> bool:
    """Mirror Layer 3 of the evidence gate: source_reference + allowed match_method."""
    ref = str(prov.get("source_reference") or "").strip()
    method = str(prov.get("match_method") or "").strip()
    return bool(ref) and method in ("manual-curation", "spec-table-row",
                                    "manufacturer-declaration")


class TestEvidenceGatePilotSeed:
    """Regression: pilot_seed must not claim 'verified' without SKU-level
    citation (MPN field or per-SKU URL)."""

    @pytest.fixture(scope="class")
    def records(self):
        return build_pilot_records()

    def test_no_generated_record_claims_verified_without_sku_reference(
        self, records
    ):
        """Every record claiming evidence_status='verified' on any field must
        have that field's provenance cite a per-SKU URL (not a family page)
        OR the record must carry an MPN field."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if prov.get("evidence_status") == "verified":
                        assert _has_sku_reference(record, prov), (
                            f"{category}/{record['name']}: field {field_name!r} "
                            f"claims evidence_status='verified' but source_url "
                            f"{prov.get('source_url', '')!r} is family-level "
                            "(no MPN or per-SKU path); evidence_status must be "
                            "'unverified' or lower"
                        )

    def test_family_level_citations_use_unverified_not_verified(self, records):
        """Provenance cited from a vendor family page root must NOT have
        evidence_status='verified' unless the record carries a SKU anchor
        (MPN field) — family pages alone cannot verify SKU specs."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    url = prov.get("source_url", "")
                    if any(root in url for root in _FAMILY_LEVEL_ROOTS):
                        if prov.get("evidence_status") == "verified":
                            assert any(
                                str(record.get(f) or "").strip()
                                for f in _MPN_FIELDS), (
                                f"{category}/{record['name']}: field "
                                f"{field_name!r} cites family-level URL "
                                f"{url!r} with evidence_status='verified' "
                                "but the record has no MPN; family pages "
                                "cannot verify SKU specs without a "
                                "manufacturer MPN"
                            )

    def test_wikipedia_citations_never_verified_for_sku_fields(self, records):
        """Wikipedia technology articles (DDR4/DDR5/NVMe/ATX/80Plus/etc.)
        may support technology-level facts only. They are NEVER a
        per-SKU source and must not yield evidence_status='verified'
        for capacity, speed, wattage, etc."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if "wikipedia.org" in prov.get("source_url", ""):
                        assert prov.get("evidence_status") != "verified", (
                            f"{category}/{record['name']}: field {field_name!r} "
                            f"cited Wikipedia ({prov['source_url']!r}) but claims "
                            "evidence_status='verified'; Wikipedia can only support "
                            "technology vocabulary (DDR5, NVMe, ATX, etc.), not SKU specs"
                        )

    def test_identity_status_confirmed_requires_verified_evidence(self, records):
        """A record with identity_status='confirmed' must have at least one
        field with evidence_status='verified' AND that field's citation must
        be per-SKU (not family-level) or the record carries an MPN."""
        for category, batch in records.items():
            for record in batch:
                if record.get("identity_status") == "confirmed":
                    has_verified_sku = any(
                        prov.get("evidence_status") == "verified"
                        and _has_sku_reference(record, prov)
                        for prov in record["provenance"].values()
                    )
                    assert has_verified_sku, (
                        f"{category}/{record['name']}: identity_status='confirmed' "
                        "but no provenance field cites a per-SKU URL with "
                        "evidence_status='verified'; confirming a product's "
                        "identity requires SKU-level evidence (MPN or per-SKU page)"
                    )

    def test_generated_combinations_not_auto_verified(self, records):
        """The generator enumerates family × tier combinations. These
        generated combinations must NOT all have evidence_status='verified'.
        At minimum, the generated ones without per-SKU citations must carry
        evidence_status='unverified' (or 'uncertain'), not 'verified'."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if prov.get("evidence_status") == "verified":
                        assert _has_sku_reference(record, prov), (
                            f"{category}/{record['name']}: field {field_name!r} "
                            "is marked verified but cites a generated-family "
                            "URL without SKU-specific path; "
                            "family enumeration cannot verify SKU existence"
                        )

    def test_verified_provance_has_source_reference(self, records):
        """Every provenance entry with evidence_status='verified' must carry
        a non-empty source_reference (the table/heading/row/field where the
        curator read the value from the cited document). Layer 3 of the
        evidence gate contract; fail-closed when missing."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if prov.get("evidence_status") == "verified":
                        assert _verified_prov_complete(prov), (
                            f"{category}/{record['name']}: field {field_name!r} "
                            "has evidence_status='verified' but lacks a "
                            f"source_reference or has an invalid match_method; "
                            f"source_reference={prov.get('source_reference')!r}, "
                            f"match_method={prov.get('match_method')!r}; "
                            "Layer 3 of the evidence gate requires both"
                        )

    def test_uncertain_provenance_has_no_verified_marker(self, records):
        """Technology-level provenance (Wikipedia, family pages) must not
        claim evidence_status='verified'; 'uncertain' is the correct label
        for family/technology-tier evidence."""
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if prov.get("evidence_status") == "verified":
                        assert _has_sku_reference(record, prov), (
                            f"{category}/{record['name']}: field {field_name!r} "
                            "has evidence_status='verified' from a "
                            f"non-SKU source {prov.get('source_url')!r} "
                            "(missing MPN + no per-SKU path)"
                        )


class TestEvidenceGateAdversarial:
    """Fail-closed adversarial cases for the evidence gate contract.

    These tests directly exercise validate_record() with the strengthened
    Layer 3 requirements (source_reference + allowed match_method)."""

    def test_missing_source_reference_blocks_verified(self):
        """A 'verified' provenance entry without source_reference is rejected
        by the evidence gate — no self-declared verification without a
        traceable locator."""
        from backend.app.importers.m3_validation import validate_record
        record = {
            "name": "Test RAM SKU",
            "manufacturer": "TestCorp",
            "mpn": "TC-3200C16-16G",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 3200,
            "modules": 2,
            "provenance": {
                "capacity_gb": {
                    "source_name": "TestCorp official",
                    "source_url": "https://testcorp.com/products/tc-3200c16-16g",
                    "evidence_status": "verified",
                    "access_date": "2026-11-18",
                    # source_reference MISSING
                    "match_method": "spec-table-row",
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        blockers = [b for b in outcome.blockers if "source_reference" in b]
        assert blockers, f"expected source_reference blocker; got {outcome.blockers}"
        assert not outcome.passed

    def test_missing_match_method_blocks_verified(self):
        """A 'verified' provenance entry without match_method is rejected."""
        from backend.app.importers.m3_validation import validate_record
        record = {
            "name": "Test PSU SKU",
            "manufacturer": "TestPSU",
            "mpn": "TP-750G",
            "wattage": 750,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
            "provenance": {
                "wattage": {
                    "source_name": "TestPSU official",
                    "source_url": "https://testpsu.com/products/tp-750g",
                    "evidence_status": "verified",
                    "access_date": "2026-11-18",
                    "source_reference": "Specifications > Wattage",
                    # match_method MISSING
                },
            },
        }
        outcome = validate_record("PSU", record, conflict_free=True,
                                  identity_confirmed=True)
        blockers = [b for b in outcome.blockers if "match_method" in b]
        assert blockers, f"expected match_method blocker; got {outcome.blockers}"
        assert not outcome.passed

    def test_invalid_match_method_blocks_verified(self):
        """A 'verified' provenance entry with a match_method outside the
        allowed curation vocabulary is rejected (no automatic approval
        from self-declared status)."""
        from backend.app.importers.m3_validation import validate_record
        record = {
            "name": "Test PSU SKU",
            "manufacturer": "TestPSU",
            "mpn": "TP-750G",
            "wattage": 750,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
            "provenance": {
                "wattage": {
                    "source_name": "TestPSU official",
                    "source_url": "https://testpsu.com/products/tp-750g",
                    "evidence_status": "verified",
                    "access_date": "2026-11-18",
                    "source_reference": "Specifications > Wattage",
                    "match_method": "auto-scraped",  # ← invalid
                },
            },
        }
        outcome = validate_record("PSU", record, conflict_free=True,
                                  identity_confirmed=True)
        blockers = [b for b in outcome.blockers if "match_method" in b]
        assert blockers, f"expected match_method blocker; got {outcome.blockers}"
        assert not outcome.passed

    def test_valid_verified_provenance_passes(self):
        """A 'verified' provenance entry with source_reference + allowed
        match_method + MPN + per-SKU URL passes the evidence gate."""
        from backend.app.importers.m3_validation import validate_record
        record = {
            "name": "Test RAM SKU",
            "manufacturer": "TestCorp",
            "mpn": "TC-3200C16-16G",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 3200,
            "modules": 2,
            "provenance": {
                "capacity_gb": {
                    "source_name": "TestCorp official",
                    "source_url": "https://testcorp.com/products/tc-3200c16-16g",
                    "evidence_status": "verified",
                    "access_date": "2026-11-18",
                    "source_reference": "Tech Specs > Capacity",
                    "match_method": "spec-table-row",
                },
                "speed_mhz": {
                    "source_name": "TestCorp official",
                    "source_url": "https://testcorp.com/products/tc-3200c16-16g",
                    "evidence_status": "verified",
                    "access_date": "2026-11-18",
                    "source_reference": "Tech Specs > Speed",
                    "match_method": "spec-table-row",
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        evidence_blockers = [
            b for b in outcome.blockers
            if any(k in b for k in ("source_reference", "match_method",
                                    "evidence", "verified"))
        ]
        assert not evidence_blockers, (
            f"record with complete verified provenance should not be "
            f"blocked by evidence gate; blockers: {outcome.blockers}"
        )
        assert outcome.passed
