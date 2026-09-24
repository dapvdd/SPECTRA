import unittest
from pathlib import Path

import pytest

from backend.app.importers.gpu_csv import read_gpu_csv
from backend.app.importers.gpu_normalizer import (
    detect_gpu_manufacturer,
    normalize_gpu_name,
    normalize_gpu_row,
    parse_length_mm,
    parse_memory_size_gb,
    parse_mhz,
    parse_release_date,
    parse_vram_bandwidth_gbps,
)

RAW_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "raw" / "gpu_1986-2026.csv"
)


def _row(updates=None):
    row = {
        "Brand": "NVIDIA",
        "Name": "GeForce RTX 5090",
        "Graphics Card__Release Date": "Jan 30th, 2025",
        "Graphics Processor__Architecture": "Blackwell 2.0",
        "Memory__Memory Size": "32 GB",
        "Memory__Memory Type": "GDDR7",
        "Memory__Bandwidth": "1.79 TB/s",
        "Clock Speeds__GPU Clock": "",
        "Clock Speeds__Boost Clock": "2407 MHz",
        "Board Design__TDP": "575 W",
        "Graphics Card__Bus Interface": "PCIe 5.0 x16",
        "Board Design__Length": "304 mm 12 inches",
    }
    if updates:
        row.update(updates)
    return row


class ManufacturerNormalizationTests(unittest.TestCase):
    def test_nvidia_is_recognized(self):
        self.assertEqual(detect_gpu_manufacturer("NVIDIA"), "NVIDIA")

    def test_amd_is_recognized(self):
        self.assertEqual(detect_gpu_manufacturer("AMD"), "AMD")

    def test_intel_is_recognized(self):
        self.assertEqual(detect_gpu_manufacturer("Intel"), "Intel")

    def test_ati_is_recognized(self):
        self.assertEqual(detect_gpu_manufacturer("ATI"), "ATI")

    def test_unknown_manufacturer_is_not_guessed(self):
        self.assertEqual(detect_gpu_manufacturer(""), "Unknown")
        self.assertEqual(detect_gpu_manufacturer(None), "Unknown")
        self.assertEqual(detect_gpu_manufacturer("  "), "Unknown")

    def test_unlisted_manufacturer_is_preserved(self):
        self.assertEqual(detect_gpu_manufacturer("Matrox"), "Matrox")
        self.assertEqual(detect_gpu_manufacturer("3dfx"), "3dfx")


class NameNormalizationTests(unittest.TestCase):
    def test_whitespace_is_collapsed(self):
        self.assertEqual(
            normalize_gpu_name("  GeForce   RTX   5090 "),
            "GeForce RTX 5090",
        )

    def test_vendor_prefix_is_stripped(self):
        self.assertEqual(
            normalize_gpu_name("NVIDIA GeForce RTX 5090", "NVIDIA"),
            "GeForce RTX 5090",
        )
        self.assertEqual(
            normalize_gpu_name("Intel Arc B580", "Intel"),
            "Arc B580",
        )

    def test_name_without_brand_prefix_is_kept(self):
        self.assertEqual(
            normalize_gpu_name("GeForce RTX 5090", "NVIDIA"),
            "GeForce RTX 5090",
        )

    def test_distinct_model_variants_remain_distinct(self):
        self.assertNotEqual(
            normalize_gpu_name("GeForce RTX 5060 Ti 16 GB"),
            normalize_gpu_name("GeForce RTX 5060 Ti 8 GB"),
        )

    def test_empty_name_becomes_none(self):
        self.assertIsNone(normalize_gpu_name(""))
        self.assertIsNone(normalize_gpu_name(None))


class MemoryParsingTests(unittest.TestCase):
    def test_regular_gb_value(self):
        self.assertEqual(parse_memory_size_gb("32 GB"), 32.0)
        self.assertEqual(parse_memory_size_gb("12 GB"), 12.0)

    def test_megabyte_value_is_converted(self):
        self.assertAlmostEqual(parse_memory_size_gb("256 MB"), 0.25)
        self.assertAlmostEqual(parse_memory_size_gb("64 MB"), 0.0625)

    def test_kilobyte_value_is_converted(self):
        self.assertAlmostEqual(
            parse_memory_size_gb("32 KB"),
            32.0 / (1024.0 ** 2),
        )

    def test_shared_memory_becomes_none(self):
        self.assertIsNone(parse_memory_size_gb("System Shared"))
        self.assertIsNone(parse_memory_size_gb("Shared"))

    def test_missing_value_becomes_none(self):
        self.assertIsNone(parse_memory_size_gb(""))
        self.assertIsNone(parse_memory_size_gb(None))

    def test_malformed_value_becomes_none(self):
        self.assertIsNone(parse_memory_size_gb("12GBS"))
        self.assertIsNone(parse_memory_size_gb("unknown"))
        self.assertIsNone(parse_memory_size_gb("?"))
        self.assertIsNone(parse_memory_size_gb("1,024 MB"))


class MemoryTypeTests(unittest.TestCase):
    def test_memory_types_are_preserved(self):
        for value in ("GDDR6", "GDDR6X", "GDDR7", "HBM2", "HBM2e",
                      "HBM3", "HBM3e", "DRAM", "System Shared"):
            record = normalize_gpu_row(
                _row({"Memory__Memory Type": value})
            )
            self.assertEqual(record["memory_type"], value)

    def test_whitespace_is_collapsed(self):
        record = normalize_gpu_row(
            _row({"Memory__Memory Type": " GDDR6  X "})
        )
        self.assertEqual(record["memory_type"], "GDDR6 X")

    def test_missing_memory_type_becomes_none(self):
        self.assertIsNone(
            normalize_gpu_row(
                _row({"Memory__Memory Type": ""})
            )["memory_type"]
        )


class ClockParsingTests(unittest.TestCase):
    def test_regular_mhz_value(self):
        self.assertEqual(parse_mhz("2070 MHz"), 2070.0)
        self.assertEqual(parse_mhz("2407 MHz"), 2407.0)

    def test_missing_markers_become_none(self):
        self.assertIsNone(parse_mhz("? MHz"))
        self.assertIsNone(parse_mhz("-"))
        self.assertIsNone(parse_mhz("unknown"))
        self.assertIsNone(parse_mhz(""))
        self.assertIsNone(parse_mhz(None))

    def test_malformed_value_becomes_none(self):
        self.assertIsNone(parse_mhz("1200"))
        self.assertIsNone(parse_mhz("1200 MHz extra"))

    def test_boost_clock_is_not_substituted_from_core_clock(self):
        record = normalize_gpu_row(_row({
            "Clock Speeds__GPU Clock": "2070 MHz",
            "Clock Speeds__Boost Clock": "",
        }))
        self.assertEqual(record["core_clock_mhz"], 2070.0)
        self.assertIsNone(record["boost_clock_mhz"])


class TdpParsingTests(unittest.TestCase):
    def test_valid_tdp(self):
        record = normalize_gpu_row(_row({"Board Design__TDP": "575 W"}))
        self.assertEqual(record["tdp_w"], 575.0)

    def test_missing_tdp_becomes_none(self):
        self.assertIsNone(
            normalize_gpu_row(
                _row({"Board Design__TDP": "unknown"})
            )["tdp_w"]
        )
        self.assertIsNone(
            normalize_gpu_row(_row({"Board Design__TDP": ""}))["tdp_w"]
        )


class BandwidthParsingTests(unittest.TestCase):
    def test_gb_per_second_value(self):
        self.assertEqual(parse_vram_bandwidth_gbps("960.0 GB/s"), 960.0)

    def test_tb_per_second_value_is_converted(self):
        self.assertEqual(parse_vram_bandwidth_gbps("1.79 TB/s"), 1790.0)

    def test_mb_per_second_value_is_converted(self):
        self.assertAlmostEqual(parse_vram_bandwidth_gbps("20.00 MB/s"), 0.02)

    def test_system_dependent_becomes_none(self):
        self.assertIsNone(parse_vram_bandwidth_gbps("System Dependent"))

    def test_missing_value_becomes_none(self):
        self.assertIsNone(parse_vram_bandwidth_gbps(""))
        self.assertIsNone(parse_vram_bandwidth_gbps(None))


class InterfaceAndLengthTests(unittest.TestCase):
    def test_interface_is_preserved(self):
        record = normalize_gpu_row(
            _row({"Graphics Card__Bus Interface": "PCIe 5.0 x16"})
        )
        self.assertEqual(record["interface"], "PCIe 5.0 x16")

    def test_interface_missing_becomes_none(self):
        self.assertIsNone(
            normalize_gpu_row(
                _row({"Graphics Card__Bus Interface": ""})
            )["interface"]
        )

    def test_length_mm(self):
        self.assertEqual(parse_length_mm("304 mm 12 inches"), 304.0)
        self.assertEqual(parse_length_mm("272 mm 10.7 inches"), 272.0)

    def test_length_missing_becomes_none(self):
        self.assertIsNone(parse_length_mm(""))
        self.assertIsNone(
            normalize_gpu_row(
                _row({"Board Design__Length": ""})
            )["length_mm"]
        )


class ReleaseDateTests(unittest.TestCase):
    def test_full_date_is_normalized(self):
        self.assertEqual(parse_release_date("Jan 30th, 2025"), "2025-01-30")
        self.assertEqual(parse_release_date("Feb 5th, 1990"), "1990-02-05")

    def test_year_only_keeps_reduced_precision(self):
        self.assertEqual(parse_release_date("2022"), "2022")

    def test_missing_and_malformed_become_none(self):
        self.assertIsNone(parse_release_date(""))
        self.assertIsNone(parse_release_date(None))
        self.assertIsNone(parse_release_date("not-a-date"))

    def test_architecture_is_preserved(self):
        record = normalize_gpu_row(
            _row({"Graphics Processor__Architecture": "Blackwell 2.0"})
        )
        self.assertEqual(record["architecture"], "Blackwell 2.0")
        self.assertIsNone(
            normalize_gpu_row(
                _row({"Graphics Processor__Architecture": ""})
            )["architecture"]
        )


class RowNormalizationTests(unittest.TestCase):
    def test_rtx_5090_row_normalizes_to_full_record(self):
        record = normalize_gpu_row(_row())

        self.assertEqual(record["name"], "GeForce RTX 5090")
        self.assertEqual(record["manufacturer"], "NVIDIA")
        self.assertEqual(record["type"], "GPU")
        self.assertEqual(record["release_date"], "2025-01-30")
        self.assertEqual(record["architecture"], "Blackwell 2.0")
        self.assertEqual(record["memory_gb"], 32.0)
        self.assertEqual(record["memory_type"], "GDDR7")
        self.assertIsNone(record["core_clock_mhz"])
        self.assertEqual(record["boost_clock_mhz"], 2407.0)
        self.assertEqual(record["vram_bandwidth_gbps"], 1790.0)
        self.assertEqual(record["tdp_w"], 575.0)
        self.assertEqual(record["interface"], "PCIe 5.0 x16")
        self.assertEqual(record["length_mm"], 304.0)

    def test_legacy_ati_row_normalizes(self):
        record = normalize_gpu_row({
            "Brand": "ATI",
            "Name": "Color Emulation Card",
            "Graphics Card__Release Date": "Aug 4th, 1986",
            "Graphics Processor__Architecture": "Wonder",
            "Memory__Memory Size": "32 KB",
            "Memory__Memory Type": "DRAM",
            "Memory__Bandwidth": "20.00 MB/s",
            "Clock Speeds__GPU Clock": "10 MHz",
            "Clock Speeds__Boost Clock": "",
            "Board Design__TDP": "unknown",
            "Graphics Card__Bus Interface": "ISA 8-bit",
            "Board Design__Length": "",
        })

        self.assertEqual(record["name"], "Color Emulation Card")
        self.assertEqual(record["manufacturer"], "ATI")
        self.assertEqual(record["release_date"], "1986-08-04")
        self.assertAlmostEqual(record["memory_gb"], 32.0 / (1024.0 ** 2))
        self.assertEqual(record["memory_type"], "DRAM")
        self.assertAlmostEqual(record["vram_bandwidth_gbps"], 0.02)
        self.assertEqual(record["core_clock_mhz"], 10.0)
        self.assertIsNone(record["boost_clock_mhz"])
        self.assertIsNone(record["tdp_w"])
        self.assertEqual(record["interface"], "ISA 8-bit")
        self.assertIsNone(record["length_mm"])


class RealDatasetIntegrationTests(unittest.TestCase):
    def test_actual_dataset_rows_normalize_to_expected_fields(self):
        if not RAW_DATASET_PATH.is_file():
            pytest.skip("raw GPU dataset is not present")

        rows = read_gpu_csv(RAW_DATASET_PATH)
        by_name = {normalize_gpu_row(r)["name"]: r for r in rows}

        checks = {
            "GeForce RTX 5090": {
                "manufacturer": "NVIDIA",
                "memory_gb": 32.0,
                "memory_type": "GDDR7",
                "boost_clock_mhz": 2407.0,
                "vram_bandwidth_gbps": 1790.0,
                "tdp_w": 575.0,
                "interface": "PCIe 5.0 x16",
                "length_mm": 304.0,
            },
            "GeForce RTX 5080": {
                "manufacturer": "NVIDIA",
                "memory_gb": 16.0,
                "memory_type": "GDDR7",
                "vram_bandwidth_gbps": 960.0,
            },
            "GeForce RTX 5070 Ti": {
                "manufacturer": "NVIDIA",
                "memory_gb": 16.0,
                "memory_type": "GDDR7",
                "vram_bandwidth_gbps": 896.0,
            },
            "Radeon RX 7900 XTX": {
                "manufacturer": "AMD",
                "memory_gb": 24.0,
                "memory_type": "GDDR6",
                "vram_bandwidth_gbps": 960.0,
            },
            "Arc B580": {
                "manufacturer": "Intel",
                "memory_gb": 12.0,
                "memory_type": "GDDR6",
                "boost_clock_mhz": 2670.0,
                "tdp_w": 190.0,
                "interface": "PCIe 4.0 x8",
            },
        }

        for name, expected in checks.items():
            self.assertIn(name, by_name, name)
            record = normalize_gpu_row(by_name[name])
            for field, value in expected.items():
                self.assertEqual(
                    record[field], value, f"{name}.{field}"
                )

    def test_actual_dataset_rows_contain_modern_blackwell_gpus(self):
        if not RAW_DATASET_PATH.is_file():
            pytest.skip("raw GPU dataset is not present")

        rows = read_gpu_csv(RAW_DATASET_PATH)
        names = {normalize_gpu_row(r)["name"] for r in rows}

        self.assertIn("GeForce RTX 5090", names)
        self.assertIn("GeForce RTX 5080", names)
        self.assertIn("GeForce RTX 5070 Ti", names)


if __name__ == "__main__":
    unittest.main()