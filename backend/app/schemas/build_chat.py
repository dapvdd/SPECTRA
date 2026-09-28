from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


ScalarValue: TypeAlias = str | int | float | bool | None

MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_MESSAGE_LENGTH = 4000


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


class BuildContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: BuildCpuContext
    gpu: BuildGpuContext
    context: BuildUserContext = Field(default_factory=BuildUserContext)


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


class BuildHardwareChatResponse(BaseModel):
    answer: str = Field(min_length=1)
