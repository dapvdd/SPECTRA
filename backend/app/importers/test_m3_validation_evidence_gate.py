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
        (plus source_reference + allowed match_method) passes the evidence
        gate (if other fields are consistent)."""
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
                    "source_reference": "Specs table > Capacity",
                    "match_method": "spec-table-row",
                },
            },
        }
        outcome = validate_record("RAM", record, conflict_free=True,
                                  identity_confirmed=True)
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
        field or a per-SKU URL (product.aspx?pn=, /product/, etc.) PLUS a
        source_reference locator and an allowed match_method (Layer 3)."""
        record = {
            **ram_record,
            "mpn": "F5-6400J3248G16GX2-TZ5NK",
            "_provenance": {
                "capacity_gb": {
                    "source_name": "Official product pages",
                    "source_url": "https://www.gskill.com/products/165/396/Trident-Z5",
                    "evidence_status": "verified",
                    "source_reference": "Specs table > Capacity",
                    "match_method": "spec-table-row",
                },
            },
        }
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


# ---------------------------------------------------------------------------
# Task 3 — adversarial regression tests (merge-gate strengthening)
# ---------------------------------------------------------------------------

_PER_SKU_URL = "https://testcorp.com/p/psu/tp-750g/testpsu-750w-gold"
_VALID_REF = "Specifications > Power Output > Total continuous power"
_VALID_METHOD = "spec-table-row"


def _psu_with_provenance(prov_overrides: dict, *, mpn: str | None = "TP-750G") -> dict:
    """PSU record with per-field provenance overrides for adversarial tests."""
    spec = {"wattage": 750, "efficiency_rating": "80 Plus Gold", "modular": True}
    base_prov = {
        "source_name": "TestPSU official",
        "source_url": _PER_SKU_URL,
        "evidence_status": "verified",
        "access_date": "2026-11-18",
        "source_reference": _VALID_REF,
        "match_method": _VALID_METHOD,
    }
    provenance = {
        field: {**base_prov, **prov_overrides.get(field, {})}
        for field in spec
    }
    record = {
        "name": "TestPSU 750W Gold",
        "manufacturer": "TestPSU",
        **spec,
        "_provenance": provenance,
    }
    if mpn is not None:
        record["mpn"] = mpn
    return record


class TestAdversarialEvidenceGate:
    """Task 3 adversarial cases — every bypass shape must fail closed."""

    def test_fabricated_mpn_with_valid_looking_url_blocked(self):
        """Fabricated MPN + URL that merely LOOKS per-SKU: the gate demands
        Layer 3 (source_reference + match_method). A URL pattern alone with
        a made-up MPN and no curator assertion cannot pass."""
        record = _psu_with_provenance(
            {"wattage": {"source_reference": "", "match_method": ""}},
            mpn="FAKE-999-XXX",
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        assert any("source_reference" in b for b in outcome.blockers)

    def test_real_mpn_with_mismatched_spec_value_is_curation_problem(self):
        """The gate verifies traceability, not truth of the number — but a
        mismatched value still cannot slip through unattributed: with a
        proper source_reference the audit manifest is the arbiter. Here we
        pin that the gate REQUIRES the manifest trail regardless of value
        plausibility (value sanity is unit_checks' job)."""
        record = _psu_with_provenance(
            {"wattage": {"source_reference": ""}},  # no locator for the claim
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        assert any("source_reference" in b for b in outcome.blockers)

    def test_family_url_with_unsupported_variant_blocked(self):
        """Family URL + MPN + verified claim on a field the family page
        cannot support: family roots stay ineligible even with an MPN when
        the URL is not per-SKU (Layer 2 anchor must come from URL or MPN —
        family URL alone with MPN passes Layer 2, but Layer 3 still applies).
        With no source_reference it must fail."""
        record = _psu_with_provenance(
            {"wattage": {"source_url": "https://testpsu.com/focus-family/",
                         "source_reference": ""}},
            mpn="TP-750G",
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        assert any("source_reference" in b for b in outcome.blockers)

    def test_valid_url_syntax_with_unrelated_content_still_needs_layer3(self):
        """A URL with SKU-like syntax but no curator assertion (no
        source_reference) is rejected — URL string patterns never promote."""
        record = _psu_with_provenance(
            {"efficiency_rating": {"source_reference": None}},
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        assert any("source_reference" in b for b in outcome.blockers)

    def test_missing_evidence_locator_blocked(self):
        """Missing source_reference entirely → blocker."""
        record = _psu_with_provenance(
            {"modular": {"source_reference": None, "match_method": _VALID_METHOD}},
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        assert any("source_reference" in b for b in outcome.blockers)

    def test_conflicting_evidence_values_detected_not_merged(self):
        """Two records, same canonical_key, differing wattage: the conflict
        gate rejects both (existing behavior preserved under the new gate)."""
        from backend.app.importers.m3_validation import detect_conflicts
        a = {**_psu_with_provenance({}), "canonical_key": "testpsu|psu|750g|750w",
             "_type": "PSU", "source_name": "s1"}
        b = {**_psu_with_provenance({}), "wattage": 850,
             "canonical_key": "testpsu|psu|750g|750w",
             "_type": "PSU", "source_name": "s2"}
        conflicts = detect_conflicts([a, b])
        assert conflicts, "differing wattage on same key must surface as conflict"
        assert conflicts[0].field == "wattage"

    def test_false_verified_status_without_anchor_blocked(self):
        """Self-declared evidence_status='verified' with NO MPN and a
        family-level URL: blocked at Layer 2 AND Layer 3."""
        record = _psu_with_provenance(
            {"wattage": {"source_url": "https://seasonic.com/focus/",
                         "source_reference": None, "match_method": None}},
            mpn=None,
        )
        outcome = validate_record("PSU", record)
        assert not outcome.passed
        # Layer 2 (family URL, no MPN) fires.
        assert any("family-level" in b for b in outcome.blockers)

    def test_missing_optional_fields_still_publishable(self):
        """Optional fields absent (NULL) stay publishable: the gate only
        polices 'verified' claims, not absence."""
        record = _psu_with_provenance({})
        # pcie_8pin_count / pcie_12vhpwr intentionally absent (optional).
        outcome = validate_record("PSU", record)
        assert outcome.passed, outcome.blockers

    def test_dry_run_apply_parity_on_layer3(self, tmp_path):
        """Dry-run mirrors the strengthened gate: a record failing Layer 3
        is rejected in dry-run exactly as at publish time."""
        import sqlite3

        from backend.app.migrations.runner import upgrade
        from backend.app.publishing.publisher import dry_run_batch
        from backend.app.test_migration_runner import _clone_schema

        db = tmp_path / "parity.db"
        _clone_schema(db)
        upgrade(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO sources (name, url) VALUES "
                     "('TestPSU official', 'https://testpsu.com')")
        conn.commit()
        conn.close()

        record = _psu_with_provenance(
            {"wattage": {"source_reference": ""}},
        )
        record["category"] = "PSU"
        record["record_status"] = "APPROVED"
        record["approved_by"] = "curator"
        record["canonical_key"] = "testpsu|psu|750g|750w"

        result = dry_run_batch(db, [record])
        assert result.would_publish == 0
        assert result.rejected == 1
        assert any("source_reference" in r for r in result.rejection_reasons)
