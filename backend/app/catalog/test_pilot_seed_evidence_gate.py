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
        FLEET_MPN_KEYWORDS = ("pn=", "product.aspx", "/product/", "-mpn",
                              "sku=", "part-number")
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    if prov.get("evidence_status") == "verified":
                        url = prov.get("source_url", "")
                        has_mpn = "mpn" in record or "part_number" in record
                        is_sku_url = any(kw in url.lower() for kw in FLEET_MPN_KEYWORDS)
                        assert is_sku_url or has_mpn, (
                            f"{category}/{record['name']}: field {field_name!r} "
                            f"claims evidence_status='verified' but source_url "
                            f"{url!r} is family-level (no MPN or per-SKU path); "
                            "evidence_status must be 'unverified' or lower"
                        )

    def test_family_level_citations_use_unverified_not_verified(self, records):
        """Provenance cited from a vendor family page (gskill.com Trident-Z5
        family listing, seasonic.com Focus GX series page) must NOT have
        evidence_status='verified' for SKU-specific fields (speed_mhz,
        capacity_gb, wattage, etc.)."""
        FAMILY_LEVEL_ROOTS = (
            "gskill.com/products/165",   # Trident-Z5 family listing
            "corsair.com/us/en/c/memory", # Corsair RAM family pages
            "seasonic.com/focus",         # Focus GX series page
            "samsung.com/consumer-storage/support/990-pro",  # family support page
            "westerndigital.com/products/internal-drives/wd-black-sn850x",  # family
            "asus.com/us/motherboards/prime-b650",   # ASUS PRIME B650 family
            "msi.com/Motherboard/MAG-B650",          # MSI MAG B650 family
            "gigabyte.com/Motherboard/B650",         # Gigabyte B650 family
            "asrock.com/MB/AMD/B650",                # ASRock B650 family
            "bequiet.com/en/power-supply",           # be quiet! PSU family pages
            "thermaltake.com/power-supply",          # Thermaltake PSU family
            "coolermaster.com/catalog/power-supplies",  # CoolerMaster family
        )
        for category, batch in records.items():
            for record in batch:
                for field_name, prov in record["provenance"].items():
                    url = prov.get("source_url", "")
                    if any(root in url for root in FAMILY_LEVEL_ROOTS):
                        assert prov.get("evidence_status") != "verified", (
                            f"{category}/{record['name']}: field {field_name!r} "
                            f"cites family-level URL {url!r} but claims "
                            "evidence_status='verified'; must be "
                            "'unverified' or 'uncertain'"
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
        be per-SKU (not family-level). A record with no SKU-level verified
        field must have identity_status='unconfirmed' or 'unverified'."""
        for category, batch in records.items():
            for record in batch:
                if record.get("identity_status") == "confirmed":
                    has_verified_sku = False
                    for prov in record["provenance"].values():
                        if prov.get("evidence_status") == "verified":
                            url = prov.get("source_url", "")
                            FLEET_MPN = ("pn=", "product.aspx", "/product/",
                                         "-mpn", "sku=", "part-number")
                            if any(kw in url.lower() for kw in FLEET_MPN):
                                has_verified_sku = True
                                break
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
                        url = prov.get("source_url", "")
                        FLEET = ("pn=", "product.aspx", "/product/", "-mpn",
                                 "sku=", "part-number")
                        if not any(kw in url.lower() for kw in FLEET):
                            pytest.fail(
                                f"{category}/{record['name']}: field {field_name!r} "
                                "is marked verified but cites a generated-family "
                                "URL without SKU-specific path; "
                                "family enumeration cannot verify SKU existence"
                            )
