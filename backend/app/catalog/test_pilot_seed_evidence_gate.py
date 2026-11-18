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
    """Mirror the evidence-gate SKU reference rule (single source of truth
    is m3_validation._evidence_gate; this mirrors it for pilot audit)."""
    if any(str(record.get(f) or "").strip() for f in _MPN_FIELDS):
        return True
    url = prov.get("source_url", "")
    return any(sig in url.lower() for sig in _SKU_URL_SIGNATURES)


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
