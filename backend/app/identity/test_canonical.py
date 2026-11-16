"""M3 Phase 1 — canonical identity tests (RED first).

Pins the identity contract from docs/m3/M3_IDENTITY_RULES.md:
- canonical key determinism (same inputs -> byte-identical key)
- manufacturer alias collapse (G.SKILL vs gskill -> same key)
- kit vs module (RAM) are different identities
- capacity variants (storage) are different identities
- PSU wattage/efficiency/modularity variants are different identities
- motherboard revision policy (same key unless compatibility-bearing change)
- no silent merge: duplicate canonical keys are conflict candidates
"""
from __future__ import annotations

import pytest

from backend.app.identity.canonical import (
    canonical_key,
    normalize_manufacturer,
    variant_key,
)
from backend.app.identity.manufacturer_aliases import ALIASES


class TestManufacturerNormalization:
    def test_alias_collapse_gskill(self):
        assert normalize_manufacturer("G.SKILL") == "G.Skill"
        assert normalize_manufacturer("gskill") == "G.Skill"
        assert normalize_manufacturer("GSKILL") == "G.Skill"

    def test_alias_collapse_wd(self):
        assert normalize_manufacturer("Western Digital") == "Western Digital"
        assert normalize_manufacturer("WD") == "Western Digital"

    def test_unknown_keeps_input_trimmed(self):
        assert normalize_manufacturer("  Corsair  ") == "Corsair"

    def test_alias_table_is_nonempty_and_deterministic(self):
        assert len(ALIASES) > 0
        for alias, canonical in ALIASES.items():
            assert alias == alias.strip().lower()
            assert canonical == canonical.strip()


class TestCanonicalKeyDeterminism:
    def test_ram_kit_key(self):
        key = canonical_key(
            manufacturer="G.SKILL",
            hardware_type="RAM",
            family_or_model="Trident Z5 RGB 32GB (2x16GB) DDR5-6000 CL30",
            variant="kit-2x16-ddr56000",
        )
        assert key == "g.skill|ram|trident z5 rgb 32gb (2x16gb) ddr5-6000 cl30|kit-2x16-ddr56000"

    def test_same_inputs_byte_identical(self):
        a = canonical_key("Corsair", "PSU", "RM850x", "850w-gold-mod")
        b = canonical_key("corsair", "PSU", "RM850x", "850w-gold-mod")
        assert a == b

    def test_alias_manufacturers_same_key(self):
        a = canonical_key("G.SKILL", "RAM", "Trident Z5", "kit-2x16-ddr56000")
        b = canonical_key("gskill", "RAM", "Trident Z5", "kit-2x16-ddr56000")
        assert a == b

    def test_invisible_chars_never_break_identity(self):
        a = canonical_key("Corsair", "PSU", "RM850\u200bx", "850w-gold-mod")
        b = canonical_key("Corsair", "PSU", "RM850x", "850w-gold-mod")
        assert a == b

    def test_key_is_lowercase_and_bounded(self):
        key = canonical_key("Corsair", "PSU", "RM850x", "850w-gold-mod")
        assert key == key.lower()
        assert len(key) <= 300


class TestKitVsModule:
    def test_kit_and_module_different_keys(self):
        kit = canonical_key("G.Skill", "RAM", "Trident Z5 32GB", "kit-2x16-ddr56000")
        module = canonical_key("G.Skill", "RAM", "Trident Z5 32GB", "module-1x32-ddr56000")
        assert kit != module

    def test_variant_key_ram_kit(self):
        assert variant_key(
            "RAM",
            {"modules": 2, "capacity_gb": 32, "ddr_generation": "DDR5", "speed_mhz": 6000},
        ) == "kit-2x16-ddr56000"

    def test_variant_key_ram_module(self):
        assert variant_key(
            "RAM",
            {"modules": 1, "capacity_gb": 32, "ddr_generation": "DDR5", "speed_mhz": 5600},
        ) == "module-1x32-ddr55600"

    def test_variant_key_missing_components_omitted(self):
        # No generation/speed known: components are omitted, never "unknown".
        assert variant_key(
            "RAM", {"modules": 2, "capacity_gb": 16},
        ) == "kit-2x8"


class TestCapacityVariants:
    def test_storage_1tb_vs_2tb(self):
        a = variant_key("STORAGE", {"storage_type": "NVMe", "capacity_gb": 1024,
                                    "interface": "PCIe 4.0 x4"})
        b = variant_key("STORAGE", {"storage_type": "NVMe", "capacity_gb": 2048,
                                    "interface": "PCIe 4.0 x4"})
        assert a != b
        assert "1024gb" in a
        assert "2048gb" in b

    def test_motherboard_same_key_no_compat_change(self):
        a = canonical_key("ASUS", "MOTHERBOARD", "TUF Gaming B650-PLUS WIFI",
                          "atx-am5-b650")
        b = canonical_key("ASUS", "MOTHERBOARD", "TUF Gaming B650-PLUS WIFI",
                          "atx-am5-b650")
        assert a == b

    def test_motherboard_revision_changes_key_only_when_compat_bearing(self):
        base = "atx-am5-b650"
        rev = "atx-am5-b650-rev2"
        assert canonical_key("ASUS", "MOTHERBOARD", "TUF Gaming B650-PLUS", base) \
            != canonical_key("ASUS", "MOTHERBOARD", "TUF Gaming B650-PLUS", rev)

    def test_psu_modularity_variants(self):
        a = variant_key("PSU", {"wattage": 850, "efficiency_rating": "80 Plus Gold",
                                "modular": True})
        b = variant_key("PSU", {"wattage": 850, "efficiency_rating": "80 Plus Gold",
                                "modular": False})
        assert a != b


class TestDuplicatePolicy:
    def test_identical_keys_are_conflict_candidates_not_merges(self):
        """Two source rows producing the same canonical key MUST be reported,
        not merged. The identity module exposes a helper that detects this."""
        from backend.app.identity.canonical import duplicate_candidates

        rows = [
            {"name": "Corsair RM850x", "wattage": 850},
            {"name": "Corsair RM850x", "wattage": 750},
        ]
        keyed = [
            (canonical_key("Corsair", "PSU", r["name"], f"{r['wattage']}w-gold"), r)
            for r in rows
        ]
        # Different keys -> not duplicates (wattage differs -> different SKUs)
        assert duplicate_candidates(keyed) == []

        same_rows = [
            {"name": "Corsair RM850x", "wattage": 850},
            {"name": "corsair rm850x", "wattage": 850},
        ]
        keyed_same = [
            (canonical_key("Corsair", "PSU", r["name"], f"{r['wattage']}w-gold"), r)
            for r in same_rows
        ]
        groups = duplicate_candidates(keyed_same)
        assert len(groups) == 1
        assert len(groups[0]) == 2
