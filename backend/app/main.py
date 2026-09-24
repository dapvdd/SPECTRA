from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_backend_environment():
    load_dotenv(PROJECT_ROOT / ".env", override=False)


load_backend_environment()

from backend.app.database import SessionLocal
from backend.app.models import Hardware

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.schemas.benchmark import BenchmarkResultResponse
from backend.app.schemas.explanation import (
    ExplanationRequest,
    ExplanationResponse,
)
from backend.app.schemas.hardware_chat import (
    HardwareChatRequest,
    HardwareChatResponse,
)
from backend.app.services.benchmark_service import (
    get_benchmarks_for_hardware,
)
from backend.app.services import explanation_service
from backend.app.services import hardware_chat_service


app = FastAPI(
    title="SPECTRA API",
    description="Hardware Intelligence Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
def get_hardware(
    hardware_type: str | None = Query(default=None, alias="type"),
):
    statement = select(Hardware)

    if hardware_type is not None:
        statement = statement.where(
            Hardware.type == hardware_type
        )

    with SessionLocal() as session:
        hardware_list = session.scalars(
            statement
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

        if hardware.type == "GPU":
            gpu_spec = hardware.gpu_specification

            return {
                "id": hardware.id,
                "name": hardware.name,
                "manufacturer": hardware.manufacturer,
                "type": hardware.type,
                "release_date": hardware.release_date,
                "architecture": hardware.architecture,

                "specifications": {
                    "memory_gb": (
                        gpu_spec.memory_gb
                        if gpu_spec
                        else None
                    ),
                    "memory_type": (
                        gpu_spec.memory_type
                        if gpu_spec
                        else None
                    ),
                    "core_clock_mhz": (
                        gpu_spec.core_clock_mhz
                        if gpu_spec
                        else None
                    ),
                    "boost_clock_mhz": (
                        gpu_spec.boost_clock_mhz
                        if gpu_spec
                        else None
                    ),
                    "vram_bandwidth_gbps": (
                        gpu_spec.vram_bandwidth_gbps
                        if gpu_spec
                        else None
                    ),
                    "tdp_w": (
                        gpu_spec.tdp_w
                        if gpu_spec
                        else None
                    ),
                    "interface": (
                        gpu_spec.interface
                        if gpu_spec
                        else None
                    ),
                    "length_mm": (
                        gpu_spec.length_mm
                        if gpu_spec
                        else None
                    ),
                },
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


@app.get(
    "/hardware/{hardware_id}/benchmarks",
    response_model=list[BenchmarkResultResponse],
)
def get_hardware_benchmarks(
    hardware_id: int,
) -> list[BenchmarkResultResponse]:
    try:
        return get_benchmarks_for_hardware(hardware_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post(
    "/comparison/explanation",
    response_model=ExplanationResponse,
)
def generate_comparison_explanation(
    request_data: ExplanationRequest,
) -> ExplanationResponse:
    try:
        explanation = explanation_service.generate_explanation(
            request_data.comparison
        )
    except explanation_service.ProviderUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except explanation_service.ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return ExplanationResponse(explanation=explanation)


@app.post(
    "/hardware/chat",
    response_model=HardwareChatResponse,
)
def generate_hardware_chat_answer(
    request_data: HardwareChatRequest,
) -> HardwareChatResponse:
    try:
        answer = hardware_chat_service.generate_chat_answer(request_data)
    except explanation_service.ProviderUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except explanation_service.ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return HardwareChatResponse(answer=answer)
