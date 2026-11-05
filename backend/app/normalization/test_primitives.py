"""Tests for the shared normalization primitives (Phase 1.5).

These primitives were moved verbatim from
``backend/app/importers/benchmark_normalizer.py`` into
``backend.app.normalization.primitives``. The tests pin the behavior so that a
future change to the shared home cannot silently alter importer output.
"""

import unittest

from backend.app.normalization.primitives import (
    INVISIBLE_CHARACTER_CATEGORIES,
    normalize_name,
    parse_int,
    parse_watt,
    strip_invisible_characters,
)


class StripInvisibleCharactersTests(unittest.TestCase):
    def test_removes_control_and_format_characters(self):
        self.assertEqual(
            strip_invisible_characters("Intel\u200b Core i5"),
            "Intel Core i5",
        )
        self.assertEqual(
            strip_invisible_characters("AMD\u200e Ryzen"),
            "AMD Ryzen",
        )

    def test_preserves_visible_characters(self):
        self.assertEqual(
            strip_invisible_characters("AMD Ryzen 5 5600"),
            "AMD Ryzen 5 5600",
        )


class NormalizeNameTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(normalize_name("  AMD   Ryzen  5  "), "AMD Ryzen 5")

    def test_strips_invisible_characters(self):
        self.assertEqual(
            normalize_name("AMD Ryzen 5 5600\u200b"),
            "AMD Ryzen 5 5600",
        )

    def test_empty_becomes_none(self):
        self.assertIsNone(normalize_name(""))
        self.assertIsNone(normalize_name(None))

    def test_whitespace_only_collapses_to_empty_string(self):
        # The benchmark variant returns value.strip() directly, which collapses
        # whitespace-only input to "" (not None). Pinning this matches the
        # original importer behavior exactly.
        self.assertEqual(normalize_name("   "), "")


class ParseWattTests(unittest.TestCase):
    def test_valid_watt(self):
        self.assertEqual(parse_watt("65 W"), 65.0)
        self.assertEqual(parse_watt("105 W"), 105.0)
        self.assertEqual(parse_watt("575 W"), 575.0)

    def test_watts_suffix(self):
        self.assertEqual(parse_watt("65 Watts"), 65.0)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_watt(""))
        self.assertIsNone(parse_watt(None))
        self.assertIsNone(parse_watt("unknown"))
        self.assertIsNone(parse_watt("-5 W"))


class ParseIntTests(unittest.TestCase):
    def test_valid_int(self):
        self.assertEqual(parse_int("6"), 6)
        self.assertEqual(parse_int("128"), 128)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int("6.5"))
        self.assertIsNone(parse_int("unknown"))


class PackageExportsTests(unittest.TestCase):
    def test_package_re_exports_the_primitives(self):
        from backend.app.normalization import (
            normalize_name as package_normalize_name,
            parse_int as package_parse_int,
            parse_watt as package_parse_watt,
            strip_invisible_characters as package_strip,
        )

        self.assertIs(package_normalize_name, normalize_name)
        self.assertIs(package_parse_int, parse_int)
        self.assertIs(package_parse_watt, parse_watt)
        self.assertIs(package_strip, strip_invisible_characters)


if __name__ == "__main__":
    unittest.main()
