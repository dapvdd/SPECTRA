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