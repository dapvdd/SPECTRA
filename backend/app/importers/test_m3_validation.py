"""M3 Phase 3 — category validation rules tests (RED first).

Pins docs/m3 contract (mission §5):
- unit semantics: MB/s vs Gb/s never conflated; MHz vs MT/s recorded honestly
  (RAM speed column stays speed_mhz but accepted tokens must be MT/s);
  TDP vs measured power (PSU wattage is rated output, never a TDP claim);
  PCIe generation is not physical-connector compatibility.
- range checks per field
- cross-field consistency (RAM modules×per-module = capacity; PSU wattage
  vs efficiency tier; storage capacity vs interface sanity)
- missing-data classification (optional vs critical fields)
- source conflict detection (same identity, different facts)
- quality scoring (0-100, deterministic; never manufactures compatibility)

Fail-closed: any CRITICAL-class problem blocks the approved publication set.
"""
from __future__ import annotations

import pytest

from backend.app.importers.m3_validation import (
    Conflict,
    ValidationOutcome,
    classify_missing,
    cross_field_checks,
    detect_conflicts,
    quality_score,
    range_checks,
    unit_checks,
    validate_record,
)


class TestUnitChecks:
    def test_ram_speed_accepts_mt_s_tokens(self):
        ok = unit_checks("RAM", {"speed_mhz": 6000})
        assert ok.passed

    def test_ram_speed_rejects_absurd_values(self):
        # 6 MHz is a clock, not a transfer rate; 6,000,000 is a typo.
        assert not unit_checks("RAM", {"speed_mhz": 6}).passed
        assert not unit_checks("RAM", {"speed_mhz": 6_000_000}).passed

    def test_storage_mb_s_vs_gb_s_range(self):
        # PCIe 4.0 sequential read cannot be 14,000 MB/s? Actually it can be
        # ~7,400; 14,000 would be a Gb/s mislabeled as MB/s.
        assert not unit_checks("STORAGE", {"read_mb_s": 14000}).passed
        assert unit_checks("STORAGE", {"read_mb_s": 7400}).passed

    def test_psu_wattage_is_rated_output_not_tdp(self):
        ok = unit_checks("PSU", {"wattage": 850})
        assert ok.passed
        # 85 W "PSU" is nonsense for ATX; fail-closed.
        assert not unit_checks("PSU", {"wattage": 85}).passed

    def test_pcie_generation_is_not_connector_compatibility(self):
        # The check itself never outputs a compatibility claim; it only
        # validates the value vocabulary.
        ok = unit_checks("STORAGE", {"interface": "PCIe 4.0 x4"})
        assert ok.passed


class TestRangeChecks:
    def test_ram_capacity_bounds(self):
        assert range_checks("RAM", {"capacity_gb": 16}).passed
        assert not range_checks("RAM", {"capacity_gb": 0}).passed
        assert not range_checks("RAM", {"capacity_gb": 999_999}).passed

    def test_storage_capacity_bounds(self):
        assert range_checks("STORAGE", {"capacity_gb": 1024}).passed
        assert not range_checks("STORAGE", {"capacity_gb": 5_000_000}).passed

    def test_motherboard_slot_counts(self):
        assert range_checks("MOTHERBOARD", {"ram_slots": 4, "sata_ports": 6}).passed
        assert not range_checks("MOTHERBOARD", {"ram_slots": 64}).passed

    def test_psu_wattage_bounds(self):
        assert range_checks("PSU", {"wattage": 850}).passed
        assert not range_checks("PSU", {"wattage": 50_000}).passed


class TestCrossField:
    def test_ram_kit_capacity_consistency(self):
        ok = cross_field_checks("RAM", {"modules": 2, "capacity_gb": 32})
        assert ok.passed
        bad = cross_field_checks("RAM", {"modules": 3, "capacity_gb": 32})
        assert not bad.passed

    def test_ram_capacity_divisible_by_modules(self):
        bad = cross_field_checks("RAM", {"modules": 2, "capacity_gb": 15})
        assert not bad.passed

    def test_psu_high_end_efficiency_needs_reasonable_wattage(self):
        ok = cross_field_checks("PSU", {"wattage": 1200,
                                        "efficiency_rating": "80 Plus Titanium"})
        assert ok.passed

    def test_motherboard_ram_slots_vs_max_ram(self):
        ok = cross_field_checks("MOTHERBOARD", {"ram_slots": 4, "max_ram_gb": 192})
        assert ok.passed


class TestMissingClassification:
    def test_ram_critical_fields(self):
        missing = classify_missing("RAM", {"capacity_gb": 32, "ddr_generation": "DDR5",
                                           "speed_mhz": 6000, "modules": 2})
        assert missing.critical == []
        assert "voltage_v" in missing.optional

    def test_psu_critical_missing_blocks(self):
        missing = classify_missing("PSU", {"wattage": 850})
        assert "efficiency_rating" in missing.critical

    def test_motherboard_socket_is_critical(self):
        missing = classify_missing("MOTHERBOARD", {"chipset": "B650"})
        assert "socket" in missing.critical


class TestConflicts:
    def test_same_key_different_wattage_is_conflict(self):
        a = {"canonical_key": "corsair|psu|rm850x|850w-gold-mod", "wattage": 850,
             "source_name": "S1"}
        b = {"canonical_key": "corsair|psu|rm850x|850w-gold-mod", "wattage": 750,
             "source_name": "S2"}
        conflicts = detect_conflicts([a, b])
        assert len(conflicts) == 1
        assert isinstance(conflicts[0], Conflict)
        assert conflicts[0].field == "wattage"

    def test_same_key_same_values_no_conflict(self):
        a = {"canonical_key": "k|ram|x|kit-2x16", "capacity_gb": 32, "source_name": "S1"}
        b = {"canonical_key": "k|ram|x|kit-2x16", "capacity_gb": 32, "source_name": "S2"}
        assert detect_conflicts([a, b]) == []

    def test_different_keys_never_conflict(self):
        a = {"canonical_key": "k1", "wattage": 850, "source_name": "S1"}
        b = {"canonical_key": "k2", "wattage": 750, "source_name": "S2"}
        assert detect_conflicts([a, b]) == []


class TestQualityScore:
    def test_full_record_scores_high(self):
        record = {
            "name": "X", "manufacturer": "Corsair", "wattage": 850,
            "efficiency_rating": "80 Plus Gold", "modular": True,
            "pcie_8pin_count": 4, "pcie_12vhpwr": 1,
        }
        score = quality_score("PSU", record)
        assert 0 <= score <= 100
        assert score >= 80

    def test_sparse_record_scores_low(self):
        record = {"name": "Y", "manufacturer": "Corsair", "wattage": 850}
        score = quality_score("PSU", record)
        assert score < 50

    def test_score_is_deterministic(self):
        record = {"name": "Z", "manufacturer": "Corsair", "wattage": 750,
                  "efficiency_rating": "80 Plus Gold"}
        assert quality_score("PSU", record) == quality_score("PSU", dict(record))


class TestValidateRecordGate:
    def test_valid_psu_record_passes(self):
        outcome = validate_record("PSU", {
            "name": "Corsair RM850x", "manufacturer": "Corsair",
            "wattage": 850, "efficiency_rating": "80 Plus Gold", "modular": True,
        })
        assert isinstance(outcome, ValidationOutcome)
        assert outcome.passed
        assert outcome.blockers == []

    def test_invalid_wattage_blocks(self):
        outcome = validate_record("PSU", {
            "name": "Corsair RM85", "manufacturer": "Corsair", "wattage": 85,
            "efficiency_rating": "80 Plus Gold",
        })
        assert not outcome.passed
        assert any("wattage" in b for b in outcome.blockers)

    def test_critical_missing_blocks(self):
        outcome = validate_record("PSU", {
            "name": "Mystery PSU", "manufacturer": "Corsair", "wattage": 650,
        })
        assert not outcome.passed

    def test_kit_capacity_mismatch_blocks(self):
        outcome = validate_record("RAM", {
            "name": "Bad Kit", "manufacturer": "G.Skill",
            "capacity_gb": 33, "modules": 2, "ddr_generation": "DDR5",
            "speed_mhz": 6000,
        })
        assert not outcome.passed
