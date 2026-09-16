import unittest
from types import SimpleNamespace

from backend.app.importers.geekbench_unmatched_audit import (
    CATALOG_AVAILABLE,
    NEEDS_REVIEW,
    NORMALIZATION_GAP,
    NOT_FOUND,
    _catalog_lookup,
    _classify_unmatched,
    _hardware_gap_lookup,
)
from backend.app.models import Hardware


class GeekbenchUnmatchedAuditTests(unittest.TestCase):
    def _unmatched(self, name, manufacturer, normalized_name=None):
        return SimpleNamespace(
            name=name,
            manufacturer=manufacturer,
            normalized_name=normalized_name or name.lower(),
        )

    def test_exact_catalog_entry_is_catalog_available(self):
        rows = [
            {
                "CpuName": "AMD Ryzen 3 2200G",
                "Cores": "4",
                "Threads": "4",
                "ClockSpeed": "3.5 GHz",
                "TurboSpeed": "3.7 GHz",
                "TDP": "65 W",
                "Socket": "AM4",
                "ReleaseDate": "Q1 2018",
                "SourceUrl": "https://example.test/2200g",
            }
        ]
        catalog = _catalog_lookup(rows)
        unmatched = [
            self._unmatched(
                "AMD Ryzen 3 2200G",
                "AMD",
                "amd ryzen 3 2200g",
            )
        ]

        result = _classify_unmatched(unmatched, catalog, {})

        self.assertEqual(result.records[0].category, CATALOG_AVAILABLE)
        self.assertEqual(result.records[0].catalog_entries[0].cores, 4)

    def test_hidden_format_character_is_normalization_gap(self):
        hardware = Hardware(
            id=74,
            name="AMD Ryzen 9 6900HS\u200b",
            manufacturer="AMD",
            type="CPU",
        )
        hardware_lookup = _hardware_gap_lookup([hardware])
        unmatched = [
            self._unmatched(
                "AMD Ryzen 9 6900HS",
                "AMD",
                "amd ryzen 9 6900hs",
            )
        ]

        result = _classify_unmatched(unmatched, {}, hardware_lookup)

        self.assertEqual(result.records[0].category, NORMALIZATION_GAP)
        self.assertEqual(result.records[0].hardware.hardware_id, 74)

    def test_duplicate_catalog_entries_require_review(self):
        rows = [
            {
                "CpuName": "Intel Xeon E5-2696 v4 @ 2.20GHz",
                "Cores": "22",
                "Threads": "44",
            },
            {
                "CpuName": "[Dual CPU] Intel Xeon E5-2696 v4 @ 2.20GHz",
                "Cores": "22",
                "Threads": "44",
            },
        ]
        catalog = _catalog_lookup(rows)
        unmatched = [
            self._unmatched(
                "Intel Xeon E5-2696 v4",
                "Intel",
                "intel xeon e5-2696 v4",
            )
        ]

        result = _classify_unmatched(unmatched, catalog, {})

        self.assertEqual(result.records[0].category, NEEDS_REVIEW)
        self.assertEqual(len(result.records[0].catalog_entries), 2)

    def test_missing_everywhere_is_not_found(self):
        unmatched = [
            self._unmatched(
                "AMD Ryzen 5 9999X",
                "AMD",
                "amd ryzen 5 9999x",
            )
        ]

        result = _classify_unmatched(unmatched, {}, {})

        self.assertEqual(result.records[0].category, NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
