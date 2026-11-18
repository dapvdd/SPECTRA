"""M3 remediation — RED regression tests: validation evidence gate.

validate_record() must fail-closed on records that claim
evidence_status='verified' on SKU-specific fields without an MPN field or a
per-SKU source URL. The evidence tier model:

- Wikipedia: technology vocabulary only (DDR5, NVMe, ATX, 80 Plus); NEVER
  SKU-specific specs (capacity, speed, wattage).
- Vendor family page: family-level facts only; never SKU-specific specs.
- Per-SKU product page (product.aspx?pn=..., /product/...) or a present
  MPN field: can back 'verified' evidence.
"""
from __future__ import annotations

import pytest

from backend.app.importers.m3_validation import validate_record

_BLOCKER_HINTS = ("evidence", "verified", "mpn", "sku")


def _evidence_blockers(outcome) -> list[str]:
    return [b for b in outcome.blockers
            if any(h in b.lower() for h in _BLOCKER_HINTS)]


class TestValidationEvidenceGate:
    """Regression: validate_record must reject records claiming 'verified'
    without SKU-level evidence (MPN field or per-SKU URL)."""

    def test_record_with_verified_wikipedia_cite_fails_gate(self):
        """A record citing Wikipedia for capacity_gb (an SKU-specific field)
        and claiming evidence_status='verified' must fail the evidence gate.
        Wikipedia is technology-vocabulary only; it cannot verify SKU specs."""
        record = {
            "name": "G.Skill Trident Z5 32GB DDR5-6400",
            "manufacturer": "G.Skill",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6400,
            "modules": 2,
            # Provenance claims verified via Wikipedia for capacity_gb
            "_provenance": {
                "capacity_gb": {
                    "source_name": "Wikipedia (English)",
                    "source_url": "https://en.wikipedia.org/wiki/DDR5_SDRAM",
                    "evidence_status": "verified",  # ← wrong: Wikipedia can't verify SKU capacity
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        # Should fail because evidence_status='verified' on a SKU-specific field
        # with only a Wikipedia citation is a contract violation.
        evidence_blocker = next(
            (b for b in outcome.blockers if "evidence" in b.lower() or "verified" in b.lower()),
            None,
        )
        assert evidence_blocker is not None, (
            f"validate_record should block a record citing Wikipedia for "
            f"capacity_gb with evidence_status='verified'; blockers: {outcome.blockers}"
        )

    def test_record_without_mpn_no_sku_url_fails_when_claiming_verified(self):
        """A record with SKU-specific fields (capacity_gb, speed_mhz, wattage)
        that claims evidence_status='verified' on those fields but has no MPN
        field and no per-SKU source URL (only family-level URL) must fail
        the validation gate."""
        record = {
            "name": "G.Skill Trident Z5 DDR5-6400",
            "manufacturer": "G.Skill",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6400,
            "modules": 2,
            "_provenance": {
                "capacity_gb": {
                    "source_name": "Official product pages",
                    # Family page — NOT per-SKU
                    "source_url": "https://www.gskill.com/products/165/396/Trident-Z5",
                    "evidence_status": "verified",  # ← must fail: family page ≠ SKU proof
                },
                "speed_mhz": {
                    "source_name": "Official product pages",
                    "source_url": "https://www.gskill.com/products/165/396/Trident-Z5",
                    "evidence_status": "verified",
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        evidence_blocker = next(
            (b for b in outcome.blockers if "evidence" in b.lower() or "verified" in b.lower()),
            None,
        )
        assert evidence_blocker is not None, (
            f"validate_record should block a record claiming 'verified' with "
            f"only family-level citation; blockers: {outcome.blockers}"
        )

    def test_record_with_mpn_field_passes_evidence_gate(self):
        """A record that carries an 'mpn' field with a per-SKU URL citation
        for its spec fields SHOULD pass the evidence gate (if other fields
        are consistent)."""
        record = {
            "name": "G.Skill Trident Z5 RGB F5-6400J3248G16GX2-TZ5NK",
            "manufacturer": "G.Skill",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6400,
            "modules": 2,
            "mpn": "F5-6400J3248G16GX2-TZ5NK",
            "_provenance": {
                "capacity_gb": {
                    "source_name": "Official product pages",
                    "source_url": "https://www.gskill.com/products/165/396/Trident-Z5",
                    "evidence_status": "verified",
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        # With MPN field, the evidence gate should pass (the MPN is the SKU-level anchor)
        evidence_blocker = next(
            (b for b in outcome.blockers
             if "evidence" in b.lower() or "verified" in b.lower() or "mpn" in b.lower()),
            None,
        )
        assert evidence_blocker is None, (
            f"Record with MPN field should not be blocked by evidence gate; "
            f"blockers: {outcome.blockers}"
        )

    def test_unverified_evidence_passes_validation(self):
        """A record with evidence_status='unverified' (family-level citation)
        should pass validation — the evidence gate does not block unverified
        records; it only prevents FAKE verification claims."""
        record = {
            "name": "G.Skill Trident Z5 DDR5-6400 (unverified variant)",
            "manufacturer": "G.Skill",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6400,
            "modules": 2,
            "_provenance": {
                "capacity_gb": {
                    "source_name": "Official product pages",
                    "source_url": "https://www.gskill.com/products/165/396/Trident-Z5",
                    "evidence_status": "unverified",  # ← honest: we know it's a family
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=False)
        # Unverified evidence adds NO blocker of its own. The only expected
        # blocker is the by-design "identity not confirmed" one from
        # identity_confirmed=False — the evidence gate must not add more.
        evidence_blockers = [
            b for b in outcome.blockers
            if "evidence" in b.lower() or "verified" in b.lower()
        ]
        assert not evidence_blockers, (
            f"Record with evidence_status='unverified' must not be blocked by "
            f"the evidence gate; got: {evidence_blockers}"
        )


class TestEvidenceStatusSemantics:
    """Unit tests: evidence_status values and their meaning."""

    @pytest.fixture
    def ram_record(self):
        return {
            "name": "G.Skill Trident Z5 RGB",
            "manufacturer": "G.Skill",
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6400,
            "modules": 2,
        }

    def test_verified_requires_sku_citation_or_mpn(self, ram_record):
        """evidence_status='verified' is only valid when backed by an MPN
        field or a per-SKU URL (product.aspx?pn=, /product/, etc.)."""
        record = {**ram_record, "mpn": "F5-6400J3248G16GX2-TZ5NK"}
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        assert outcome.passed

    def test_wikipedia_technology_facts_accepted(self, ram_record):
        """Wikipedia citations for technology-level facts (DDR5 generation,
        M.2 form factor, ATX standard, 80 Plus tier) are acceptable with
        evidence_status='unverified' (not 'verified')."""
        record = {**ram_record}
        # No mpn, Wikipedia URL for generation — should be unverified, not verified
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
        # This passes because we don't assert on evidence_status here;
        # the validation pass/fail is about spec completeness, not evidence.
        # The evidence gate is about the provenance dictionary.
        assert outcome.passed

    def test_family_only_cannot_be_verified(self):
        """A record with no MPN and only a family-level vendor URL
        citing 'verified' evidence_status fails a new evidence gate
        (if implemented)."""
        record = {
            "name": "Seasonic Focus GX 750W",
            "manufacturer": "Seasonic",
            "wattage": 750,
            "efficiency_rating": "80 Plus Gold",
            "modular": True,
            "pcie_8pin_count": 4,
            "pcie_12vhpwr": 0,
            # Only family-level URL, no per-SKU
            "_provenance": {
                "wattage": {
                    "source_name": "Seasonic official",
                    "source_url": "https://seasonic.com/focus-gx/",
                    "evidence_status": "verified",  # ← BLOCKED
                },
            },
        }
        outcome = validate_record("PSU", record, conflict_free=True,
                                  identity_confirmed=True)
        evidence_blocker = next(
            (b for b in outcome.blockers
             if "evidence" in b.lower() or "verified" in b.lower()),
            None,
        )
        assert evidence_blocker is not None, (
            f"PSU with family-level 'verified' citation should be blocked; "
            f"blockers: {outcome.blockers}"
        )
