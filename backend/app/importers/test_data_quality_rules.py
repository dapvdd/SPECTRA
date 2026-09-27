"""Regression tests for objective hardware data-quality rules.

These cover the normalization and numeric-parsing rules that were found to
be non-objective during the Sprint 13 data-quality audit:

- invisible Unicode control/format characters are removed from names, and
  are not allowed to survive whitespace collapsing;
- a wattage is parsed only from a plain non-negative decimal followed by a
  complete watt unit, so signed and scientific-notation values cannot be
  silently reduced to a different magnitude.
"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.importers.benchmark_matcher import normalize_match_name
from backend.app.importers.benchmark_normalizer import (
    normalize_name as normalize_benchmark_name,
    parse_watt as parse_benchmark_watt,
    strip_invisible_characters,
)
from backend.app.importers.cpu_normalizer import (
    normalize_name as normalize_cpu_name,
    parse_watt as parse_cpu_watt,
)
from backend.app.migrations.normalize_hardware_names import (
    apply_correction,
    find_affected_hardware,
)
from backend.app.models import Hardware

ZERO_WIDTH_SPACE = "\u200b"
SOFT_HYPHEN = "\u00ad"
LEFT_TO_RIGHT_MARK = "\u200e"

NAME_NORMALIZERS = (normalize_cpu_name, normalize_benchmark_name)
WATT_PARSERS = (parse_cpu_watt, parse_benchmark_watt)


def _hardware(name):
    return Hardware(
        name=name,
        manufacturer="AMD",
        type="CPU",
    )


class InvisibleCharacterTests(unittest.TestCase):
    def test_zero_width_space_is_removed(self):
        self.assertEqual(
            strip_invisible_characters(f"AMD Ryzen 7 7736U{ZERO_WIDTH_SPACE}"),
            "AMD Ryzen 7 7736U",
        )

    def test_soft_hyphen_and_direction_marks_are_removed(self):
        self.assertEqual(
            strip_invisible_characters(
                f"AMD EPYC{SOFT_HYPHEN} 7252{LEFT_TO_RIGHT_MARK}"
            ),
            "AMD EPYC 7252",
        )

    def test_visible_letters_are_preserved(self):
        self.assertEqual(
            strip_invisible_characters("Caf\u00e9 Core"),
            "Caf\u00e9 Core",
        )

    def test_names_lose_trailing_zero_width_space(self):
        for normalizer in NAME_NORMALIZERS:
            self.assertEqual(
                normalizer(f"AMD Ryzen 7 7736U{ZERO_WIDTH_SPACE}"),
                "AMD Ryzen 7 7736U",
                normalizer.__name__,
            )

    def test_repeated_zero_width_spaces_are_removed(self):
        for normalizer in NAME_NORMALIZERS:
            self.assertEqual(
                normalizer(f"AMD Ryzen{ZERO_WIDTH_SPACE * 3} 9 5950X"),
                "AMD Ryzen 9 5950X",
                normalizer.__name__,
            )

    def test_tab_and_newline_become_a_single_space_not_a_deletion(self):
        for normalizer in NAME_NORMALIZERS:
            self.assertEqual(
                normalizer("AMD\tRyzen\n9  5950X"),
                "AMD Ryzen 9 5950X",
                normalizer.__name__,
            )

    def test_trademark_symbols_are_still_removed(self):
        self.assertEqual(
            normalize_cpu_name("AMD Ryzen\u2122 5 7520C"),
            "AMD Ryzen 5 7520C",
        )
        self.assertEqual(
            normalize_cpu_name("Intel\u00ae Core\u2122 i7"),
            "Intel Core i7",
        )

    def test_empty_and_none_stay_empty(self):
        for normalizer in NAME_NORMALIZERS:
            self.assertIsNone(normalizer(None), normalizer.__name__)
            self.assertIsNone(normalizer(""), normalizer.__name__)


class IdentityResolutionTests(unittest.TestCase):
    def test_zero_width_space_does_not_defeat_match_identity(self):
        self.assertEqual(
            normalize_match_name(f"AMD Ryzen 7 7736U{ZERO_WIDTH_SPACE}"),
            normalize_match_name("AMD Ryzen 7 7736U"),
        )

    def test_tab_and_space_produce_the_same_match_identity(self):
        self.assertEqual(
            normalize_match_name("AMD\tRyzen 9 5950X"),
            normalize_match_name("AMD Ryzen 9 5950X"),
        )

    def test_existing_match_normalization_still_applies(self):
        self.assertEqual(
            normalize_match_name(
                f"[Dual CPU] AMD EPYC 7252{ZERO_WIDTH_SPACE}"
            ),
            "amd epyc 7252",
        )
        self.assertEqual(
            normalize_match_name("Intel Xeon E5-1650 v3 @ 3.50GHz"),
            "intel xeon e5-1650 v3",
        )


class WattParsingTests(unittest.TestCase):
    def test_well_formed_wattages_are_parsed(self):
        for value, expected in (
            ("105 W", 105.0),
            ("105W", 105.0),
            ("105 watts", 105.0),
            ("105 watt", 105.0),
            ("65 W (TDP)", 65.0),
            ("TDP 105W", 105.0),
            ("(105W)", 105.0),
            ("0.025 W", 0.025),
            ("0.5W", 0.5),
        ):
            for parser in WATT_PARSERS:
                self.assertEqual(
                    parser(value), expected, f"{parser.__name__}({value!r})"
                )

    def test_genuine_sub_watt_value_is_preserved(self):
        # Intel Quark Microcontroller D1000 is a real 25 mW part. A low
        # wattage is not by itself evidence of a data defect.
        for parser in WATT_PARSERS:
            self.assertEqual(parser("0.025 W"), 0.025, parser.__name__)

    def test_signed_wattage_is_not_reduced_to_its_magnitude(self):
        for parser in WATT_PARSERS:
            self.assertIsNone(parser("-5 W"), parser.__name__)

    def test_scientific_notation_is_not_reduced_to_its_coefficient(self):
        for parser in WATT_PARSERS:
            self.assertIsNone(parser("1e3 W"), parser.__name__)

    def test_milliwatts_are_not_read_as_watts(self):
        for parser in WATT_PARSERS:
            self.assertIsNone(parser("65000 mW"), parser.__name__)
            self.assertIsNone(parser("65000mW"), parser.__name__)

    def test_trailing_w_of_a_longer_word_is_not_a_unit(self):
        for parser in WATT_PARSERS:
            self.assertIsNone(parser("Unspecified 1 waffle"), parser.__name__)
            self.assertIsNone(parser("105 WW"), parser.__name__)

    def test_missing_and_unrelated_values_stay_missing(self):
        for value in (
            None,
            "",
            "   ",
            "N/A",
            "Unknown",
            "105",
            "Max. Boost Clock 5.7 GHz",
        ):
            for parser in WATT_PARSERS:
                self.assertIsNone(parser(value), f"{parser.__name__}({value!r})")


class HardwareNameCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_invisible_character_names_are_reported(self):
        self.session.add_all(
            [
                _hardware(f"AMD Ryzen 7 7736U{ZERO_WIDTH_SPACE}"),
                _hardware(f"AMD Ryzen 9 6900HS{ZERO_WIDTH_SPACE}"),
                _hardware("AMD Ryzen 7 5700X"),
            ]
        )
        self.session.commit()

        affected = find_affected_hardware(self.session)

        self.assertEqual(
            sorted(changed[0] for changed in affected),
            [1, 2],
        )
        self.assertEqual(
            dict((row_id, after) for row_id, _, after in affected)[1],
            "AMD Ryzen 7 7736U",
        )

    def test_visible_name_is_never_altered(self):
        self.session.add(
            _hardware("Intel Core i7-5960X @ 3.00GHz")
        )
        self.session.commit()

        self.assertEqual(find_affected_hardware(self.session), [])

    def test_correction_is_idempotent(self):
        self.session.add_all(
            [
                _hardware(f"AMD Ryzen 7 7736U{ZERO_WIDTH_SPACE}"),
                _hardware(f"AMD Ryzen 5 6600HS{ZERO_WIDTH_SPACE}"),
                _hardware("AMD Ryzen 7 5700X"),
            ]
        )
        self.session.commit()

        first_run = apply_correction(self.session)
        second_run = apply_correction(self.session)

        self.assertEqual(len(first_run), 2)
        self.assertEqual(second_run, [])

        names = [
            hardware.name
            for hardware in self.session.query(Hardware).order_by(Hardware.id)
        ]
        self.assertEqual(
            names,
            [
                "AMD Ryzen 7 7736U",
                "AMD Ryzen 5 6600HS",
                "AMD Ryzen 7 5700X",
            ],
        )


if __name__ == "__main__":
    unittest.main()
