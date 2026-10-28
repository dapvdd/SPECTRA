"""Data quality audit: counts VALIDATED records (provenance-backed or evidence-backed),
not just row counts. Run against a local copy of the SPECTRA database."""
from sqlalchemy import select, func

from backend.app.database import SessionLocal
from backend.app.models import Hardware
from backend.app.models.cpu import CPUSpecification
from backend.app.models.gpu import GPUSpecification
from backend.app.models.benchmark import BenchmarkResult
from backend.app.models.external_identifier import ExternalIdentifier
from backend.app.models.provenance import FieldProvenance

s = SessionLocal()


def count(m):
    return s.scalar(select(func.count()).select_from(m))


hardware = count(Hardware)
cpu_specs = count(CPUSpecification)
gpu_specs = count(GPUSpecification)
benchmarks = count(BenchmarkResult)
ext_ids = count(ExternalIdentifier)
prov = count(FieldProvenance)

print(f"hardware={hardware} cpu_specs={cpu_specs} gpu_specs={gpu_specs} "
      f"benchmarks={benchmarks} ext_ids={ext_ids} provenance={prov}")

# Hardware classified by type
print("\n-- hardware by type --")
for t, n in s.execute(select(Hardware.type, func.count()).group_by(Hardware.type)).all():
    print(f"  {t}: {n}")

# CPU: how many have a COMPLETE spec row (all 7 fields present)?
print("\n-- CPU completeness (all core fields present) --")
for col in ["cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w", "process_node_nm", "socket"]:
    n = s.scalar(select(func.count()).where(getattr(CPUSpecification, col).is_(None)))
    print(f"  missing {col}: {n}")

# GPU completeness
print("\n-- GPU completeness --")
for col in ["memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
            "vram_bandwidth_gbps", "memory_bus_width_bits", "tdp_w", "interface", "length_mm"]:
    n = s.scalar(select(func.count()).where(getattr(GPUSpecification, col).is_(None)))
    print(f"  missing {col}: {n}")

# How many hardware rows have provenance at all?
print("\n-- provenance coverage --")
prov_hw = s.scalar(select(func.count(func.distinct(FieldProvenance.hardware_id))))
bench_prov = s.scalar(select(func.count(func.distinct(FieldProvenance.benchmark_result_id)))
                     .where(FieldProvenance.benchmark_result_id.isnot(None)))
print(f"  hardware with any provenance: {prov_hw} / {hardware}")
print(f"  benchmark results with provenance: {bench_prov} / {benchmarks}")

# Provenance status distribution per table
print("\n-- provenance per table/status --")
for t, st, n in s.execute(
    select(FieldProvenance.table_name, FieldProvenance.evidence_status, func.count())
    .group_by(FieldProvenance.table_name, FieldProvenance.evidence_status)
).all():
    print(f"  {t} / {st}: {n}")

# confidence distribution
print("\n-- provenance confidence --")
for c, n in s.execute(
    select(FieldProvenance.confidence, func.count()).group_by(FieldProvenance.confidence)
).all():
    print(f"  {c}: {n}")

# Benchmarks: which hardware types, and hardware coverage
print("\n-- benchmark coverage --")
covered = s.scalar(select(func.count(func.distinct(BenchmarkResult.hardware_id))))
print(f"  hardware with >=1 benchmark: {covered} / {hardware}")
bench_by_type = s.execute(
    select(Hardware.type, func.count(func.distinct(BenchmarkResult.hardware_id)))
    .join(BenchmarkResult, BenchmarkResult.hardware_id == Hardware.id)
    .group_by(Hardware.type)
).all()
print(f"  by type: {[(t, n) for t, n in bench_by_type]}")
for bn, n in s.execute(
    select(BenchmarkResult.benchmark_name, func.count())
    .group_by(BenchmarkResult.benchmark_name)
).all():
    print(f"  benchmark {bn}: {n}")

# Sources
print("\n-- sources --")
from backend.app.models.source import Source
for row in s.execute(select(Source.id, Source.name, Source.license_status, Source.retrieved_on, Source.url)).all():
    print(f"  #{row[0]} {row[1]} | license={row[2]} | retrieved={row[3]}")

# external identifiers
print("\n-- external identifiers by type --")
for t, n in s.execute(
    select(ExternalIdentifier.identifier_type, func.count()).group_by(ExternalIdentifier.identifier_type)
).all():
    print(f"  {t}: {n}")

s.close()
