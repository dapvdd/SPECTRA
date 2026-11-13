from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator


ScalarValue: TypeAlias = str | int | float | bool | None

MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_MESSAGE_LENGTH = 4000

# M2.5 Task 5: the compatibility digest is a bounded summary of the last
# SPECTRA compatibility check. The M2 rule set has seven rules; the digest
# carries at most that many entries so a client cannot inflate the prompt.
MAX_COMPATIBILITY_RULE_RESULTS = 7
MAX_COMPATIBILITY_RULE_EXPLANATION_LENGTH = 600
MAX_COMPATIBILITY_UNRESOLVED_ITEMS = 7
MAX_COMPATIBILITY_UNRESOLVED_ITEM_LENGTH = 300
MAX_COMPATIBILITY_SLOTS = 6

COMPATIBILITY_STATES = ("COMPATIBLE", "INCOMPATIBLE", "UNKNOWN")

MAX_EVIDENCE_ITEMS = 10
MAX_EVIDENCE_ITEM_LENGTH = 1000

MAX_ANALYSIS_ITEMS = 5
MAX_ANALYSIS_ITEM_LENGTH = 500


class BuildUseCase(str, Enum):
    gaming = "gaming"
    productivity = "productivity"
    ai_compute = "ai_compute"
    general = "general"
    unspecified = "unspecified"


class BuildResolution(str, Enum):
    unspecified = "unspecified"
    p1080 = "1080p"
    p1440 = "1440p"
    p4k = "4k"


class BuildBenchmarkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None, gt=0)
    hardware_id: int | None = Field(default=None, gt=0)
    benchmark_name: str = Field(min_length=1)
    test_type: str = Field(min_length=1)
    score: float = Field(gt=0)
    unit: str = Field(min_length=1)
    source: str | dict[str, ScalarValue] | None = None
    recorded_at: str | None = None

    @field_validator("benchmark_name", "test_type", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class BuildCpuSpecifications(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cores: int | None = Field(default=None, ge=0)
    threads: int | None = Field(default=None, ge=0)
    base_clock_ghz: float | None = Field(default=None, ge=0)
    boost_clock_ghz: float | None = Field(default=None, ge=0)
    tdp_w: float | None = Field(default=None, ge=0)
    process_node_nm: float | None = Field(default=None, ge=0)
    socket: str | None = None

    @field_validator("socket")
    @classmethod
    def strip_socket(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class BuildGpuSpecifications(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_gb: float | None = Field(default=None, ge=0)
    memory_type: str | None = None
    core_clock_mhz: float | None = Field(default=None, ge=0)
    boost_clock_mhz: float | None = Field(default=None, ge=0)
    vram_bandwidth_gbps: float | None = Field(default=None, ge=0)
    tdp_w: float | None = Field(default=None, ge=0)
    interface: str | None = None
    length_mm: float | None = Field(default=None, ge=0)

    @field_validator("memory_type", "interface")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class BuildComponentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    architecture: str | None = None
    release_date: str | None = None
    benchmarks: list[BuildBenchmarkContext] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("manufacturer", "architecture", "release_date")
    @classmethod
    def strip_component_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class BuildCpuContext(BuildComponentContext):
    type: Literal["CPU"] = "CPU"
    specifications: BuildCpuSpecifications = Field(
        default_factory=BuildCpuSpecifications
    )


class BuildGpuContext(BuildComponentContext):
    type: Literal["GPU"] = "GPU"
    specifications: BuildGpuSpecifications = Field(
        default_factory=BuildGpuSpecifications
    )


class BuildUserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case: BuildUseCase = BuildUseCase.unspecified
    resolution: BuildResolution = BuildResolution.unspecified


class BuildCompatibilityRuleDigest(BaseModel):
    """One rule result from the last SPECTRA compatibility check.

    A pass-through of a SPECTRA-computed fact: rule_id, state, and the
    explanation SPECTRA already produced. Nothing here is derived, scored,
    or extended by the assistant.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1, max_length=100)
    state: Literal["COMPATIBLE", "INCOMPATIBLE", "UNKNOWN"]
    explanation: str = Field(
        min_length=1, max_length=MAX_COMPATIBILITY_RULE_EXPLANATION_LENGTH
    )


class BuildCompatibilityDigest(BaseModel):
    """Bounded compatibility summary for the six-slot build.

    ``aggregate_state`` is the report-level verdict from the last
    compatibility check; ``rule_results`` carries the individual outcomes
    (at most MAX_COMPATIBILITY_RULE_RESULTS entries); ``unresolved`` names
    checks that could not be completed and why; ``slots`` maps slot name ->
    selected hardware id (six-slot identity without serializing records).
    """

    model_config = ConfigDict(extra="forbid")

    aggregate_state: Literal["COMPATIBLE", "INCOMPATIBLE", "UNKNOWN"]
    rule_results: list[BuildCompatibilityRuleDigest] = Field(
        default_factory=list,
        max_length=MAX_COMPATIBILITY_RULE_RESULTS,
    )
    unresolved: list[
        Annotated[
            str, Field(min_length=1, max_length=MAX_COMPATIBILITY_UNRESOLVED_ITEM_LENGTH)
        ]
    ] = Field(
        default_factory=list,
        max_length=MAX_COMPATIBILITY_UNRESOLVED_ITEMS,
    )
    slots: dict[
        Annotated[str, Field(min_length=1, max_length=20)],
        Annotated[int, Field(gt=0)],
    ] = Field(
        default_factory=dict,
        max_length=MAX_COMPATIBILITY_SLOTS,
    )


class BuildContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: BuildCpuContext
    gpu: BuildGpuContext
    context: BuildUserContext = Field(default_factory=BuildUserContext)
    compatibility: BuildCompatibilityDigest | None = None


class BuildChatMessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class BuildChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: BuildChatMessageRole
    content: str = Field(min_length=1, max_length=MAX_HISTORY_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class BuildHardwareChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build: BuildContext
    messages: list[BuildChatMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
    )
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("messages")
    @classmethod
    def enforce_alternating_roles(
        cls,
        value: list[BuildChatMessage],
    ) -> list[BuildChatMessage]:
        for index, message in enumerate(value):
            expected_role = (
                BuildChatMessageRole.user
                if index % 2 == 0
                else BuildChatMessageRole.assistant
            )
            if message.role is not expected_role:
                raise ValueError(
                    "history must strictly alternate starting with 'user', "
                    f"but message {index} has role '{message.role.value}'"
                )
        return value


def _validate_evidence_item(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    if len(value) > MAX_EVIDENCE_ITEM_LENGTH:
        raise ValueError(f"must be at most {MAX_EVIDENCE_ITEM_LENGTH} characters")
    return value


BuildEvidenceItem: TypeAlias = Annotated[str, AfterValidator(_validate_evidence_item)]


class BuildEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known_facts: list[BuildEvidenceItem] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_ITEMS,
    )
    interpretation: list[BuildEvidenceItem] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_ITEMS,
    )
    unknown: list[BuildEvidenceItem] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_ITEMS,
    )


def _validate_analysis_item(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    if len(value) > MAX_ANALYSIS_ITEM_LENGTH:
        raise ValueError(f"must be at most {MAX_ANALYSIS_ITEM_LENGTH} characters")
    return value


BuildAnalysisItem: TypeAlias = Annotated[str, AfterValidator(_validate_analysis_item)]


class BuildAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[BuildAnalysisItem] = Field(
        default_factory=list,
        max_length=MAX_ANALYSIS_ITEMS,
    )
    considerations: list[BuildAnalysisItem] = Field(
        default_factory=list,
        max_length=MAX_ANALYSIS_ITEMS,
    )
    data_gaps: list[BuildAnalysisItem] = Field(
        default_factory=list,
        max_length=MAX_ANALYSIS_ITEMS,
    )


class BuildHardwareChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    evidence: BuildEvidence
    analysis: BuildAnalysis

    @field_validator("answer")
    @classmethod
    def strip_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value
