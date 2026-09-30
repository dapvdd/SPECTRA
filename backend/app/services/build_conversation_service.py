from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import (
    BuildConversation,
    BuildMessage,
    Hardware,
)
from backend.app.schemas.build_chat import (
    BuildAnalysis,
    BuildChatMessageRole,
    BuildEvidence,
)
from backend.app.schemas.build_conversation import (
    BuildConversationCreateRequest,
    BuildConversationResponse,
    BuildMessageCreateRequest,
    BuildMessageResponse,
    BuildTurnCreateRequest,
    BuildTurnResponse,
)


class BuildIdentityError(ValueError):
    """The requested CPU and GPU cannot form a build conversation."""


class ConversationNotFoundError(ValueError):
    """The requested build conversation does not exist."""


class StoredConversationDataError(ValueError):
    """A stored build conversation message could not be read back."""


def _require_hardware(
    session: Session,
    hardware_id: int,
    expected_type: str,
    label: str,
) -> Hardware:
    hardware = session.get(Hardware, hardware_id)

    if hardware is None:
        raise BuildIdentityError(
            f"{label} hardware not found: {hardware_id}"
        )

    if hardware.type != expected_type:
        raise BuildIdentityError(
            f"{label} hardware must be a {expected_type}: {hardware_id}"
        )

    return hardware


def _require_conversation(
    session: Session,
    conversation_id: int,
) -> BuildConversation:
    conversation = session.get(BuildConversation, conversation_id)

    if conversation is None:
        raise ConversationNotFoundError(
            f"Build conversation not found: {conversation_id}"
        )

    return conversation


def _add_message(
    session: Session,
    conversation: BuildConversation,
    role: BuildChatMessageRole,
    content: str,
    evidence: BuildEvidence | None,
    analysis: BuildAnalysis | None,
    now: datetime,
) -> BuildMessage:
    message = BuildMessage(
        conversation_id=conversation.id,
        role=role.value,
        content=content,
        evidence_json=(
            evidence.model_dump_json() if evidence is not None else None
        ),
        analysis_json=(
            analysis.model_dump_json() if analysis is not None else None
        ),
        created_at=now,
    )

    session.add(message)
    conversation.updated_at = now

    return message


def _parse_evidence(raw: str) -> BuildEvidence:
    try:
        return BuildEvidence.model_validate_json(raw)
    except ValidationError as error:
        raise StoredConversationDataError(
            "A stored assistant message has unreadable evidence."
        ) from error


def _parse_analysis(raw: str) -> BuildAnalysis:
    try:
        return BuildAnalysis.model_validate_json(raw)
    except ValidationError as error:
        raise StoredConversationDataError(
            "A stored assistant message has unreadable analysis."
        ) from error


def _parse_role(raw: str) -> BuildChatMessageRole:
    try:
        return BuildChatMessageRole(raw)
    except ValueError as error:
        raise StoredConversationDataError(
            f"A stored build message has an unsupported role: {raw}"
        ) from error


def build_message_response(message: BuildMessage) -> BuildMessageResponse:
    evidence = (
        _parse_evidence(message.evidence_json)
        if message.evidence_json is not None
        else None
    )
    analysis = (
        _parse_analysis(message.analysis_json)
        if message.analysis_json is not None
        else None
    )

    return BuildMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=_parse_role(message.role),
        content=message.content,
        evidence=evidence,
        analysis=analysis,
        created_at=message.created_at,
    )


def build_turn_response(
    conversation_id: int,
    user_message: BuildMessage,
    assistant_message: BuildMessage,
) -> BuildTurnResponse:
    return BuildTurnResponse(
        conversation_id=conversation_id,
        user_message=build_message_response(user_message),
        assistant_message=build_message_response(assistant_message),
    )


def create_or_get_conversation(
    request_data: BuildConversationCreateRequest,
) -> BuildConversationResponse:
    with SessionLocal() as session:
        _require_hardware(
            session,
            request_data.cpu_hardware_id,
            "CPU",
            "CPU",
        )
        _require_hardware(
            session,
            request_data.gpu_hardware_id,
            "GPU",
            "GPU",
        )

        conversation = session.scalar(
            select(BuildConversation).where(
                BuildConversation.cpu_hardware_id
                == request_data.cpu_hardware_id,
                BuildConversation.gpu_hardware_id
                == request_data.gpu_hardware_id,
            )
        )

        if conversation is None:
            now = datetime.now()
            conversation = BuildConversation(
                cpu_hardware_id=request_data.cpu_hardware_id,
                gpu_hardware_id=request_data.gpu_hardware_id,
                created_at=now,
                updated_at=now,
            )
            session.add(conversation)
            session.commit()
            session.refresh(conversation)

        return BuildConversationResponse.model_validate(conversation)


def get_conversation(conversation_id: int) -> BuildConversationResponse:
    with SessionLocal() as session:
        conversation = _require_conversation(session, conversation_id)

        return BuildConversationResponse.model_validate(conversation)


def list_messages(conversation_id: int) -> list[BuildMessageResponse]:
    with SessionLocal() as session:
        _require_conversation(session, conversation_id)

        messages = session.scalars(
            select(BuildMessage)
            .where(BuildMessage.conversation_id == conversation_id)
            .order_by(BuildMessage.created_at, BuildMessage.id)
        ).all()

        return [
            build_message_response(message) for message in messages
        ]


def append_message(
    conversation_id: int,
    message_data: BuildMessageCreateRequest,
) -> BuildMessageResponse:
    with SessionLocal() as session:
        conversation = _require_conversation(session, conversation_id)

        message = _add_message(
            session,
            conversation,
            message_data.role,
            message_data.content,
            message_data.evidence,
            message_data.analysis,
            datetime.now(),
        )

        session.commit()
        session.refresh(message)

        return build_message_response(message)


def append_turn(
    conversation_id: int,
    turn_data: BuildTurnCreateRequest,
) -> BuildTurnResponse:
    with SessionLocal() as session:
        conversation = _require_conversation(session, conversation_id)
        now = datetime.now()

        user_message = _add_message(
            session,
            conversation,
            BuildChatMessageRole.user,
            turn_data.question,
            None,
            None,
            now,
        )
        assistant_message = _add_message(
            session,
            conversation,
            BuildChatMessageRole.assistant,
            turn_data.answer,
            turn_data.evidence,
            turn_data.analysis,
            now,
        )

        session.commit()
        session.refresh(user_message)
        session.refresh(assistant_message)

        return build_turn_response(
            conversation_id,
            user_message,
            assistant_message,
        )


def reset_conversation(conversation_id: int) -> BuildConversationResponse:
    with SessionLocal() as session:
        conversation = _require_conversation(session, conversation_id)

        session.execute(
            delete(BuildMessage).where(
                BuildMessage.conversation_id == conversation_id
            )
        )
        conversation.updated_at = datetime.now()

        session.commit()
        session.refresh(conversation)

        return BuildConversationResponse.model_validate(conversation)
