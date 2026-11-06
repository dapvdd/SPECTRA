"""Unit tests for `suitability_service` star-mapping functions.

The `_score_to_stars` function maps a raw benchmark score to a 1..5 star range
using anchor points.  These tests cover the boundary branches that were not
exercised by the API-level suitability tests.

Anchors are read from the live module (verified empirically before writing):
- _MULTI_CORE_ANCHORS: (1409.0, 2809.0, 5001.0, 8017.0, 16347.0)
- _SINGLE_CORE_ANCHORS: (667.0, 983.0, 1325.0, 1637.0, 2020.0)
"""

from __future__ import annotations

from backend.app.services.suitability_service import _score_to_stars


# Multi-core anchor range (larger, easier to reason about boundary positions)
_MULTI_LO = 1409.0
_MULTI_HI = 16347.0
_MULTI_ANCHORS = (1409.0, 2809.0, 5001.0, 8017.0, 16347.0)

# Single-core anchor range
_SINGLE_LO = 667.0
_SINGLE_HI = 2020.0
_SINGLE_ANCHORS = (667.0, 983.0, 1325.0, 1637.0, 2020.0)


class TestScoreToStarsMultiCore:
    """Boundary tests using the multi-core anchor range."""

    def test_at_lower_bound_returns_one_star(self):
        assert _score_to_stars(_MULTI_LO, _MULTI_ANCHORS) == 1.0

    def test_below_lower_bound_returns_one_star(self):
        assert _score_to_stars(_MULTI_LO - 100.0, _MULTI_ANCHORS) == 1.0

    def test_at_upper_bound_returns_five_stars(self):
        assert _score_to_stars(_MULTI_HI, _MULTI_ANCHORS) == 5.0

    def test_above_upper_bound_returns_five_stars(self):
        assert _score_to_stars(_MULTI_HI + 100.0, _MULTI_ANCHORS) == 5.0


class TestScoreToStarsSingleCore:
    """Boundary tests using the single-core anchor range (spot-checked)."""

    def test_at_lower_bound_returns_one_star(self):
        assert _score_to_stars(_SINGLE_LO, _SINGLE_ANCHORS) == 1.0

    def test_above_upper_bound_returns_five_stars(self):
        assert _score_to_stars(_SINGLE_HI + 100.0, _SINGLE_ANCHORS) == 5.0
