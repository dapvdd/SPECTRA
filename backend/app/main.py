import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_backend_environment():
    load_dotenv(PROJECT_ROOT / ".env", override=False)


load_backend_environment()

from backend.app.database import SessionLocal
from backend.app.models import Hardware

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

_cors_origins = os.getenv("SPECTRA_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080")
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

from backend.app.schemas.benchmark import BenchmarkResultResponse
from backend.app.schemas.hardware import (
    FacetCount,
    HardwareCatalogItem,
    HardwareDetail,
    HardwareFacetsResponse,
)
from backend.app.services.hardware_catalog_service import (
    get_hardware_facets,
    query_hardware,
)
from backend.app.logging_config import configure_logging, get_logger
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import (
    REQUEST_ID_HEADER,
    install_request_id_middleware,
)
from backend.app.schemas.build_chat import (
    BuildHardwareChatRequest,
    BuildHardwareChatResponse,
)
from backend.app.schemas.build_conversation import (
    BuildConversationCreateRequest,
    BuildConversationResponse,
    BuildMessageCreateRequest,
    BuildMessageResponse,
    BuildTurnCreateRequest,
    BuildTurnResponse,
)
from backend.app.schemas.explanation import (
    ExplanationRequest,
    ExplanationResponse,
)
from backend.app.schemas.comparison import (
    GPUComparisonRequest,
    ComparisonResultResponse,
    MetricComparisonResponse,
)
from backend.app.schemas.hardware_chat import (
    HardwareChatRequest,
    HardwareChatResponse,
)
from backend.app.schemas.provenance import (
    BenchmarkProvenanceResponse,
    HardwareProvenanceResponse,
    SourceSummaryResponse,
)
from backend.app.services.benchmark_service import (
    get_benchmarks_for_hardware,
)
from backend.app.services import build_chat_service
from backend.app.services import build_conversation_service
from backend.app.services import comparison_service
from backend.app.services import explanation_service
from backend.app.services import hardware_chat_service
from backend.app.services import source_service


# Configure structured JSON logging before any request handling. Running the
# JSON handler twice is a no-op thanks to configure_logging idempotency.
configure_logging()

logger = get_logger(__name__)

app = FastAPI(
    title="SPECTRA API",
    description="Hardware Intelligence Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Opt-in rate/cost control for the AI endpoints. Disabled unless configured
# (SPECTRA_RATE_LIMIT_ENABLED=1) so existing behaviour and tests are unchanged.
app.add_middleware(RateLimitMiddleware)

# Request-id correlation. Additive: sets a header on every response and never
# changes behaviour. Setting it is safe because no existing test asserts the
# absence of a header.
install_request_id_middleware(app)


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


@app.get("/ready")
def readiness_check():
    """Readiness probe: DB reachable and migrations current.

    Semantics for orchestration: returns 200 only when ready, 503 with a JSON
    body when not. The DB check is a ``SELECT 1`` through the app's own session
    factory. Migration status is reported over the versioned runner's
    ``schema_version`` table (0 = baseline not yet applied, which is an
    informational state, not a readiness failure — the runner is new and the
    deployed DB predates it). No production migration is ever applied here.
    """
    db_ready = False
    migrations_status = "unknown"

    try:
        with SessionLocal() as session:
            session.execute(select(Hardware.id).limit(1))
            has_version_table = session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='schema_version'"
                )
            ).scalar()
            if has_version_table:
                version = session.execute(
                    text("SELECT version FROM schema_version WHERE id=1")
                ).scalar()
                migrations_status = f"tracked-version-{version}"
            else:
                migrations_status = "untracked"
        db_ready = True
    except Exception as error:  # noqa: BLE001 - report any probe failure
        logger.error(
            "readiness probe failed",
            extra={"error": str(error)},
        )
        db_ready = False

    ready = db_ready
    if not ready:
        raise HTTPException(status_code=503, detail="not ready")

    return {
        "status": "ready",
        "database": "reachable",
        "migrations": migrations_status,
    }

@app.get(
    "/hardware",
    response_model=list[HardwareCatalogItem],
)
def get_hardware(
    response: Response,
    hardware_type: str | None = Query(default=None, alias="type"),
    q: str | None = Query(default=None, min_length=1),
    manufacturer: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[HardwareCatalogItem]:
    """Server-side catalog query (Phase 1.3).

    All parameters are additive. With no parameters the endpoint returns the
    full catalog exactly as before 1.3 (byte-identical default behavior).
    ``q`` filters by case-insensitive name substring; ``type``/``manufacturer``/
    ``segment`` filter exactly; ``limit``/``offset`` paginate the result. The
    ``X-Total-Count`` header always carries the total rows under the active
    filters (the full filtered set, not the page), so clients can page without
    guessing.
    """
    page, total = query_hardware(
        hardware_type=hardware_type,
        q=q,
        manufacturer=manufacturer,
        segment=segment,
        limit=limit,
        offset=offset,
    )

    # Always set the header so default callers also learn the whole catalog
    # size, and paginated callers learn the full filtered total.
    response.headers["X-Total-Count"] = str(total)

    return [
        {
            "id": hardware.id,
            "name": hardware.name,
            "manufacturer": hardware.manufacturer,
            "type": hardware.type,
            "segment": hardware.segment,
            "release_date": hardware.release_date,
            "architecture": hardware.architecture,
        }
        for hardware in page
    ]


@app.get(
    "/hardware/facets",
    response_model=HardwareFacetsResponse,
)
def get_hardware_facet_counts(
    hardware_type: str | None = Query(default=None, alias="type"),
    q: str | None = Query(default=None, min_length=1),
    manufacturer: str | None = Query(default=None),
    segment: str | None = Query(default=None),
) -> HardwareFacetsResponse:
    """Accurate facet counts for the active catalog filters.

    Counts are computed with the same WHERE clauses the catalog query applies,
    so each facet reflects the rows visible under the other active filters.
    Declared before ``/hardware/{hardware_id}`` so the literal ``facets`` path
    is not shadowed by the id route.
    """
    facets = get_hardware_facets(
        hardware_type=hardware_type,
        q=q,
        manufacturer=manufacturer,
        segment=segment,
    )

    return {
        "types": facets["types"],
        "manufacturers": facets["manufacturers"],
        "segments": facets["segments"],
    }

@app.get(
    "/hardware/{hardware_id}",
    response_model=HardwareDetail,
)
def get_hardware_detail(hardware_id: int) -> HardwareDetail:
    with SessionLocal() as session:
        hardware = session.get(
            Hardware,
            hardware_id,
        )

        if not hardware:
            raise HTTPException(status_code=404, detail="Hardware not found")

        if hardware.type == "GPU":
            gpu_spec = hardware.gpu_specification

            return {
                "id": hardware.id,
                "name": hardware.name,
                "manufacturer": hardware.manufacturer,
                "type": hardware.type,
                "segment": hardware.segment,
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
                    "memory_bus_width_bits": (
                        gpu_spec.memory_bus_width_bits
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
            "segment": hardware.segment,
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
    source_id: int | None = Query(default=None),
    benchmark_name: str | None = Query(default=None),
    test_type: str | None = Query(default=None),
) -> list[BenchmarkResultResponse]:
    try:
        return get_benchmarks_for_hardware(
            hardware_id,
            source_id=source_id,
            benchmark_name=benchmark_name,
            test_type=test_type,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/sources",
    response_model=list[SourceSummaryResponse],
)
def get_sources() -> list[SourceSummaryResponse]:
    """List the registered sources with their provenance usage and terms."""
    return source_service.list_sources()


@app.get(
    "/sources/{source_id}",
    response_model=SourceSummaryResponse,
)
def get_source(source_id: int) -> SourceSummaryResponse:
    try:
        return source_service.get_source(source_id)
    except source_service.ProvenanceLookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/hardware/{hardware_id}/provenance",
    response_model=HardwareProvenanceResponse,
)
def get_hardware_provenance(hardware_id: int) -> HardwareProvenanceResponse:
    try:
        return source_service.get_hardware_provenance(hardware_id)
    except source_service.ProvenanceLookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/benchmarks/{benchmark_result_id}/provenance",
    response_model=BenchmarkProvenanceResponse,
)
def get_benchmark_provenance(
    benchmark_result_id: int,
) -> BenchmarkProvenanceResponse:
    try:
        return source_service.get_benchmark_provenance(benchmark_result_id)
    except source_service.ProvenanceLookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post(
    "/comparison/gpu",
    response_model=ComparisonResultResponse,
)
def compare_gpu_hardware(
    request_data: GPUComparisonRequest,
) -> ComparisonResultResponse:
    """Deterministic GPU comparison by specification metrics.

    Mirrors the CPU comparison semantics (unavailable / tie / winner). Returns
    404 when either hardware id does not exist, and 422 when either record is
    not a GPU with a specification.
    """
    with SessionLocal() as session:
        hardware_a = session.scalars(
            select(Hardware)
            .where(Hardware.id == request_data.hardware_id_a)
            .options(selectinload(Hardware.gpu_specification))
        ).first()
        hardware_b = session.scalars(
            select(Hardware)
            .where(Hardware.id == request_data.hardware_id_b)
            .options(selectinload(Hardware.gpu_specification))
        ).first()

    if hardware_a is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hardware not found: {request_data.hardware_id_a}",
        )
    if hardware_b is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hardware not found: {request_data.hardware_id_b}",
        )

    try:
        result = comparison_service.compare_gpus(hardware_a, hardware_b)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return ComparisonResultResponse(
        hardware_a=result.hardware_a,
        hardware_b=result.hardware_b,
        metrics=[
            MetricComparisonResponse(
                name=metric.name,
                value_a=metric.value_a,
                value_b=metric.value_b,
                unit=metric.unit,
                winner=metric.winner,
                difference=metric.difference,
            )
            for metric in result.metrics
        ],
    )


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


@app.post(
    "/build/chat",
    response_model=BuildHardwareChatResponse,
)
def generate_build_chat_answer(
    request_data: BuildHardwareChatRequest,
) -> BuildHardwareChatResponse:
    try:
        return build_chat_service.generate_build_chat_answer(request_data)
    except explanation_service.ProviderUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except explanation_service.ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post(
    "/build/conversations",
    response_model=BuildConversationResponse,
)
def create_build_conversation(
    request_data: BuildConversationCreateRequest,
) -> BuildConversationResponse:
    try:
        return build_conversation_service.create_or_get_conversation(
            request_data
        )
    except build_conversation_service.BuildIdentityError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get(
    "/build/conversations/{conversation_id}",
    response_model=BuildConversationResponse,
)
def get_build_conversation(
    conversation_id: int,
) -> BuildConversationResponse:
    try:
        return build_conversation_service.get_conversation(conversation_id)
    except build_conversation_service.ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/build/conversations/{conversation_id}/messages",
    response_model=list[BuildMessageResponse],
)
def get_build_conversation_messages(
    conversation_id: int,
) -> list[BuildMessageResponse]:
    try:
        return build_conversation_service.list_messages(conversation_id)
    except build_conversation_service.ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except build_conversation_service.StoredConversationDataError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post(
    "/build/conversations/{conversation_id}/messages",
    response_model=BuildMessageResponse,
    status_code=201,
)
def append_build_conversation_message(
    conversation_id: int,
    request_data: BuildMessageCreateRequest,
) -> BuildMessageResponse:
    try:
        return build_conversation_service.append_message(
            conversation_id,
            request_data,
        )
    except build_conversation_service.ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post(
    "/build/conversations/{conversation_id}/turn",
    response_model=BuildTurnResponse,
    status_code=201,
)
def append_build_conversation_turn(
    conversation_id: int,
    request_data: BuildTurnCreateRequest,
) -> BuildTurnResponse:
    try:
        return build_conversation_service.append_turn(
            conversation_id,
            request_data,
        )
    except build_conversation_service.ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post(
    "/build/conversations/{conversation_id}/reset",
    response_model=BuildConversationResponse,
)
def reset_build_conversation(
    conversation_id: int,
) -> BuildConversationResponse:
    try:
        return build_conversation_service.reset_conversation(conversation_id)
    except build_conversation_service.ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
