from datetime import datetime
from typing import Annotated, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from backend.app.schemas.build_chat import (
    BuildAnalysis,
    BuildChatMessageRole,
    BuildEvidence,
)


MAX_PERSISTED_MESSAGE_LENGTH = 40000

MAX_PERSISTED_TURN_ANSWER_LENGTH = 40000
MAX_PERSISTED_TURN_QUESTION_LENGTH = 2000


def _validate_message_content(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")

    value = value.strip()

    if not value:
        raise ValueError("must not be blank")

    if len(value) > MAX_PERSISTED_MESSAGE_LENGTH:
        raise ValueError(
            f"must be at most {MAX_PERSISTED_MESSAGE_LENGTH} characters"
        )

    return value


BuildMessageContent: TypeAlias = Annotated[
    str,
    AfterValidator(_validate_message_content),
]


class BuildConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_hardware_id: int = Field(gt=0)
    gpu_hardware_id: int = Field(gt=0)


class BuildMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: BuildChatMessageRole
    content: BuildMessageContent
    evidence: BuildEvidence | None = None
    analysis: BuildAnalysis | None = None

    @model_validator(mode="after")
    def reject_assistant_metadata_for_user_messages(self):
        if self.role is BuildChatMessageRole.user and (
            self.evidence is not None or self.analysis is not None
        ):
            raise ValueError(
                "a user message must not carry evidence or analysis"
            )

        return self


class BuildTurnCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=MAX_PERSISTED_TURN_QUESTION_LENGTH,
    )
    answer: str = Field(
        min_length=1,
        max_length=MAX_PERSISTED_TURN_ANSWER_LENGTH,
    )
    evidence: BuildEvidence = Field(default_factory=BuildEvidence)
    analysis: BuildAnalysis = Field(default_factory=BuildAnalysis)

    @model_validator(mode="after")
    def normalize_turn_text(self):
        question = self.question.strip()
        answer = self.answer.strip()

        if not question:
            raise ValueError("question must not be blank")

        if not answer:
            raise ValueError("answer must not be blank")

        if len(question) > MAX_PERSISTED_MESSAGE_LENGTH:
            raise ValueError(
                f"question must be at most {MAX_PERSISTED_MESSAGE_LENGTH} characters"
            )

        if len(answer) > MAX_PERSISTED_MESSAGE_LENGTH:
            raise ValueError(
                f"answer must be at most {MAX_PERSISTED_MESSAGE_LENGTH} characters"
            )

        return self.model_copy(update={"question": question, "answer": answer})


class BuildConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cpu_hardware_id: int
    gpu_hardware_id: int
    created_at: datetime
    updated_at: datetime


class BuildMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: BuildChatMessageRole
    content: str
    evidence: BuildEvidence | None = None
    analysis: BuildAnalysis | None = None
    created_at: datetime


class BuildTurnResponse(BaseModel):
    conversation_id: int

    user_message: BuildMessageResponse
    assistant_message: BuildMessageResponse
