"""Unit tests for the deterministic segment classifier (Phase B).

Every test encodes a *hand-verified* product fact (manufacturer-designated
naming convention or explicit published segment). No test relies on the
classifier's own output — they pin expected behavior.

Run from repo root: python -m pytest data/research/test_segment_classifier.py -q
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from segment_classifier import classify  # noqa: E402


def c(name, htype, manuf):
    m = classify(name, htype, manuf)
    return m["segment"] if m else None


class MobileExplicitWordTests(unittest.TestCase):
    def test_literal_mobile_word(self):
        self.assertEqual(
            c("AMD Athlon PRO 200U Mobile Processor with Radeon Vega 3 Graphics",
              "CPU", "AMD"),
            "mobile",
        )

    def test_mobility_radeon(self):
        self.assertEqual(
            c("Mobility Radeon HD 4850", "GPU", "ATI"), "mobile"
        )

    def test_maxq(self):
        self.assertEqual(
            c("GeForce RTX 3070 Max-Q", "GPU", "NVIDIA"), "mobile"
        )


class NvidiaMobileTests(unittest.TestCase):
    def test_classic_geforce_m(self):
        self.assertEqual(
            c("NVIDIA GeForce GT 710M", "GPU", "NVIDIA"), "mobile"
        )
        self.assertEqual(
            c("NVIDIA GeForce 310M", "GPU", "NVIDIA"), "mobile"
        )

    def test_mx_series(self):
        self.assertEqual(
            c("NVIDIA GeForce 940MX", "GPU", "NVIDIA"), "mobile"
        )
        self.assertEqual(
            c("NVIDIA GeForce MX450", "GPU", "NVIDIA"), "mobile"
        )

    def test_nvs_m(self):
        self.assertEqual(
            c("NVIDIA NVS 5200M", "GPU", "NVIDIA"), "mobile"
        )

    def test_rtx_a_mobile(self):
        self.assertEqual(
            c("NVIDIA GeForce RTX 3050 A Mobile", "GPU", "NVIDIA"), "mobile"
        )


class AmdMobileTests(unittest.TestCase):
    def test_firepro_m_series_mobile(self):
        # FirePro M2000 is the MOBILE part; bare Quadro M2000 is desktop.
        self.assertEqual(c("ATI FirePro M2000", "GPU", "ATI"), "mobile")

    def test_radeon_rx_m(self):
        self.assertEqual(
            c("AMD Radeon RX 5500M", "GPU", "AMD"), "mobile"
        )

    def test_radeon_r_m(self):
        self.assertEqual(c("AMD Radeon R5 M230", "GPU", "AMD"), "mobile")

    def test_firepro_w_mobile(self):
        # FirePro W5100 is desktop workstation; W5170M is mobile.
        self.assertEqual(c("AMD FirePro W5170M", "GPU", "AMD"), "mobile")
        self.assertEqual(c("AMD FirePro W5100", "GPU", "AMD"), "workstation")

    def test_radeon_pro_mobile(self):
        self.assertEqual(c("AMD Radeon Pro 5300M", "GPU", "AMD"), "mobile")
        self.assertEqual(c("AMD Radeon Pro WX 4100", "GPU", "AMD"), "workstation")


class IntelMobileTests(unittest.TestCase):
    def test_arc_m(self):
        self.assertEqual(c("Intel Arc A370M", "GPU", "Intel"), "mobile")
        self.assertEqual(c("Intel Arc A750", "GPU", "Intel"), None)

    def test_cpu_mobile_suffix(self):
        self.assertEqual(c("AMD Ryzen 9 7945HX", "CPU", "AMD"), "mobile")
        self.assertEqual(c("Intel Core i7-13700H", "CPU", "Intel"), "mobile")
        # P-suffix is genuinely ambiguous (desktop Core i5-6402P exists alongside
        # mobile Core i5-1240P). The classifier MUST refuse, not guess.
        self.assertIsNone(c("Intel Core i5-1240P", "CPU", "Intel"))
        self.assertEqual(c("AMD Ryzen 5 5600U", "CPU", "AMD"), "mobile")


class ServerTests(unittest.TestCase):
    def test_epyc(self):
        self.assertEqual(c("AMD EPYC 9654", "CPU", "AMD"), "server")

    def test_xeon(self):
        self.assertEqual(c("Intel Xeon Platinum 8458P", "CPU", "Intel"), "server")

    def test_tesla(self):
        self.assertEqual(
            c("NVIDIA Tesla V100 SXM2 32 GB", "GPU", "NVIDIA"), "server"
        )

    def test_firepro_s_server(self):
        # FirePro S9000 is a rack GPU compute card, not workstation.
        self.assertEqual(c("AMD FirePro S9000", "GPU", "AMD"), "server")

    def test_firepro_d_server(self):
        self.assertEqual(c("AMD FirePro D500", "GPU", "AMD"), "server")

    def test_instinct(self):
        self.assertEqual(c("AMD Radeon Instinct MI100", "GPU", "AMD"), "server")


class WorkstationTests(unittest.TestCase):
    def test_quadro(self):
        self.assertEqual(c("NVIDIA Quadro 4000", "GPU", "NVIDIA"), "workstation")
        # Quadro M2000 is a DESKTOP workstation card (bare M, no double-M).
        self.assertEqual(c("NVIDIA Quadro M2000", "GPU", "NVIDIA"), "workstation")
        # Quadro M2200 Mobile / M2000M are mobile.
        self.assertEqual(c("NVIDIA Quadro M2200 Mobile", "GPU", "NVIDIA"), "mobile")

    def test_radeon_pro_workstation(self):
        self.assertEqual(c("AMD Radeon Pro WX 8200", "GPU", "AMD"), "workstation")

    def test_cpu_with_embedded_pro_gpu_is_not_workstation(self):
        # Kaby Lake-G CPU: 'Radeon Pro' is its embedded GPU, not its segment.
        self.assertEqual(
            c("Intel Core i7-8706G Processor with Radeon Pro WX Vega M GL graphics",
              "CPU", "Intel"),
            None,
        )


class RefusedAmbiguityTests(unittest.TestCase):
    """The classifier must REFUSE ambiguous evidence rather than guess."""

    def test_desktop_geforce_without_suffix_is_null(self):
        self.assertEqual(c("NVIDIA GeForce RTX 3060", "GPU", "NVIDIA"), None)

    def test_desktop_gtx_without_suffix_is_null(self):
        self.assertEqual(c("NVIDIA GeForce GTX 1650", "GPU", "NVIDIA"), None)

    def test_intel_hd_graphics_without_mobile_word_is_null(self):
        self.assertEqual(c("Intel HD Graphics 4000", "GPU", "Intel"), None)

    def test_amd_radeon_desktop_without_m_is_null(self):
        self.assertEqual(c("AMD Radeon RX 580", "GPU", "AMD"), None)

    def test_apple_silicon_untrusted(self):
        self.assertIsNone(c("Apple M1", "CPU", "Apple"))


class ClosedVocabularyConsistencyTests(unittest.TestCase):
    def test_segments_match_migration_vocabulary(self):
        # Must match backend/app/migrations/add_hardware_segment.py SEGMENT_VALUES.
        for name, htype, manuf, expected in [
            ("AMD EPYC 9654", "CPU", "AMD", "server"),
            ("AMD Ryzen 5 5600U", "CPU", "AMD", "mobile"),
            ("NVIDIA Quadro 4000", "GPU", "NVIDIA", "workstation"),
        ]:
            self.assertEqual(c(name, htype, manuf), expected)


if __name__ == "__main__":
    unittest.main()
