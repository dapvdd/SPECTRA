"""Phase 1.2 tests for the benchmark quality scoring service.

The score is a deterministic, heuristic evidence-quality indicator — a
normalised weight of observable signals (attribution, timestamp, licence,
provenance vote). It is explicitly NOT a statistically calibrated probability.
These tests pin the formula so a change cannot silently reweight it.
"""

import unittest
from datetime import datetime

from backend.app.services import benchmark_quality_service
from backend.app.services.benchmark_quality_service import (
    quality_to_response_field,
    score_benchmark_quality,
)


class _Source:
    def __init__(self, license_status=None):
        self.license_status = license_status


class _Provenance:
    def __init__(self, evidence_status):
        self.evidence_status = evidence_status


def _bmark(
    *,
    source_id=None,
    recorded_at=None,
    source=None,
    provenance=(),
):
    class Benchmark:
        pass

    benchmark = Benchmark()
    benchmark.source_id = source_id
    benchmark.recorded_at = recorded_at
    benchmark.source = source
    benchmark.field_provenance = provenance
    return benchmark


class QualityScoringTests(unittest.TestCase):
    def test_all_signals_plus_clear_licence_yields_high_score(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("verified"),),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        # 0.35 + 0.25 + 0.20 + 0.20 = 1.0
        self.assertEqual(quality["score"], 1.0)
        self.assertEqual(quality["band"], "high")
        self.assertFalse(quality["vetoed"])
        self.assertTrue(quality["signals"]["attribution"])
        self.assertTrue(quality["signals"]["timestamp"])
        self.assertTrue(quality["signals"]["licence"])
        self.assertTrue(quality["signals"]["evidence_verified"])

    def test_no_signals_yields_honest_zero_score(self):
        benchmark = _bmark()

        quality = score_benchmark_quality(benchmark=benchmark)

        # Zero observable evidence is a real low score, not a veto.
        self.assertEqual(quality["score"], 0.0)
        self.assertEqual(quality["band"], "low")
        self.assertFalse(quality["vetoed"])
        self.assertFalse(quality["signals"]["attribution"])
        self.assertFalse(quality["signals"]["timestamp"])
        self.assertFalse(quality["signals"]["licence"])

    def test_attribution_and_timestamp_without_licence_yields_medium(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="unknown"),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        # 0.35 + 0.25 = 0.6
        self.assertEqual(quality["score"], 0.6)
        self.assertEqual(quality["band"], "medium")
        self.assertFalse(quality["signals"]["licence"])

    def test_verified_provenance_boosts_evidence_signal(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("verified"),),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        # licence (0.2) + evidence verified (0.2) + attribution + timestamp
        self.assertEqual(quality["score"], 1.0)
        self.assertTrue(quality["signals"]["evidence_verified"])
        self.assertFalse(quality["signals"]["evidence_uncertain"])
        self.assertEqual(quality["band"], "high")

    def test_uncertain_provenance_contributes_partial_evidence(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("uncertain"),),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        # attribution + timestamp + licence + 0.5*evidence(0.2)
        self.assertEqual(quality["score"], 0.9)
        self.assertTrue(quality["signals"]["evidence_uncertain"])
        self.assertEqual(quality["band"], "high")

    def test_excluded_provenance_vetoes_the_score(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("excluded"),),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        self.assertIsNone(quality["score"])
        self.assertIsNone(quality["band"])
        self.assertTrue(quality["vetoed"])
        self.assertEqual(quality["label"], "no score")

    def test_unmatched_provenance_vetoes_the_score(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("unmatched"),),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        self.assertIsNone(quality["score"])
        self.assertTrue(quality["vetoed"])
        self.assertEqual(quality["label"], "no score")

    def test_missing_source_metadata_means_no_attribution_or_licence(self):
        # source_id present but the source row itself is absent.
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=None,
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        self.assertTrue(quality["signals"]["attribution"])
        self.assertFalse(quality["signals"]["licence"])
        self.assertEqual(quality["score"], 0.6)

    def test_score_is_deterministic_across_repeated_calls(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("verified"),),
        )

        first = score_benchmark_quality(benchmark=benchmark)
        second = score_benchmark_quality(benchmark=benchmark)
        third = score_benchmark_quality(benchmark=benchmark)

        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_mixed_provenance_with_veto_overrides_verified(self):
        benchmark = _bmark(
            source_id=1,
            recorded_at=datetime(2026, 9, 16),
            source=_Source(license_status="clear"),
            provenance=(_Provenance("verified"), _Provenance("excluded")),
        )

        quality = score_benchmark_quality(benchmark=benchmark)

        # A single veto always wins: an excluded source must never be scored.
        self.assertIsNone(quality["score"])
        self.assertTrue(quality["vetoed"])

    def test_response_field_is_none_only_for_vetoed_rows(self):
        vetoed = {
            "score": None,
            "band": None,
            "signals": {
                "attribution": True,
                "timestamp": True,
                "licence": False,
                "evidence_verified": False,
                "evidence_uncertain": False,
            },
            "vetoed": True,
            "label": "no score",
            "reason": "excluded or unmatched provenance",
        }
        scored = {
            "score": 0.6,
            "band": "medium",
            "signals": {
                "attribution": True,
                "timestamp": True,
                "licence": False,
                "evidence_verified": False,
                "evidence_uncertain": False,
            },
            "vetoed": False,
            "label": "medium",
            "reason": None,
        }

        self.assertIsNone(quality_to_response_field(vetoed))
        self.assertEqual(quality_to_response_field(scored), scored)

    def test_heuristic_weights_sum_to_one(self):
        weights = (
            benchmark_quality_service._ATTRIBUTION_WEIGHT
            + benchmark_quality_service._TIMESTAMP_WEIGHT
            + benchmark_quality_service._LICENCE_WEIGHT
            + benchmark_quality_service._EVIDENCE_WEIGHT
        )
        self.assertEqual(round(weights, 6), 1.0)


if __name__ == "__main__":
    unittest.main()
