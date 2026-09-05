from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Hardware

from fastapi import FastAPI


app = FastAPI(
    title="SPECTRA API",
    description="Hardware Intelligence Platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Welcome to SPECTRA API",
        "status": "online",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }

@app.get("/hardware")
def get_hardware():
    with SessionLocal() as session:
        hardware_list = session.scalars(
            select(Hardware)
        ).all()

        return [
            {
                "id": hardware.id,
                "name": hardware.name,
                "manufacturer": hardware.manufacturer,
                "type": hardware.type,
            }
            for hardware in hardware_list
        ]

@app.get("/hardware/{hardware_id}")
def get_hardware_detail(hardware_id: int):
    with SessionLocal() as session:
        hardware = session.get(
            Hardware,
            hardware_id,
        )

        if not hardware:
            return {
                "error": "Hardware not found"
            }

        cpu_spec = hardware.cpu_specification

        return {
            "id": hardware.id,
            "name": hardware.name,
            "manufacturer": hardware.manufacturer,
            "type": hardware.type,
            "release_date": hardware.release_date,
            "architecture": hardware.architecture,

            "specifications": {
                "cores": (
                    cpu_spec.cores
                    if cpu_spec
                    else None
                ),
                "threads": (
                    cpu_spec.threads
                    if cpu_spec
                    else None
                ),
                "base_clock_ghz": (
                    cpu_spec.base_clock_ghz
                    if cpu_spec
                    else None
                ),
                "boost_clock_ghz": (
                    cpu_spec.boost_clock_ghz
                    if cpu_spec
                    else None
                ),
                "tdp_w": (
                    cpu_spec.tdp_w
                    if cpu_spec
                    else None
                ),
                "process_node_nm": (
                    cpu_spec.process_node_nm
                    if cpu_spec
                    else None
                ),
                "socket": (
                    cpu_spec.socket
                    if cpu_spec
                    else None
                ),
            },
        }