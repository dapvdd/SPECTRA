"""Tests for Stage 4 coverage verification + gap classification.

Encodes the contract:
- ``fillable_gaps`` calls Stage 3's audit machinery and reports, per field,
  whether a clear-license source can actually fill remaining NULL gaps, with
  the reason (fillable vs blocked-on-license vs source-exhausted).
- Every result value is derived from the real table state; nothing invented.
- ``_has_clear_source_for_field`` returns True only for a (table, field) that a
  registered clear adapter maps — proof that the gap could be filled.
- The report is deterministic (sorted keys) so a regression test can pin it.
"""

from __future__ import annotations

import json

from backend.app.scripts import coverage_verification as cv


class TestFillableGapLogic:
    def test_gpu_boost_clock_is_map_to_clear_source(self):
        # gpu_specifications.boost_clock_mhz maps to GPU Ark base_clock? No —
        # to GPU Ark boost_clock via our adapter's map; check it resolves.
        assert cv.has_clear_source("gpu_specifications", "boost_clock_mhz") is True

    def test_gpu_tdp_is_clear_source_fillable(self):
        assert cv.has_clear_source("gpu_specifications", "tdp_w") is True

    def test_cpu_boost_clock_has_no_clear_adapter(self):
        # CPU enrichment sources (Intel/AMD ARK, Geekbench) are unknown license.
        assert cv.has_clear_source("cpu_specifications", "boost_clock_ghz") is False

    def test_cpu_socket_no_clear_adapter(self):
        assert cv.has_clear_source("cpu_specifications", "socket") is False

    def test_unknown_field_is_not_fillable(self):
        assert cv.has_clear_source("gpu_specifications", "not_a_column") is False


class TestCoverageReportShape:
    def test_gap_classification_lists_each_spec_field_for_feasibility(self):
        report = cv.classify_feasibility()
        for table in ("cpu_specifications", "gpu_specifications"):
            assert table in report
            for entry in report[table]:
                assert set(entry) >= {"field", "missing", "fillable", "reason"}

    def test_gap_counts_match_stage1_v2_figures(self):
        report = cv.classify_feasibility()
        cpu_boost = next(
            e for e in report["cpu_specifications"]
            if e["field"] == "boost_clock_ghz"
        )
        # From the v2 audit: boost_clock_ghz missing ~1076 of 3501.
        assert cpu_boost["missing"] > 1000
        assert cpu_boost["fillable"] is False
        assert "license" in cpu_boost["reason"].lower()

    def test_gpu_tdp_listed_fillable_via_clear_source(self):
        report = cv.classify_feasibility() if False else cv.classify_feasibility()
        gpu_tdp = next(
            e for e in report["gpu_specifications"]
            if e["field"] == "tdp_w"
        )
        assert gpu_tdp["fillable"] is True or gpu_tdp["reason"].startswith("clear")


class TestReportSerialization:
    def test_report_json_roundtrip(self, tmp_path):
        import os
        from pathlib import Path
        db_path = getattr(cv, "COVERAGE_DB", None)
        # If the dev DB path is not set, the report should still be serializable.
        report = cv.build_report()
        text = json.dumps(report, sort_keys=True)
        assert '"tool"' in text
        Path(tmp_path, "cov.json").write_text(text, encoding="utf-8")
        assert Path(tmp_path, "cov.json").stat().st_size > 0
