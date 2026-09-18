import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.importers.benchmark_cpu_enrichment_v2 import (
    apply_enrichment_plan,
    build_enrichment_plan,
    enrich_catalog_cpus_v2,
)
from backend.app.models import CPUSpecification, Hardware, Source


class BenchmarkCpuEnrichmentV2Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _write_catalog(self, rows):
        file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        )
        fields = [
            "CpuName", "Socket", "ClockSpeed", "TurboSpeed", "Cores",
            "Threads", "TDP", "ReleaseDate", "SourceUrl",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        file.close()
        path = Path(file.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def _row(self, name="AMD Ryzen 5 5600", socket="AM4", threads="12"):
        return {
            "CpuName": name,
            "Socket": socket,
            "ClockSpeed": "3.5 GHz",
            "TurboSpeed": "4.4 GHz",
            "Cores": "6",
            "Threads": threads,
            "TDP": "65 W",
            "ReleaseDate": "Q4 2020",
            "SourceUrl": "https://example.test/cpu",
        }

    def _add_cpu(self, name="AMD Ryzen 5 5600", socket=None, threads=None):
        hardware = Hardware(name=name, manufacturer="AMD", type="CPU")
        hardware.cpu_specification = CPUSpecification(socket=socket, threads=threads)
        with self.session_factory() as session:
            session.add(hardware)
            session.commit()

    def test_exact_matched_socket_null_is_updated(self):
        self._add_cpu()
        path = self._write_catalog([self._row(socket=" AM4 ", threads="")])
        with self.session_factory() as session:
            summary = enrich_catalog_cpus_v2(path, session)
            spec = session.scalar(select(CPUSpecification))
            self.assertEqual(summary.planned_updates, 1)
            self.assertEqual(summary.socket_updates, 1)
            self.assertEqual(spec.socket, "AM4")

    def test_exact_matched_threads_null_is_updated(self):
        self._add_cpu()
        path = self._write_catalog([self._row(socket="", threads="12")])
        with self.session_factory() as session:
            summary = enrich_catalog_cpus_v2(path, session)
            spec = session.scalar(select(CPUSpecification))
            self.assertEqual(summary.threads_updates, 1)
            self.assertEqual(spec.threads, 12)

    def test_existing_values_are_not_overwritten(self):
        self._add_cpu(socket="existing", threads=8)
        path = self._write_catalog([self._row(socket="source", threads="12")])
        with self.session_factory() as session:
            summary = enrich_catalog_cpus_v2(path, session)
            spec = session.scalar(select(CPUSpecification))
            self.assertEqual(summary.planned_updates, 0)
            self.assertEqual((spec.socket, spec.threads), ("existing", 8))

    def test_unmatched_and_ambiguous_are_skipped(self):
        self._add_cpu()
        self._add_cpu(name="AMD Ryzen 5 5600 Processor")
        path = self._write_catalog([self._row()])
        with self.session_factory() as session:
            summary = enrich_catalog_cpus_v2(path, session)
            self.assertEqual(summary.planned_updates, 0)
            self.assertEqual(summary.ambiguous_rows, 2)

        path = self._write_catalog([self._row(name="AMD Missing 9999")])
        with self.session_factory() as session:
            summary = enrich_catalog_cpus_v2(path, session)
            self.assertEqual(summary.unmatched_rows, 2)
            self.assertEqual(summary.actual_updates, 0)

    def test_empty_and_invalid_source_values_are_skipped(self):
        self._add_cpu()
        path = self._write_catalog([self._row(socket="", threads="not-an-int")])
        with self.session_factory() as session:
            plan = build_enrichment_plan(path, session)
            self.assertEqual(len(plan.updates), 0)
            self.assertEqual(plan.invalid_rows, 1)

    def test_socket_is_preserved_without_aggressive_rewriting(self):
        self._add_cpu()
        path = self._write_catalog([self._row(socket="LGA 1700 / custom")])
        with self.session_factory() as session:
            enrich_catalog_cpus_v2(path, session)
            spec = session.scalar(select(CPUSpecification))
            self.assertEqual(spec.socket, "LGA 1700 / custom")

    def test_idempotency_and_source_reuse(self):
        self._add_cpu()
        path = self._write_catalog([self._row()])
        with self.session_factory() as session:
            first = enrich_catalog_cpus_v2(path, session)
            second = enrich_catalog_cpus_v2(path, session)
            self.assertEqual(first.actual_updates, 2)
            self.assertEqual(second.planned_updates, 0)
            self.assertEqual(second.actual_updates, 0)
            self.assertEqual(len(session.scalars(select(Source)).all()), 1)

    def test_rollback_leaves_database_unchanged(self):
        self._add_cpu()
        path = self._write_catalog([self._row()])
        with self.session_factory() as session:
            plan = build_enrichment_plan(path, session)

            def fail_before_flush(session, flush_context, instances):
                raise RuntimeError("forced database failure")

            event.listen(self.session_factory.class_, "before_flush", fail_before_flush)
            self.addCleanup(
                lambda: event.remove(
                    self.session_factory.class_, "before_flush", fail_before_flush
                )
            )
            with self.assertRaises(RuntimeError):
                apply_enrichment_plan(plan, session)
            spec = session.scalar(select(CPUSpecification))
            self.assertEqual((spec.socket, spec.threads), (None, None))
            self.assertIsNone(session.scalar(select(Source)))


if __name__ == "__main__":
    unittest.main()
