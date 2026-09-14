import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.importers import benchmark_importer
from backend.app.models import BenchmarkResult, Hardware, Source


class BenchmarkImporterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.original_session_local = benchmark_importer.SessionLocal
        benchmark_importer.SessionLocal = self.session_factory

        with self.session_factory() as session:
            session.add(
                Hardware(
                    name="AMD Ryzen 5 5600",
                    manufacturer="AMD",
                    type="CPU",
                )
            )
            session.commit()

    def tearDown(self):
        benchmark_importer.SessionLocal = self.original_session_local
        self.engine.dispose()

    def _write_csv(self, rows, fieldnames=None):
        fieldnames = fieldnames or [
            "CpuName",
            "BenchmarkName",
            "Score",
            "Unit",
            "TestType",
        ]
        file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        )
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)
        file.close()
        self.addCleanup(lambda: Path(file.name).unlink(missing_ok=True))
        return file.name

    def test_catalog_schema_is_rejected_without_writing(self):
        path = self._write_csv(
            [
                {
                    "CpuName": "Ryzen 5 5600",
                    "Socket": "AM4",
                    "ClockSpeed": "3.5 GHz",
                    "Cores": "6",
                }
            ],
            fieldnames=["CpuName", "Socket", "ClockSpeed", "Cores"],
        )

        with self.assertRaises(benchmark_importer.BenchmarkImportError):
            benchmark_importer.import_benchmark_scores(
                path,
                "Test scores",
                "https://example.com/scores",
            )

        with self.session_factory() as session:
            self.assertEqual(session.scalar(select(BenchmarkResult.id)), None)
            self.assertEqual(session.scalar(select(Source.id)), None)

    def test_import_is_idempotent_and_preserves_source(self):
        path = self._write_csv(
            [
                {
                    "CpuName": "AMD Ryzen 5 5600 Processor",
                    "BenchmarkName": "Example Bench",
                    "Score": "1234.5",
                    "Unit": "points",
                    "TestType": "multi-core",
                }
            ]
        )
        args = (
            path,
            "Example benchmark dataset",
            "https://example.com/scores",
        )

        first = benchmark_importer.import_benchmark_scores(*args)
        second = benchmark_importer.import_benchmark_scores(*args)

        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["skipped"], 1)

        with self.session_factory() as session:
            result = session.scalar(select(BenchmarkResult))
            source = session.scalar(select(Source))
            self.assertEqual(result.score, 1234.5)
            self.assertEqual(result.source_id, source.id)
            self.assertEqual(source.name, "Example benchmark dataset")

    def test_unmatched_and_ambiguous_rows_are_not_inserted(self):
        with self.session_factory() as session:
            session.add(
                Hardware(
                    name="AMD Ryzen 5 5600 Processor",
                    manufacturer="AMD",
                    type="CPU",
                )
            )
            session.commit()

        path = self._write_csv(
            [
                {
                    "CpuName": "AMD Ryzen 5 5600 Processor",
                    "BenchmarkName": "Example Bench",
                    "Score": "100",
                    "Unit": "points",
                    "TestType": "multi-core",
                },
                {
                    "CpuName": "AMD Ryzen 9 7950X",
                    "BenchmarkName": "Example Bench",
                    "Score": "200",
                    "Unit": "points",
                    "TestType": "multi-core",
                },
            ]
        )

        summary = benchmark_importer.import_benchmark_scores(
            path,
            "Example benchmark dataset",
            "https://example.com/scores",
        )

        self.assertEqual(summary["imported"], 0)
        self.assertEqual(summary["ambiguous"], 1)
        self.assertEqual(summary["unmatched"], 1)

        with self.session_factory() as session:
            self.assertIsNone(session.scalar(select(BenchmarkResult.id)))

    def test_invalid_score_is_skipped(self):
        path = self._write_csv(
            [
                {
                    "CpuName": "AMD Ryzen 5 5600",
                    "BenchmarkName": "Example Bench",
                    "Score": "not-a-score",
                    "Unit": "points",
                    "TestType": "multi-core",
                }
            ]
        )

        summary = benchmark_importer.import_benchmark_scores(
            path,
            "Example benchmark dataset",
            "https://example.com/scores",
        )

        self.assertEqual(summary["invalid"], 1)
        self.assertEqual(summary["imported"], 0)

        with self.session_factory() as session:
            self.assertIsNone(session.scalar(select(BenchmarkResult.id)))


if __name__ == "__main__":
    unittest.main()
