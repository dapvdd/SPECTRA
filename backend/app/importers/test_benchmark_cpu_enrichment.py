import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.importers.benchmark_cpu_enrichment import (
    apply_enrichment_plan,
    build_enrichment_plan,
    enrich_catalog_cpus,
)
from backend.app.models import CPUSpecification, Hardware, Source


class BenchmarkCpuEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _write_csv(self, fieldnames, rows):
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

    def _paths(self, catalog_rows, geekbench_name="AMD Ryzen 3 2200G"):
        catalog = self._write_csv(
            [
                "CpuName",
                "Socket",
                "ClockSpeed",
                "TurboSpeed",
                "Cores",
                "Threads",
                "TDP",
                "ReleaseDate",
                "SourceUrl",
            ],
            catalog_rows,
        )
        geekbench = self._write_csv(
            [
                "devices/id",
                "devices/name",
                "devices/description",
                "devices/samples",
                "devices/score",
                "devices/multicore_score",
                "devices/icon",
                "devices/family",
            ],
            [
                {
                    "devices/id": "1",
                    "devices/name": geekbench_name,
                    "devices/description": "4 cores",
                    "devices/samples": "1",
                    "devices/score": "100",
                    "devices/multicore_score": "200",
                    "devices/icon": "amd",
                    "devices/family": "Test",
                }
            ],
        )
        return geekbench, catalog

    def _catalog_row(self, name="AMD Ryzen 3 2200G", source_url="https://example.test/cpu"):
        return {
            "CpuName": name,
            "Socket": "AM4",
            "ClockSpeed": "3.5 GHz",
            "TurboSpeed": "3.7 GHz",
            "Cores": "4",
            "Threads": "4",
            "TDP": "65 W",
            "ReleaseDate": "Q1 2018",
            "SourceUrl": source_url,
        }

    def test_valid_catalog_row_inserts_hardware_and_specification(self):
        geekbench, catalog = self._paths([self._catalog_row()])

        with self.session_factory() as session:
            summary = enrich_catalog_cpus(geekbench, catalog, session)
            hardware = session.scalar(
                select(Hardware).where(Hardware.name == "AMD Ryzen 3 2200G")
            )

            self.assertEqual(summary.inserted, 1)
            self.assertEqual(summary.errors, 0)
            self.assertEqual(hardware.manufacturer, "AMD")
            self.assertEqual(hardware.cpu_specification.cores, 4)
            self.assertEqual(hardware.cpu_specification.threads, 4)
            self.assertEqual(hardware.cpu_specification.base_clock_ghz, 3.5)
            self.assertEqual(hardware.cpu_specification.boost_clock_ghz, 3.7)
            self.assertEqual(hardware.cpu_specification.tdp_w, 65)
            self.assertEqual(hardware.cpu_specification.socket, "AM4")
            self.assertIsNone(hardware.release_date)
            self.assertEqual(session.scalar(select(Source)).name, "PassMark CPU benchmark catalog (benchmark-cpus.csv)")

    def test_rerun_does_not_create_duplicates(self):
        geekbench, catalog = self._paths([self._catalog_row()])

        with self.session_factory() as session:
            first = enrich_catalog_cpus(geekbench, catalog, session)
            second = enrich_catalog_cpus(geekbench, catalog, session)

            self.assertEqual(first.inserted, 1)
            self.assertEqual(second.candidates, 0)
            self.assertEqual(second.inserted, 0)
            self.assertEqual(second.errors, 0)
            self.assertEqual(
                len(session.scalars(select(Hardware)).all()),
                1,
            )
            self.assertEqual(
                len(session.scalars(select(CPUSpecification)).all()),
                1,
            )

    def test_existing_hardware_is_not_changed(self):
        geekbench, catalog = self._paths([self._catalog_row()])

        with self.session_factory() as session:
            existing = Hardware(
                name="AMD Ryzen 3 2200G",
                manufacturer="AMD",
                type="CPU",
            )
            existing.cpu_specification = CPUSpecification(
                cores=99,
                threads=99,
            )
            session.add(existing)
            session.commit()

            summary = enrich_catalog_cpus(geekbench, catalog, session)
            unchanged = session.scalar(select(Hardware))

            self.assertEqual(summary.inserted, 0)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(unchanged.cpu_specification.cores, 99)
            self.assertEqual(unchanged.cpu_specification.threads, 99)

    def test_invalid_catalog_row_is_not_imported(self):
        geekbench, catalog = self._paths(
            [self._catalog_row(source_url="")]
        )

        with self.session_factory() as session:
            plan = build_enrichment_plan(geekbench, catalog, session)
            summary = apply_enrichment_plan(plan, session)

            self.assertEqual(len(plan.errors), 1)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(summary.errors, 1)
            self.assertIsNone(session.scalar(select(Hardware)))
            self.assertIsNone(session.scalar(select(Source)))

    def test_ambiguous_catalog_candidate_is_not_imported(self):
        geekbench, catalog = self._paths(
            [
                self._catalog_row(),
                self._catalog_row(
                    name="[Dual CPU] AMD Ryzen 3 2200G",
                    source_url="https://example.test/cpu?dual=2",
                ),
            ]
        )

        with self.session_factory() as session:
            plan = build_enrichment_plan(geekbench, catalog, session)
            summary = apply_enrichment_plan(plan, session)

            self.assertEqual(len(plan.candidates), 0)
            self.assertEqual(len(plan.errors), 0)
            self.assertEqual(summary.inserted, 0)
            self.assertIsNone(session.scalar(select(Hardware)))
            self.assertIsNone(session.scalar(select(Source)))


if __name__ == "__main__":
    unittest.main()
