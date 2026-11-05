"""Regression tests for safe GPU identity resolution.

Ensures that:
- Model-number digits are preserved (5770 != 7970, 48 != 16, 600 != 3600).
- Desktop vs mobile suffixes are preserved.
- Vendor prefixes are safely stripped.
- Ambiguous multi-candidate scenarios are quarantined.
"""
import pytest
from backend.app.scripts.gpu_identity import (
    strip_vendor_prefix,
    identity_tokens,
    safe_gpu_match,
    gpu_collides,
)


class TestStripVendorPrefix:
    @pytest.mark.parametrize("name, expected", [
        ("MSI GeForce RTX 4090", "GeForce RTX 4090"),
        ("NVIDIA GeForce RTX 4090", "GeForce RTX 4090"),
        ("ASUS ROG Strix RTX 4090", "ROG Strix RTX 4090"),
        ("XFX AMD Radeon RX 6700 XT", "AMD Radeon RX 6700 XT"),
        ("AMD Radeon HD 5770", "Radeon HD 5770"),
        ("Intel GMA 600", "GMA 600"),
        ("Sapphire AMD Radeon R5", "AMD Radeon R5"),
        ("No-prefix GPU", "No-prefix GPU"),
        ("  leading spaces  ", "leading spaces"),
    ])
    def test_strips_known_prefixes(self, name, expected):
        assert strip_vendor_prefix(name) == expected


class TestIdentityTokens:
    def test_preserves_model_digits(self):
        tokens = identity_tokens("NVIDIA GeForce RTX 4090")
        assert "4090" in tokens
        assert "nvidia" not in tokens  # vendor stripped

    def test_hd_5770_vs_hd_7970_differ(self):
        t5770 = identity_tokens("AMD Radeon HD 5770")
        t7970 = identity_tokens("AMD Radeon HD 7970")
        assert "5770" in t5770
        assert "7970" in t7970
        assert t5770 != t7970

    def test_gma_600_vs_gma_3600_differ(self):
        t600  = identity_tokens("Intel GMA 600")
        t3600 = identity_tokens("Intel GMA 3600")
        assert "600" in t600
        assert "3600" in t3600
        assert t600 != t3600

    def test_vega_48_vs_vega_16_differ(self):
        t48 = identity_tokens("AMD Radeon Pro Vega 48")
        t16 = identity_tokens("AMD Radeon Pro Vega 16")
        assert t48 != t16

    def test_mobile_suffix_preserved(self):
        t_desk  = identity_tokens("NVIDIA GeForce RTX 4090")
        t_mobil = identity_tokens("NVIDIA GeForce RTX 4090 Mobile")
        # Desktop and mobile are DIFFERENT hardware profiles; tokens differ.
        assert "mobile" in t_mobil
        assert "mobile" not in t_desk
        assert t_desk != t_mobil


class TestSafeGpuMatch:
    def test_rtx_4090_exact_match(self):
        assert safe_gpu_match("MSI GeForce RTX 4090", "GeForce RTX 4090") is True

    def test_rtx_4090_variant_match(self):
        assert safe_gpu_match("ASUS GeForce RTX 4090 Gaming", "GeForce RTX 4090") is True

    def test_wrong_model_not_match(self):
        # HD 5770 CSV row must NOT match HD 7970 DB entry
        assert safe_gpu_match("AMD Radeon HD 5770", "Radeon HD 7970") is False

    def test_gma_600_not_gma_3600(self):
        assert safe_gpu_match("Intel GMA 600", "GMA 3600") is False

    def test_vega_48_not_vega_16(self):
        assert safe_gpu_match("AMD Radeon Pro Vega 48", "Radeon Pro Vega 16") is False

    def test_no_digits_is_false(self):
        # "Graphics" has no model number — not a valid identity match
        assert safe_gpu_match("Vendor Graphics Card", "Graphics") is False

    def test_mobile_desktop_distinct(self):
        # HD 6970M must not match HD 6970 (different hardware)
        assert safe_gpu_match("AMD Radeon HD 6970M", "Radeon HD 6970") is False


class TestGpuCollides:
    def test_same_name_no_collision(self):
        assert gpu_collides("AMD Radeon HD 5770", "AMD Radeon HD 5770") is False

    def test_different_model_digits_collision(self):
        assert gpu_collides("AMD Radeon HD 5770", "AMD Radeon HD 7970") is True

    def test_gma_600_vs_3600_collision(self):
        assert gpu_collides("Intel GMA 600", "Intel GMA 3600") is True

    def test_vega_48_vs_16_collision(self):
        assert gpu_collides("AMD Radeon Pro Vega 48", "AMD Radeon Pro Vega 16") is True
