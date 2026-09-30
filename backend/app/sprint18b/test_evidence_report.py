import unittest

from backend.app.sprint18b.evidence_report import (
    format_report,
    generate_evidence_report,
)


class GenerateEvidenceReportTests(unittest.TestCase):
    def test_report_has_summary(self):
        report = generate_evidence_report()
        self.assertIn("summary", report)
        summary = report["summary"]
        self.assertEqual(summary["total"], 20)
        self.assertEqual(summary["cpus"], 10)
        self.assertEqual(summary["gpus"], 10)

    def test_report_has_classifications(self):
        report = generate_evidence_report()
        self.assertIn("classifications", report["summary"])
        classifications = report["summary"]["classifications"]
        self.assertIn("MATCH", classifications)

    def test_report_has_results(self):
        report = generate_evidence_report()
        self.assertIn("results", report)
        self.assertEqual(len(report["results"]), 20)

    def test_report_has_generated_at(self):
        report = generate_evidence_report()
        self.assertIn("generated_at", report)
        self.assertIsNotNone(report["generated_at"])

    def test_all_results_have_required_fields(self):
        report = generate_evidence_report()
        for result in report["results"]:
            self.assertIn("name", result)
            self.assertIn("manufacturer", result)
            self.assertIn("type", result)
            self.assertIn("classification", result)
            self.assertIn("reasons", result)


class FormatReportTests(unittest.TestCase):
    def test_format_produces_string(self):
        report = generate_evidence_report()
        formatted = format_report(report)
        self.assertIsInstance(formatted, str)
        self.assertIn("Sprint 18B Evidence Report", formatted)

    def test_format_includes_summary(self):
        report = generate_evidence_report()
        formatted = format_report(report)
        self.assertIn("Total items: 20", formatted)
        self.assertIn("CPUs: 10", formatted)
        self.assertIn("GPUs: 10", formatted)

    def test_format_includes_classifications(self):
        report = generate_evidence_report()
        formatted = format_report(report)
        self.assertIn("MATCH", formatted)

    def test_format_includes_details(self):
        report = generate_evidence_report()
        formatted = format_report(report)
        self.assertIn("Details:", formatted)


if __name__ == "__main__":
    unittest.main()
