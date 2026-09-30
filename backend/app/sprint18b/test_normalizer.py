import unittest

from backend.app.sprint18b.normalizer import (
    normalize_cpu_row,
    normalize_gpu_row,
    normalize_manufacturer,
    normalize_name,
    normalize_sample,
    parse_ghz,
    parse_int,
    parse_length_mm,
    parse_mhz,
    parse_memory_gb,
    parse_watt,
    strip_invisible_characters,
)
from backend.app.sprint18b.sample_data import SAMPLE_CPUS, SAMPLE_GPUS


class StripInvisibleTests(unittest.TestCase):
    def test_removes_non_breaking_space(self):
        self.assertEqual(
            strip_invisible_characters("AMD Ryzen 5 5600\u00a0"),
            "AMD Ryzen 5 5600",
        )

    def test_removes_zero_width_space(self):
        self.assertEqual(
            strip_invisible_characters("Intel\u200b Core i5"),
            "Intel Core i5",
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
        self.assertEqual(normalize_name("AMD Ryzen 5 5600\u00a0"), "AMD Ryzen 5 5600")

    def test_empty_becomes_none(self):
        self.assertIsNone(normalize_name(""))
        self.assertIsNone(normalize_name(None))
        self.assertIsNone(normalize_name("   "))


class NormalizeManufacturerTests(unittest.TestCase):
    def test_canonical_manufacturers(self):
        self.assertEqual(normalize_manufacturer("AMD"), "AMD")
        self.assertEqual(normalize_manufacturer("Intel"), "Intel")
        self.assertEqual(normalize_manufacturer("NVIDIA"), "NVIDIA")
        self.assertEqual(normalize_manufacturer("Apple"), "Apple")
        self.assertEqual(normalize_manufacturer("Qualcomm"), "Qualcomm")

    def test_case_insensitive(self):
        self.assertEqual(normalize_manufacturer("amd"), "AMD")
        self.assertEqual(normalize_manufacturer("INTEL"), "Intel")

    def test_unknown_becomes_unknown(self):
        self.assertEqual(normalize_manufacturer(""), "Unknown")
        self.assertEqual(normalize_manufacturer(None), "Unknown")
        self.assertEqual(normalize_manufacturer("Matrox"), "Matrox")


class ParseGhzTests(unittest.TestCase):
    def test_valid_ghz(self):
        self.assertEqual(parse_ghz("3.5 GHz"), 3.5)
        self.assertEqual(parse_ghz("4.4 GHz"), 4.4)
        self.assertEqual(parse_ghz("2.45 GHz"), 2.45)

    def test_up_to_prefix(self):
        self.assertEqual(parse_ghz("up to 4.9 GHz"), 4.9)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_ghz(""))
        self.assertIsNone(parse_ghz(None))
        self.assertIsNone(parse_ghz("unknown"))
        self.assertIsNone(parse_ghz("3.5"))


class ParseMhzTests(unittest.TestCase):
    def test_valid_mhz(self):
        self.assertEqual(parse_mhz("2010 MHz"), 2010.0)
        self.assertEqual(parse_mhz("2407 MHz"), 2407.0)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_mhz(""))
        self.assertIsNone(parse_mhz(None))
        self.assertIsNone(parse_mhz("2010"))
        self.assertIsNone(parse_mhz("unknown"))


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


class ParseMemoryGbTests(unittest.TestCase):
    def test_gb_value(self):
        self.assertEqual(parse_memory_gb("32 GB"), 32.0)
        self.assertEqual(parse_memory_gb("12 GB"), 12.0)

    def test_mb_value(self):
        self.assertAlmostEqual(parse_memory_gb("256 MB"), 0.25)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_memory_gb(""))
        self.assertIsNone(parse_memory_gb(None))
        self.assertIsNone(parse_memory_gb("unknown"))


class ParseLengthMmTests(unittest.TestCase):
    def test_valid_mm(self):
        self.assertEqual(parse_length_mm("304 mm"), 304.0)
        self.assertEqual(parse_length_mm("272 mm"), 272.0)

    def test_invalid_becomes_none(self):
        self.assertIsNone(parse_length_mm(""))
        self.assertIsNone(parse_length_mm(None))
        self.assertIsNone(parse_length_mm("unknown"))


class NormalizeCpuRowTests(unittest.TestCase):
    def test_full_cpu_row(self):
        row = {
            "name": "AMD Ryzen 5 5600",
            "manufacturer": "AMD",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        result = normalize_cpu_row(row)
        self.assertEqual(result["name"], "AMD Ryzen 5 5600")
        self.assertEqual(result["manufacturer"], "AMD")
        self.assertEqual(result["type"], "CPU")
        self.assertEqual(result["cores"], 6)
        self.assertEqual(result["threads"], 12)
        self.assertEqual(result["base_clock_ghz"], 3.5)
        self.assertEqual(result["boost_clock_ghz"], 4.4)
        self.assertEqual(result["tdp_w"], 65.0)
        self.assertEqual(result["socket"], "AM4")

    def test_cpu_with_missing_optional_fields(self):
        row = {
            "name": "Apple M1",
            "manufacturer": "Apple",
            "cores": "8",
            "threads": "8",
            "base_clock": "3.2 GHz",
            "boost_clock": "",
            "tdp": "",
            "socket": "",
            "release_date": "2020-11-17",
        }
        result = normalize_cpu_row(row)
        self.assertEqual(result["name"], "Apple M1")
        self.assertIsNone(result["boost_clock_ghz"])
        self.assertIsNone(result["tdp_w"])
        self.assertIsNone(result["socket"])

    def test_cpu_with_invisible_characters(self):
        row = {
            "name": "AMD Ryzen 5 5600\u00a0",
            "manufacturer": "AMD",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        result = normalize_cpu_row(row)
        self.assertEqual(result["name"], "AMD Ryzen 5 5600")


class NormalizeGpuRowTests(unittest.TestCase):
    def test_full_gpu_row(self):
        row = {
            "name": "NVIDIA GeForce RTX 5090",
            "manufacturer": "NVIDIA",
            "memory_gb": "32 GB",
            "memory_type": "GDDR7",
            "core_clock": "2010 MHz",
            "boost_clock": "2407 MHz",
            "tdp": "575 W",
            "interface": "PCIe 5.0 x16",
            "length_mm": "304 mm",
            "release_date": "2025-01-30",
        }
        result = normalize_gpu_row(row)
        self.assertEqual(result["name"], "NVIDIA GeForce RTX 5090")
        self.assertEqual(result["manufacturer"], "NVIDIA")
        self.assertEqual(result["type"], "GPU")
        self.assertEqual(result["memory_gb"], 32.0)
        self.assertEqual(result["memory_type"], "GDDR7")
        self.assertEqual(result["core_clock_mhz"], 2010.0)
        self.assertEqual(result["boost_clock_mhz"], 2407.0)
        self.assertEqual(result["tdp_w"], 575.0)
        self.assertEqual(result["interface"], "PCIe 5.0 x16")
        self.assertEqual(result["length_mm"], 304.0)

    def test_gpu_with_missing_optional_fields(self):
        row = {
            "name": "AMD Radeon RX 580",
            "manufacturer": "AMD",
            "memory_gb": "8 GB",
            "memory_type": "GDDR5",
            "core_clock": "1257 MHz",
            "boost_clock": "1340 MHz",
            "tdp": "185 W",
            "interface": "PCIe 3.0 x16",
            "length_mm": "",
            "release_date": "2017-04-18",
        }
        result = normalize_gpu_row(row)
        self.assertEqual(result["name"], "AMD Radeon RX 580")
        self.assertIsNone(result["length_mm"])


class NormalizeSampleTests(unittest.TestCase):
    def test_normalizes_all_sample_cpus(self):
        cpus, gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        self.assertEqual(len(cpus), 10)
        self.assertEqual(len(gpus), 10)

    def test_all_sample_cpus_have_names(self):
        cpus, _ = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        for cpu in cpus:
            self.assertIsNotNone(cpu["name"])

    def test_all_sample_gpus_have_names(self):
        _, gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        for gpu in gpus:
            self.assertIsNotNone(gpu["name"])


if __name__ == "__main__":
    unittest.main()
