"""M4 evaluation fixtures: synthetic catalog rows covering mission edges.

Deterministic, in-memory (StaticPool pattern); no production DB contact.
Rows are keyed to explicit ids so tests can assert exact rankings.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    BenchmarkResult, CPUSpecification, GPUSpecification, Hardware,
    MotherboardSpecification, PSUSpecification,
)


class EvaluationEnvironment:
    """In-memory DB mirroring the established test-env pattern."""

    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def seed_all(self):
        with self.session_factory() as s:
            self._seed_anchored_population(s)
            self._seed_outlier(s)
            self._seed_conflicting_benchmarks(s)
            self._seed_evidence_free(s)
            self._seed_incompatible_pair(s)
            self._seed_ranking_inversion_pair(s)
            self._seed_gpus(s)
            s.commit()

    def _seed_gpus(self, s):
        s.add(Hardware(
            id=300, name="GPU Strong", manufacturer="M", type="GPU",
            gpu_specification=GPUSpecification(
                memory_gb=24.0, memory_type="GDDR6X", core_clock_mhz=1800.0,
                boost_clock_mhz=2100.0, vram_bandwidth_gbps=760.0,
                memory_bus_width_bits=320, tdp_w=450.0, interface="PCIe 4.0",
            ),
        ))
        s.add(Hardware(
            id=301, name="GPU Weak", manufacturer="M", type="GPU",
            gpu_specification=GPUSpecification(
                memory_gb=6.0, memory_type="GDDR6", core_clock_mhz=1500.0,
                boost_clock_mhz=1700.0, vram_bandwidth_gbps=200.0,
                memory_bus_width_bits=96, tdp_w=75.0, interface="PCIe 3.0",
            ),
        ))

    # -- population for anchor derivation (12 CPUs) ----------------------
    def _seed_anchored_population(self, s):
        mc = [2100, 2410, 2720, 3030, 3340, 3650, 5000, 6100, 8200, 10300,
              13100, 16500]
        sc = [700, 850, 1000, 1150, 1300, 1450, 1600, 1750, 1900, 2050,
              2200, 2350]
        for i, (m, c) in enumerate(zip(mc, sc), start=1):
            s.add(Hardware(
                id=100 + i, name=f"CPU{i:02d}", manufacturer="M", type="CPU",
                cpu_specification=CPUSpecification(
                    cores=8, threads=16, base_clock_ghz=3.0,
                    boost_clock_ghz=4.4, tdp_w=65.0, socket="AM5",
                ),
                benchmark_results=[
                    BenchmarkResult(benchmark_name="Geekbench 7",
                                    score=float(m), unit="points",
                                    test_type="multi-core"),
                    BenchmarkResult(benchmark_name="Geekbench 7",
                                    score=float(c), unit="points",
                                    test_type="single-core"),
                ],
            ))

    # -- extreme outlier: 10x p90 multi-core -----------------------------
    def _seed_outlier(self, s):
        s.add(Hardware(
            id=900, name="CPU Outlier", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=8, threads=16, base_clock_ghz=3.0, boost_clock_ghz=4.4,
                tdp_w=65.0, socket="AM5",
            ),
            benchmark_results=[
                BenchmarkResult(benchmark_name="Geekbench 7", score=165000.0,
                                unit="points", test_type="multi-core"),
                BenchmarkResult(benchmark_name="Geekbench 7", score=23500.0,
                                unit="points", test_type="single-core"),
            ],
        ))

    # -- conflicting specs: two multi-core records with different scores --
    def _seed_conflicting_benchmarks(self, s):
        s.add(Hardware(
            id=901, name="CPU Conflicting", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=8, threads=16, base_clock_ghz=3.0, boost_clock_ghz=4.4,
                tdp_w=65.0, socket="AM5",
            ),
            benchmark_results=[
                BenchmarkResult(benchmark_name="Geekbench 7", score=7000.0,
                                unit="points", test_type="multi-core"),
                BenchmarkResult(benchmark_name="Geekbench 7", score=9000.0,
                                unit="points", test_type="multi-core"),
            ],
        ))

    # -- evidence-free row (gate must exclude) ---------------------------
    def _seed_evidence_free(self, s):
        s.add(Hardware(id=902, name="CPU Bare", manufacturer="M", type="CPU"))

    # -- incompatible pair: LGA1700 CPU vs AM5 board ----------------------
    def _seed_incompatible_pair(self, s):
        s.add(Hardware(
            id=910, name="CPU Intel", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=8, threads=16, base_clock_ghz=3.0, boost_clock_ghz=4.4,
                tdp_w=125.0, socket="LGA1700",
            ),
            benchmark_results=[
                BenchmarkResult(benchmark_name="Geekbench 7", score=9500.0,
                                unit="points", test_type="multi-core"),
                BenchmarkResult(benchmark_name="Geekbench 7", score=2100.0,
                                unit="points", test_type="single-core"),
            ],
        ))
        s.add(Hardware(
            id=920, name="Board AM5", manufacturer="M", type="MOTHERBOARD",
            motherboard_specification=MotherboardSpecification(
                socket="AM5", ram_type="DDR5", max_ram_gb=128, ram_slots=4,
                m2_slots=2, sata_ports=4, pcie_slots=3,
            ),
        ))

    # -- ranking inversion pair: a > b at workstation, a < b at daily -----
    def _seed_ranking_inversion_pair(self, s):
        # CPU-A: strong multi-core, modest single-core
        s.add(Hardware(
            id=930, name="CPU Multi", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=16, threads=32, base_clock_ghz=2.5, boost_clock_ghz=4.0,
                tdp_w=170.0, socket="AM5",
            ),
            benchmark_results=[
                BenchmarkResult(benchmark_name="Geekbench 7", score=14000.0,
                                unit="points", test_type="multi-core"),
                BenchmarkResult(benchmark_name="Geekbench 7", score=1200.0,
                                unit="points", test_type="single-core"),
            ],
        ))
        # CPU-B: modest multi-core, strong single-core
        s.add(Hardware(
            id=931, name="CPU Single", manufacturer="M", type="CPU",
            cpu_specification=CPUSpecification(
                cores=4, threads=8, base_clock_ghz=3.8, boost_clock_ghz=5.0,
                tdp_w=65.0, socket="AM5",
            ),
            benchmark_results=[
                BenchmarkResult(benchmark_name="Geekbench 7", score=6200.0,
                                unit="points", test_type="multi-core"),
                BenchmarkResult(benchmark_name="Geekbench 7", score=2300.0,
                                unit="points", test_type="single-core"),
            ],
        ))

    # -- partial build context (CPU only) --------------------------------
    def partial_build(self):
        return {"cpu": 101}


def anchors_from_env(env):
    """Derive anchors from the seeded CPU population (deterministic)."""
    from backend.app.services.scenario_scoring import derive_anchors

    with env.session_factory() as s:
        rows = s.query(Hardware).filter(Hardware.type == "CPU").all()
        mc = sorted(
            b.score for r in rows for b in r.benchmark_results
            if b.test_type == "multi-core"
        )
        sc = sorted(
            b.score for r in rows for b in r.benchmark_results
            if b.test_type == "single-core"
        )
    return {
        "multi-core": derive_anchors(mc),
        "single-core": derive_anchors(sc),
    }
