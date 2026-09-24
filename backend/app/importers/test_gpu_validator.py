import unittest

from backend.app.importers.gpu_validator import validate_gpu

VALID_GPU = {
    "name": "GeForce RTX 5090",
    "manufacturer": "NVIDIA",
    "type": "GPU",
    "release_date": "2025-01-30",
    "architecture": "Blackwell 2.0",
    "memory_gb": 32.0,
    "memory_type": "GDDR7",
    "core_clock_mhz": 2235.0,
    "boost_clock_mhz": 2407.0,
    "vram_bandwidth_gbps": 1790.0,
    "tdp_w": 575.0,
    "interface": "PCIe 5.0 x16",
    "length_mm": 304.0,
}


def _gpu(**overrides):
    record = dict(VALID_GPU)
    record.update(overrides)
    return record


class GpuValidationTests(unittest.TestCase):
    def test_valid_full_gpu_has_no_errors(self):
        self.assertEqual(validate_gpu(VALID_GPU), [])

    def test_valid_minimum_record_missing_optional_fields(self):
        record = _gpu(
            memory_gb=None,
            memory_type=None,
            core_clock_mhz=None,
            boost_clock_mhz=None,
            vram_bandwidth_gbps=None,
            tdp_w=None,
            interface=None,
            length_mm=None,
        )

        self.assertEqual(validate_gpu(record), [])

    def test_invalid_manufacturer_is_rejected(self):
        self.assertIn(
            "manufacturer",
            validate_gpu(_gpu(manufacturer="Unknown"))[0],
        )
        self.assertIn(
            "manufacturer",
            validate_gpu(_gpu(manufacturer="Matrox"))[0],
        )
        self.assertIn(
            "manufacturer",
            validate_gpu(_gpu(manufacturer=None))[0],
        )

    def test_all_four_allowed_manufacturers_pass(self):
        for manufacturer in ("NVIDIA", "AMD", "Intel", "ATI"):
            self.assertEqual(
                validate_gpu(_gpu(manufacturer=manufacturer)),
                [],
                manufacturer,
            )

    def test_wrong_type_is_rejected(self):
        errors = validate_gpu(_gpu(type="CPU"))
        self.assertIn("type must be GPU", errors)

    def test_missing_name_is_rejected(self):
        self.assertIn("name is required", validate_gpu(_gpu(name="")))
        self.assertIn("name is required", validate_gpu(_gpu(name=None)))

    def test_zero_and_negative_memory_are_rejected(self):
        self.assertIn(
            "memory_gb", validate_gpu(_gpu(memory_gb=0))[0]
        )
        self.assertIn(
            "memory_gb", validate_gpu(_gpu(memory_gb=-16))[0]
        )

    def test_out_of_range_memory_is_rejected(self):
        self.assertIn("memory_gb", validate_gpu(_gpu(memory_gb=129))[0])
        self.assertIn("memory_gb", validate_gpu(_gpu(memory_gb=0.5))[0])

    def test_boundary_memory_values_pass(self):
        self.assertEqual(validate_gpu(_gpu(memory_gb=1)), [])
        self.assertEqual(validate_gpu(_gpu(memory_gb=128)), [])

    def test_none_memory_is_valid(self):
        self.assertEqual(validate_gpu(_gpu(memory_gb=None)), [])

    def test_invalid_clock_values_are_rejected(self):
        self.assertIn(
            "core_clock_mhz", validate_gpu(_gpu(core_clock_mhz=0))[0]
        )
        self.assertIn(
            "boost_clock_mhz", validate_gpu(_gpu(boost_clock_mhz=-500))[0]
        )

    def test_out_of_range_clocks_are_rejected(self):
        self.assertIn(
            "core_clock_mhz", validate_gpu(_gpu(core_clock_mhz=99))[0]
        )
        self.assertIn(
            "core_clock_mhz", validate_gpu(_gpu(core_clock_mhz=4001))[0]
        )
        self.assertIn(
            "boost_clock_mhz", validate_gpu(_gpu(boost_clock_mhz=99.9))[0]
        )
        self.assertIn(
            "boost_clock_mhz", validate_gpu(_gpu(boost_clock_mhz=5000))[0]
        )

    def test_boundary_clock_values_pass(self):
        self.assertEqual(validate_gpu(_gpu(core_clock_mhz=100)), [])
        self.assertEqual(validate_gpu(_gpu(core_clock_mhz=4000)), [])
        self.assertEqual(validate_gpu(_gpu(boost_clock_mhz=100)), [])
        self.assertEqual(validate_gpu(_gpu(boost_clock_mhz=4000)), [])

    def test_none_clocks_are_valid(self):
        self.assertEqual(validate_gpu(_gpu(core_clock_mhz=None)), [])
        self.assertEqual(validate_gpu(_gpu(boost_clock_mhz=None)), [])

    def test_non_numeric_values_are_rejected(self):
        self.assertIn(
            "memory_gb", validate_gpu(_gpu(memory_gb="32 GB"))[0]
        )
        self.assertIn(
            "tdp_w", validate_gpu(_gpu(tdp_w="not-a-number"))[0]
        )

    def test_zero_and_negative_bandwidth_are_rejected(self):
        self.assertIn(
            "vram_bandwidth_gbps",
            validate_gpu(_gpu(vram_bandwidth_gbps=0))[0],
        )
        self.assertIn(
            "vram_bandwidth_gbps",
            validate_gpu(_gpu(vram_bandwidth_gbps=-1))[0],
        )

    def test_none_bandwidth_is_valid(self):
        self.assertEqual(validate_gpu(_gpu(vram_bandwidth_gbps=None)), [])

    def test_zero_and_negative_tdp_are_rejected(self):
        self.assertIn("tdp_w", validate_gpu(_gpu(tdp_w=0))[0])
        self.assertIn("tdp_w", validate_gpu(_gpu(tdp_w=-65))[0])

    def test_out_of_range_tdp_is_rejected(self):
        self.assertIn("tdp_w", validate_gpu(_gpu(tdp_w=1501))[0])

    def test_boundary_tdp_values_pass(self):
        self.assertEqual(validate_gpu(_gpu(tdp_w=1)), [])
        self.assertEqual(validate_gpu(_gpu(tdp_w=1500)), [])

    def test_none_tdp_is_valid(self):
        self.assertEqual(validate_gpu(_gpu(tdp_w=None)), [])

    def test_zero_length_is_rejected(self):
        self.assertIn("length_mm", validate_gpu(_gpu(length_mm=0))[0])

    def test_none_length_is_valid(self):
        self.assertEqual(validate_gpu(_gpu(length_mm=None)), [])


if __name__ == "__main__":
    unittest.main()