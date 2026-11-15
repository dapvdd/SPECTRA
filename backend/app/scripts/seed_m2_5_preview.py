"""Disposable M2.5 preview DB: fresh schema + six-slot fixtures.

Never touches production or the M2 staging database. Writes only to the
temp preview path below. Run from the repository root (or a worktree root)
with PYTHONPATH including that root; the DB is rebuilt at the fixed temp
path so the capture script and the seeded DB always agree.

Fixture builds:
  A  full, every determinable rule compatible-except-known (aggregate
     UNKNOWN: the GPU-slot rule has no stored PCIe-generation data and the
     PSU at/above the TDP reference is advisory-UNKNOWN).
  B  incompatible (CPU socket, RAM generation, PSU wattage shortfall).
  C  unknown-heavy (missing socket / TDP / slot data -> UNKNOWN + Missing).
"""

import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(
    r"C:\Users\user\AppData\Local\Temp\opencode\m2-5-preview\m2_5_preview.db"
)
DB_URL = "sqlite:///" + DB_PATH.as_posix()

os.environ["SPECTRA_DATABASE_URL"] = DB_URL

for stale in (DB_PATH, DB_PATH.with_suffix(".db-wal"), DB_PATH.with_suffix(".db-shm")):
    if stale.exists():
        stale.unlink()

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

from backend.app.database import Base, engine  # noqa: E402
from backend.app.models import (  # noqa: E402
    CPUSpecification,
    GPUSpecification,
    Hardware,
    MotherboardSpecification,
    PSUSpecification,
    RAMSpecification,
    Source,
    StorageSpecification,
)
from backend.app.database import SessionLocal  # noqa: E402

Base.metadata.create_all(bind=engine)


def hw(name, manufacturer, htype, **spec):
    item = Hardware(
        name=name,
        manufacturer=manufacturer,
        type=htype,
        release_date=date(2023, 1, 1),
    )
    if htype == "CPU":
        item.cpu_specification = CPUSpecification(**spec)
    elif htype == "GPU":
        item.gpu_specification = GPUSpecification(**spec)
    elif htype == "RAM":
        item.ram_specification = RAMSpecification(**spec)
    elif htype == "STORAGE":
        item.storage_specification = StorageSpecification(**spec)
    elif htype == "MOTHERBOARD":
        item.motherboard_specification = MotherboardSpecification(**spec)
    elif htype == "PSU":
        item.psu_specification = PSUSpecification(**spec)
    return item


BUILD_A = [
    hw("PREVIEW M25 Core i5-14600K", "Intel", "CPU",
       cores=14, threads=20, base_clock_ghz=3.5, boost_clock_ghz=5.3,
       tdp_w=125, process_node_nm=10, socket="FCLGA1700"),
    hw("PREVIEW M25 RTX 4070", "NVIDIA", "GPU",
       memory_gb=12, memory_type="GDDR6X", core_clock_mhz=1920,
       boost_clock_mhz=2475, vram_bandwidth_gbps=504,
       memory_bus_width_bits=192, tdp_w=200,
       interface="PCIe 4.0 x16", length_mm=244),
    hw("PREVIEW M25 Vengeance DDR5 32GB", "Corsair", "RAM",
       ddr_generation="DDR5", capacity_gb=32, speed_mhz=5600,
       modules=2, form_factor="DIMM"),
    hw("PREVIEW M25 980 Pro 1TB", "Samsung", "STORAGE",
       storage_type="NVMe", capacity_gb=1024, interface="PCIe 4.0 x4",
       form_factor="M.2 2280"),
    hw("PREVIEW M25 Pro Z690-A", "ASUS", "MOTHERBOARD",
       socket="FCLGA1700", chipset="Z690", form_factor="ATX",
       ram_type="DDR5", ram_slots=4, max_ram_gb=128,
       m2_slots=3, sata_ports=4, pcie_slots=2),
    hw("PREVIEW M25 RM850x", "Corsair", "PSU",
       wattage=850, efficiency_rating="80 Plus Gold", modular=True,
       pcie_8pin_count=4, pcie_12vhpwr=0),
]

BUILD_B = [
    hw("PREVIEW M25 Ryzen 7 5800X", "AMD", "CPU",
       cores=8, threads=16, base_clock_ghz=3.8, boost_clock_ghz=4.7,
       tdp_w=105, process_node_nm=7, socket="AM4"),
    hw("PREVIEW M25 RX 7900 XTX", "AMD", "GPU",
       memory_gb=24, memory_type="GDDR6", core_clock_mhz=1900,
       boost_clock_mhz=2500, vram_bandwidth_gbps=960,
       memory_bus_width_bits=384, tdp_w=355,
       interface="PCIe 4.0 x16", length_mm=287),
    hw("PREVIEW M25 Vengeance LPX DDR4 16GB", "Corsair", "RAM",
       ddr_generation="DDR4", capacity_gb=16, speed_mhz=3200,
       modules=2, form_factor="DIMM"),
    hw("PREVIEW M25 Barracuda 2TB HDD", "Seagate", "STORAGE",
       storage_type="HDD", capacity_gb=2000, interface="SATA 6Gb/s",
       form_factor="3.5in"),
    hw("PREVIEW M25 Pro Z690-A (B)", "ASUS", "MOTHERBOARD",
       socket="FCLGA1700", chipset="Z690", form_factor="ATX",
       ram_type="DDR5", ram_slots=4, max_ram_gb=128,
       m2_slots=3, sata_ports=4, pcie_slots=2),
    hw("PREVIEW M25 CV450", "Corsair", "PSU",
       wattage=450, efficiency_rating="80 Plus Bronze", modular=False,
       pcie_8pin_count=2, pcie_12vhpwr=0),
]

BUILD_C = [
    hw("PREVIEW M25 Core i9-13900K partial", "Intel", "CPU",
       cores=24, threads=32, base_clock_ghz=3.0, boost_clock_ghz=5.8,
       tdp_w=None, process_node_nm=10, socket="FCLGA1700"),
    hw("PREVIEW M25 RTX 4080 partial", "NVIDIA", "GPU",
       memory_gb=16, memory_type="GDDR6X", core_clock_mhz=2205,
       boost_clock_mhz=2505, vram_bandwidth_gbps=717,
       memory_bus_width_bits=256, tdp_w=None,
       interface="PCIe 4.0 x16", length_mm=310),
    hw("PREVIEW M25 Fury DDR5 64GB partial", "Kingston", "RAM",
       ddr_generation="DDR5", capacity_gb=64, speed_mhz=None,
       modules=2, form_factor="DIMM"),
    hw("PREVIEW M25 870 EVO 2TB", "Samsung", "STORAGE",
       storage_type="SATA SSD", capacity_gb=2048, interface="SATA 6Gb/s",
       form_factor="2.5in"),
    hw("PREVIEW M25 X670-E partial", "ASUS", "MOTHERBOARD",
       socket=None, chipset="X670E", form_factor="ATX",
       ram_type="DDR5", ram_slots=None, max_ram_gb=None,
       m2_slots=None, sata_ports=None, pcie_slots=None),
    hw("PREVIEW M25 RM1000x", "Corsair", "PSU",
       wattage=1000, efficiency_rating="80 Plus Gold", modular=True,
       pcie_8pin_count=6, pcie_12vhpwr=1),
]

with SessionLocal() as session:
    source = Source(name="M2.5 Preview Fixture Source", url="https://example.com/preview")
    session.add(source)
    session.flush()
    session.add_all(BUILD_A + BUILD_B + BUILD_C)
    session.commit()
    total = session.query(Hardware).count()

con = sqlite3.connect(DB_PATH)
tables = sorted(
    r[0]
    for r in con.execute("select name from sqlite_master where type='table'")
)
preview = con.execute(
    "select type, count(*) from hardware where name like 'PREVIEW M25%' group by type order by type"
).fetchall()
con.close()

print("DB:", DB_PATH)
print("hardware total:", total)
print("tables:", tables)
print("preview fixtures by type:", preview)
