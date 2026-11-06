"""Seed the CI dev DB (data/dev/spectra_dev.db) with enough rows to satisfy
the data-dependent script-tests (Stage 4/5/6).

Uses the real v2 schema (Base.metadata from backend.app.models) so column
structure matches what coverage_verification / calibration_verify /
workload_evidence query. This replaces the gitignored 51MB production-like
dev DB with a tiny deterministic fixture on fresh CI runners.

Minimal data contract (from the test assertions):
- coverage_verification:  >=1001 CPU rows with boost_clock_ghz IS NULL
- calibration_verify:    >=5 single-core and >=5 multi-core benchmark scores
- workload_evidence:     >=1 CPU row and >=1 GPU row
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DEV_DIR = ROOT / "data" / "dev"
DB = DEV_DIR / "spectra_dev.db"
DEV_DIR.mkdir(parents=True, exist_ok=True)
if DB.exists():
    DB.unlink()

# Ensure the dev DB path is deterministic (absolute) and NOT the default
# sqlite:///./data/spectra.db
os.environ["SPECTRA_DATABASE_URL"] = "sqlite:///" + str(DB).replace("\\", "/")

from sqlalchemy import create_engine
from backend.app.database import Base
from backend.app.models import (  # noqa: F401
    BenchmarkResult,
    BuildConversation,
    BuildMessage,
    CPUSpecification,
    GPUSpecification,
    Hardware,
    Source,
    FieldProvenance,
    ExternalIdentifier,
)

engine = create_engine(
    "sqlite:///" + str(DB).replace("\\", "/"),
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=engine)

from sqlalchemy.orm import sessionmaker

session_factory = sessionmaker(bind=engine)

with session_factory() as session:
    # 1050 CPU rows, boost_clock_ghz NULL -> missing > 1000 for that field
    N_CPU = 1050
    cpu_idxs = []
    for i in range(N_CPU):
        hw = Hardware(name=f"SeedCPU{i}", manufacturer="FixtureMFR", type="CPU")
        session.add(hw)
        session.flush()
        cpu_idxs.append(hw.id)
        session.add(CPUSpecification(
            hardware_id=hw.id, cores=8, threads=16,
            base_clock_ghz=3.0, boost_clock_ghz=None, tdp_w=65.0,
        ))

    # 1 GPU row for workload_evidence (by_type gpu must exist)
    gpu = Hardware(name="SeedGPU0", manufacturer="FixtureMFR", type="GPU")
    session.add(gpu)
    session.flush()
    session.add(GPUSpecification(
        hardware_id=gpu.id, memory_gb=8.0, memory_type="GDDR6",
        core_clock_mhz=1500.0,
    ))

    # 6 single-core + 6 multi-core benchmark scores (calibration families)
    scores_sc = [667 + i * 137 for i in range(6)]
    scores_mc = [2100 + i * 310 for i in range(6)]
    for idx, s in enumerate(scores_sc):
        session.add(BenchmarkResult(
            hardware_id=cpu_idxs[idx], benchmark_name="Geekbench 7",
            score=float(s), unit="points", test_type="single-core",
        ))
    for idx, s in enumerate(scores_mc):
        session.add(BenchmarkResult(
            hardware_id=cpu_idxs[idx], benchmark_name="Geekbench 7",
            score=float(s), unit="points", test_type="multi-core",
        ))

    # Minimal source (workload_evidence joins field_provenance)
    source = Source(name="S", url="https://s.example")
    session.add(source)
    session.flush()
    session.add(FieldProvenance(
        hardware_id=cpu_idxs[0], source_id=source.id,
        table_name="cpu_specifications", field_name="cores",
        evidenced_value="8", source_url="https://s.example",
        evidence_status="verified", batch_no=1,
    ))

    session.commit()

with session_factory() as session:
    counts = {
        t: session.query(__import__("backend.app.models", fromlist=[t]).__dict__[t]).count()
        for t in ("Hardware", "CPUSpecification", "GPUSpecification", "BenchmarkResult", "Source")
    }
print(f"SEEDED {DB} — counts: {counts}")
engine.dispose()
