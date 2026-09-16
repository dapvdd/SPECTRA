import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.importers.geekbench_score_importer import (
    BENCHMARK_NAME,
    GEEKBENCH_SOURCE_NAME,
    MULTI_CORE_TEST_TYPE,
    SINGLE_CORE_TEST_TYPE,
    apply_score_import_plan,
    build_score_import_plan,
    import_geekbench_scores,
)
from backend.app.models import BenchmarkResult, Hardware, Source


class GeekbenchScoreImporterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

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
        self.engine.dispose()

    def _write_csv(self, rows):
        fieldnames = [
            "devices/id",
            "devices/name",
            "devices/description",
            "devices/samples",
            "devices/score",
            "devices/multicore_score",
            "devices/icon",
            "devices/family",
        ]
        file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        )
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        file.close()
        path = Path(file.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def _row(
        self,
        name="AMD Ryzen 5 5600 Processor",
        score="1234",
        multi_score="5678",
        samples="10",
    ):
        return {
            "devices/id": "1",
            "devices/name": name,
            "devices/description": "6 cores",
            "devices/samples": samples,
            "devices/score": score,
            "devices/multicore_score": multi_score,
            "devices/icon": "amd",
            "devices/family": "Test",
        }

    def test_valid_matched_cpu_inserts_single_and_multi_results(self):
        path = self._write_csv([self._row()])

        with self.session_factory() as session:
            summary = import_geekbench_scores(path, session)
            results = session.scalars(select(BenchmarkResult)).all()
            source = session.scalar(select(Source))

            self.assertEqual(summary.planned, 2)
            self.assertEqual(summary.inserted, 2)
            self.assertEqual(len(results), 2)
            self.assertEqual({result.test_type for result in results}, {
                SINGLE_CORE_TEST_TYPE,
                MULTI_CORE_TEST_TYPE,
            })
            self.assertEqual({result.benchmark_name for result in results}, {BENCHMARK_NAME})
            self.assertEqual({result.unit for result in results}, {"points"})
            self.assertTrue(all(result.recorded_at is None for result in results))
            self.assertEqual(source.name, GEEKBENCH_SOURCE_NAME)

    def test_unmatched_cpu_is_skipped(self):
        path = self._write_csv([self._row(name="AMD Ryzen 9 9999X")])

        with self.session_factory() as session:
            summary = import_geekbench_scores(path, session)

            self.assertEqual(summary.unmatched, 1)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(session.scalar(select(BenchmarkResult.id)), None)
            self.assertEqual(session.scalar(select(Source.id)), None)

    def test_ambiguous_cpu_is_skipped(self):
        with self.session_factory() as session:
            session.add(
                Hardware(
                    name="AMD Ryzen 5 5600 Processor",
                    manufacturer="AMD",
                    type="CPU",
                )
            )
            session.commit()

        path = self._write_csv([self._row()])

        with self.session_factory() as session:
            summary = import_geekbench_scores(path, session)

            self.assertEqual(summary.ambiguous, 1)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(session.scalar(select(BenchmarkResult.id)), None)
            self.assertEqual(session.scalar(select(Source.id)), None)

    def test_invalid_zero_and_nonfinite_scores_are_skipped(self):
        path = self._write_csv([
            self._row(score="0", multi_score="nan"),
        ])

        with self.session_factory() as session:
            summary = import_geekbench_scores(path, session)

            self.assertEqual(summary.invalid, 1)
            self.assertEqual(summary.invalid_score_fields, 2)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(session.scalar(select(BenchmarkResult.id)), None)
            self.assertEqual(session.scalar(select(Source.id)), None)

    def test_duplicate_source_rows_do_not_create_duplicate_logical_results(self):
        path = self._write_csv([self._row(), self._row()])

        with self.session_factory() as session:
            plan = build_score_import_plan(path, session)
            summary = apply_score_import_plan(plan, session)

            self.assertEqual(plan.duplicate_source_rows, 1)
            self.assertEqual(plan.duplicate_logical_scores, 2)
            self.assertEqual(len(plan.scores), 2)
            self.assertEqual(summary.inserted, 2)
            self.assertEqual(len(session.scalars(select(BenchmarkResult)).all()), 2)

    def test_rerun_is_idempotent(self):
        path = self._write_csv([self._row()])

        with self.session_factory() as session:
            first = import_geekbench_scores(path, session)
            second = import_geekbench_scores(path, session)

            self.assertEqual(first.inserted, 2)
            self.assertEqual(second.planned, 0)
            self.assertEqual(second.inserted, 0)
            self.assertEqual(second.skipped, 2)
            self.assertEqual(
                len(session.scalars(select(Source)).all()),
                1,
            )
            self.assertEqual(
                len(session.scalars(select(BenchmarkResult)).all()),
                2,
            )

    def test_existing_benchmark_results_are_not_modified(self):
        path = self._write_csv([self._row()])

        with self.session_factory() as session:
            source = Source(
                name="Geekbench Browser - Geekbench 7 CPU",
                url="https://browser.geekbench.com/",
            )
            session.add(source)
            session.flush()
            hardware = session.scalar(select(Hardware))
            session.add(
                BenchmarkResult(
                    hardware_id=hardware.id,
                    benchmark_name=BENCHMARK_NAME,
                    score=1234,
                    unit="points",
                    test_type=SINGLE_CORE_TEST_TYPE,
                    source_id=source.id,
                    recorded_at=None,
                )
            )
            session.commit()

            summary = import_geekbench_scores(path, session)
            results = session.scalars(select(BenchmarkResult)).all()

            self.assertEqual(summary.inserted, 1)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual(len(results), 2)
            self.assertEqual(
                next(result.score for result in results if result.test_type == SINGLE_CORE_TEST_TYPE),
                1234,
            )

    def test_transaction_rolls_back_on_database_failure(self):
        path = self._write_csv([self._row()])

        def fail_before_flush(session, flush_context, instances):
            raise RuntimeError("forced database failure")

        with self.session_factory() as session:
            plan = build_score_import_plan(path, session)
            event.listen(self.session_factory.class_, "before_flush", fail_before_flush)
            self.addCleanup(
                lambda: event.remove(
                    self.session_factory.class_,
                    "before_flush",
                    fail_before_flush,
                )
            )

            with self.assertRaises(RuntimeError):
                apply_score_import_plan(plan, session)

            self.assertEqual(session.scalar(select(BenchmarkResult.id)), None)
            self.assertEqual(session.scalar(select(Source.id)), None)


if __name__ == "__main__":
    unittest.main()
