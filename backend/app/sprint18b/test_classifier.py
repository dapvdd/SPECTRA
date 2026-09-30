import unittest

from backend.app.sprint18b.classifier import (
    Classification,
    classify_cpu,
    classify_gpu,
    classify_hardware,
)
from backend.app.sprint18b.normalizer import normalize_cpu_row, normalize_gpu_row
from backend.app.sprint18b.sample_data import SAMPLE_CPUS, SAMPLE_GPUS


class ClassifyCpuTests(unittest.TestCase):
    def test_complete_cpu_is_match(self):
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
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.MATCH)
        self.assertEqual(reasons, [])

    def test_cpu_missing_name_is_not_found(self):
        row = {
            "name": "",
            "manufacturer": "AMD",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.NOT_FOUND)
        self.assertIn("missing required fields: name", reasons)

    def test_cpu_missing_manufacturer_is_not_found(self):
        row = {
            "name": "AMD Ryzen 5 5600",
            "manufacturer": "",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.NOT_FOUND)
        self.assertIn("missing required fields: manufacturer", reasons)

    def test_cpu_missing_cores_is_needs_review(self):
        row = {
            "name": "AMD Ryzen 5 5600",
            "manufacturer": "AMD",
            "cores": "",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.NEEDS_REVIEW)
        self.assertIn("missing required fields: cores", reasons)

    def test_cpu_inconsistent_manufacturer_is_ambiguous(self):
        row = {
            "name": "AMD Ryzen 5 5600",
            "manufacturer": "Intel",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.AMBIGUOUS)
        self.assertIn("manufacturer inconsistent with name", reasons)

    def test_cpu_ambiguous_name_is_needs_review(self):
        row = {
            "name": "AMD Ryzen 5 5600 (engineering sample)",
            "manufacturer": "AMD",
            "cores": "6",
            "threads": "12",
            "base_clock": "3.5 GHz",
            "boost_clock": "4.4 GHz",
            "tdp": "65 W",
            "socket": "AM4",
            "release_date": "2022-04-04",
        }
        record = normalize_cpu_row(row)
        classification, reasons = classify_cpu(record)
        self.assertEqual(classification, Classification.NEEDS_REVIEW)
        self.assertIn("ambiguous name pattern", reasons)


class ClassifyGpuTests(unittest.TestCase):
    def test_complete_gpu_is_match(self):
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
        record = normalize_gpu_row(row)
        classification, reasons = classify_gpu(record)
        self.assertEqual(classification, Classification.MATCH)
        self.assertEqual(reasons, [])

    def test_gpu_missing_name_is_not_found(self):
        row = {
            "name": "",
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
        record = normalize_gpu_row(row)
        classification, reasons = classify_gpu(record)
        self.assertEqual(classification, Classification.NOT_FOUND)
        self.assertIn("missing required fields: name", reasons)

    def test_gpu_missing_memory_is_needs_review(self):
        row = {
            "name": "NVIDIA GeForce RTX 5090",
            "manufacturer": "NVIDIA",
            "memory_gb": "",
            "memory_type": "GDDR7",
            "core_clock": "2010 MHz",
            "boost_clock": "2407 MHz",
            "tdp": "575 W",
            "interface": "PCIe 5.0 x16",
            "length_mm": "304 mm",
            "release_date": "2025-01-30",
        }
        record = normalize_gpu_row(row)
        classification, reasons = classify_gpu(record)
        self.assertEqual(classification, Classification.NEEDS_REVIEW)
        self.assertIn("missing required fields: memory_gb", reasons)

    def test_gpu_inconsistent_manufacturer_is_ambiguous(self):
        row = {
            "name": "NVIDIA GeForce RTX 5090",
            "manufacturer": "AMD",
            "memory_gb": "32 GB",
            "memory_type": "GDDR7",
            "core_clock": "2010 MHz",
            "boost_clock": "2407 MHz",
            "tdp": "575 W",
            "interface": "PCIe 5.0 x16",
            "length_mm": "304 mm",
            "release_date": "2025-01-30",
        }
        record = normalize_gpu_row(row)
        classification, reasons = classify_gpu(record)
        self.assertEqual(classification, Classification.AMBIGUOUS)
        self.assertIn("manufacturer inconsistent with name", reasons)


class ClassifyHardwareTests(unittest.TestCase):
    def test_classifies_all_sample_data(self):
        from backend.app.sprint18b.normalizer import normalize_sample

        cpus, gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        results = classify_hardware(cpus, gpus)
        self.assertEqual(len(results), 20)

    def test_all_results_have_classification(self):
        from backend.app.sprint18b.normalizer import normalize_sample

        cpus, gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        results = classify_hardware(cpus, gpus)
        for result in results:
            self.assertIn("classification", result)
            self.assertIn(
                result["classification"],
                ["MATCH", "NEEDS_REVIEW", "AMBIGUOUS", "NOT_FOUND"],
            )

    def test_all_results_have_reasons(self):
        from backend.app.sprint18b.normalizer import normalize_sample

        cpus, gpus = normalize_sample(SAMPLE_CPUS, SAMPLE_GPUS)
        results = classify_hardware(cpus, gpus)
        for result in results:
            self.assertIn("reasons", result)
            self.assertIsInstance(result["reasons"], list)


if __name__ == "__main__":
    unittest.main()
