from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base
from backend.app.models import (
    BuildConversation,
    BuildMessage,
    CPUSpecification,
    GPUSpecification,
    Hardware,
)
from backend.app.schemas.build_chat import (
    MAX_HISTORY_MESSAGE_LENGTH,
    BuildAnalysis,
    BuildEvidence,
    BuildHardwareChatResponse,
)
from backend.app.schemas.build_conversation import (
    MAX_PERSISTED_MESSAGE_LENGTH,
    BuildConversationCreateRequest,
    BuildMessageCreateRequest,
    BuildTurnCreateRequest,
)
from backend.app.services import build_chat_service, build_conversation_service


def _response(answer="Jawaban berbasis bukti.", analysis=None, **evidence):
    return BuildHardwareChatResponse(
        answer=answer,
        evidence=BuildEvidence(**evidence),
        analysis=BuildAnalysis(**(analysis or {})),
    )


def _cpu_message_content(index):
    return f"Pertanyaan {index}?"


def _assistant_message_content(index):
    return f"Jawaban {index}."


class TestBuildConversationModels:
    def test_conversation_is_bound_to_one_build_identity(self):
        table = BuildConversation.__table__

        assert BuildConversation.__tablename__ == "build_conversations"
        assert {column.name for column in table.columns} == {
            "id",
            "cpu_hardware_id",
            "gpu_hardware_id",
            "created_at",
            "updated_at",
        }

        constraints = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert ("cpu_hardware_id", "gpu_hardware_id") in constraints

    def test_message_columns_keep_evidence_and_analysis_on_the_row(self):
        table = BuildMessage.__table__

        assert BuildMessage.__tablename__ == "build_messages"
        assert {column.name for column in table.columns} == {
            "id",
            "conversation_id",
            "role",
            "content",
            "evidence_json",
            "analysis_json",
            "created_at",
        }

    def test_message_belongs_to_one_conversation(self):
        table = BuildMessage.__table__
        referenced_tables = {
            element.column.table.name
            for constraint in table.foreign_key_constraints
            for element in constraint.elements
        }

        assert referenced_tables == {"build_conversations"}

    def test_conversation_references_stored_hardware(self):
        table = BuildConversation.__table__
        referenced_tables = {
            element.column.table.name
            for constraint in table.foreign_key_constraints
            for element in constraint.elements
        }

        assert referenced_tables == {"hardware"}


class TestBuildConversationSchemas:
    def test_create_request_requires_two_positive_hardware_ids(self):
        for payload in (
            {"cpu_hardware_id": 1},
            {"gpu_hardware_id": 1},
            {"cpu_hardware_id": 0, "gpu_hardware_id": 2},
            {"cpu_hardware_id": -1, "gpu_hardware_id": 2},
            {"cpu_hardware_id": 1, "gpu_hardware_id": 2, "user": "me"},
        ):
            with pytest.raises(ValueError):
                BuildConversationCreateRequest.model_validate(payload)

    def test_message_request_rejects_an_unknown_role(self):
        with pytest.raises(ValueError):
            BuildMessageCreateRequest.model_validate(
                {"role": "system", "content": "Halo"}
            )

    @pytest.mark.parametrize(
        "content",
        ["", "   ", "x" * (MAX_PERSISTED_MESSAGE_LENGTH + 1)],
        ids=["empty", "blank", "oversized"],
    )
    def test_message_request_rejects_empty_or_oversized_content(self, content):
        with pytest.raises(ValueError):
            BuildMessageCreateRequest.model_validate(
                {"role": "user", "content": content}
            )

    def test_user_message_cannot_carry_assistant_metadata(self):
        with pytest.raises(ValueError):
            BuildMessageCreateRequest.model_validate(
                {
                    "role": "user",
                    "content": "Halo",
                    "evidence": {"known_facts": ["Core 6."]},
                }
            )

    def test_turn_request_requires_a_question_and_an_answer(self):
        for payload in (
            {"answer": "Jawaban."},
            {"question": "  ", "answer": "Jawaban."},
            {"question": "Pertanyaan?", "answer": "   "},
            {"question": "Pertanyaan?", "answer": "Jawaban.", "role": "user"},
        ):
            with pytest.raises(ValueError):
                BuildTurnCreateRequest.model_validate(payload)


class TestBuildConversationApi:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.original_main_session_local = main.SessionLocal
        self.original_service_session_local = (
            build_conversation_service.SessionLocal
        )
        main.SessionLocal = self.session_factory
        build_conversation_service.SessionLocal = self.session_factory

        self.original_generator = build_chat_service.generate_build_chat_answer

        self.client = TestClient(main.app)
        self.cpu_id, self.gpu_id, self.gpu_id_other, self.cpu_id_other = (
            self._seed()
        )

    def teardown_method(self):
        build_chat_service.generate_build_chat_answer = self.original_generator
        main.SessionLocal = self.original_main_session_local
        build_conversation_service.SessionLocal = (
            self.original_service_session_local
        )
        self.engine.dispose()

    def _seed(self):
        with self.session_factory() as session:
            cpu = Hardware(
                name="AMD Ryzen 5 5600",
                manufacturer="AMD",
                type="CPU",
                architecture="Zen 3",
            )
            cpu.cpu_specification = CPUSpecification(
                cores=6,
                threads=12,
            )

            gpu = Hardware(
                name="NVIDIA GeForce RTX 5070 Ti",
                manufacturer="NVIDIA",
                type="GPU",
                architecture="Blackwell",
            )
            gpu.gpu_specification = GPUSpecification(
                memory_gb=16,
                memory_type="GDDR7",
            )

            other_gpu = Hardware(
                name="NVIDIA GeForce RTX 5080",
                manufacturer="NVIDIA",
                type="GPU",
                architecture="Blackwell",
            )
            other_gpu.gpu_specification = GPUSpecification(
                memory_gb=16,
                memory_type="GDDR7",
            )

            other_cpu = Hardware(
                name="AMD Ryzen 7 7700X",
                manufacturer="AMD",
                type="CPU",
                architecture="Zen 4",
            )
            other_cpu.cpu_specification = CPUSpecification(
                cores=8,
                threads=16,
            )

            session.add_all([cpu, gpu, other_gpu, other_cpu])
            session.commit()

            return cpu.id, gpu.id, other_gpu.id, other_cpu.id

    def _create_conversation(self, cpu_id=None, gpu_id=None):
        response = self.client.post(
            "/build/conversations",
            json={
                "cpu_hardware_id": cpu_id or self.cpu_id,
                "gpu_hardware_id": gpu_id or self.gpu_id,
            },
        )

        assert response.status_code == 200
        return response.json()

    def test_creates_a_conversation_for_a_cpu_and_gpu_build(self):
        conversation = self._create_conversation()

        assert conversation["cpu_hardware_id"] == self.cpu_id
        assert conversation["gpu_hardware_id"] == self.gpu_id
        assert conversation["id"] > 0
        assert conversation["created_at"] == conversation["updated_at"]

    def test_creating_twice_reuses_the_same_conversation(self):
        first = self._create_conversation()
        second = self._create_conversation()

        assert first["id"] == second["id"]

    def test_a_different_build_uses_a_different_conversation(self):
        first = self._create_conversation()
        other_gpu = self._create_conversation(gpu_id=self.gpu_id_other)
        other_cpu = self._create_conversation(cpu_id=self.cpu_id_other)

        assert first["id"] != other_gpu["id"]
        assert first["id"] != other_cpu["id"]

    def test_unknown_hardware_is_rejected(self):
        response = self.client.post(
            "/build/conversations",
            json={
                "cpu_hardware_id": 999_999,
                "gpu_hardware_id": self.gpu_id,
            },
        )

        assert response.status_code == 422
        assert "CPU hardware not found" in response.json()["detail"]

    def test_a_gpu_cannot_be_used_as_the_build_cpu(self):
        response = self.client.post(
            "/build/conversations",
            json={
                "cpu_hardware_id": self.gpu_id,
                "gpu_hardware_id": self.gpu_id,
            },
        )

        assert response.status_code == 422
        assert "CPU hardware must be a CPU" in response.json()["detail"]

    def test_a_cpu_cannot_be_used_as_the_build_gpu(self):
        response = self.client.post(
            "/build/conversations",
            json={
                "cpu_hardware_id": self.cpu_id,
                "gpu_hardware_id": self.cpu_id,
            },
        )

        assert response.status_code == 422
        assert "GPU hardware must be a GPU" in response.json()["detail"]

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"cpu_hardware_id": 0, "gpu_hardware_id": 2},
            {"cpu_hardware_id": 1, "gpu_hardware_id": "two"},
            {"cpu_hardware_id": 1, "gpu_hardware_id": 2, "unexpected": True},
        ],
    )
    def test_invalid_create_payloads_are_rejected(self, payload):
        response = self.client.post("/build/conversations", json=payload)

        assert response.status_code == 422

    def test_a_conversation_can_be_retrieved(self):
        created = self._create_conversation()

        response = self.client.get(
            f"/build/conversations/{created['id']}"
        )

        assert response.status_code == 200
        assert response.json() == created

    @pytest.mark.parametrize("conversation_id", [0, -3, 999_999])
    def test_an_unknown_conversation_is_not_found(self, conversation_id):
        response = self.client.get(
            f"/build/conversations/{conversation_id}"
        )

        assert response.status_code == 404

    def test_a_non_numeric_conversation_id_is_rejected(self):
        response = self.client.get("/build/conversations/not-a-number")

        assert response.status_code == 422

    def test_a_new_conversation_has_no_messages(self):
        created = self._create_conversation()

        response = self.client.get(
            f"/build/conversations/{created['id']}/messages"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_appends_a_user_message(self):
        created = self._create_conversation()

        response = self.client.post(
            f"/build/conversations/{created['id']}/messages",
            json={"role": "user", "content": "  Apakah build ini konsisten?  "},
        )

        assert response.status_code == 201
        message = response.json()
        assert message["conversation_id"] == created["id"]
        assert message["role"] == "user"
        assert message["content"] == "Apakah build ini konsisten?"
        assert message["evidence"] is None
        assert message["analysis"] is None

    def test_appends_an_assistant_message_with_evidence_and_analysis(self):
        created = self._create_conversation()

        response = self.client.post(
            f"/build/conversations/{created['id']}/messages",
            json={
                "role": "assistant",
                "content": "Karikernya didominasi komponen yang tersedia.",
                "evidence": {
                    "known_facts": ["CPU 6 cores / 12 threads."],
                    "unknown": ["FPS pada 1440p."],
                },
                "analysis": {
                    "strengths": ["Kapasitas multi-core tersimpan."],
                    "data_gaps": ["Benchmark GPU."],
                },
            },
        )

        assert response.status_code == 201
        message = response.json()
        assert message["role"] == "assistant"
        assert message["evidence"] == {
            "known_facts": ["CPU 6 cores / 12 threads."],
            "interpretation": [],
            "unknown": ["FPS pada 1440p."],
        }
        assert message["analysis"] == {
            "strengths": ["Kapasitas multi-core tersimpan."],
            "considerations": [],
            "data_gaps": ["Benchmark GPU."],
        }

    @pytest.mark.parametrize(
        "payload",
        [
            {"role": "system", "content": "Halo"},
            {"role": "user"},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "x" * (MAX_PERSISTED_MESSAGE_LENGTH + 1)},
            {"role": "user", "content": "Halo", "unexpected": 1},
            {
                "role": "user",
                "content": "Halo",
                "evidence": {"known_facts": ["Core 6."]},
            },
            {
                "role": "assistant",
                "content": "Halo",
                "evidence": {"known_facts": ["x" * 1001]},
            },
        ],
    )
    def test_invalid_messages_are_rejected(self, payload):
        created = self._create_conversation()

        response = self.client.post(
            f"/build/conversations/{created['id']}/messages",
            json=payload,
        )

        assert response.status_code == 422

    def test_messages_for_an_unknown_conversation_are_not_found(self):
        response = self.client.post(
            "/build/conversations/999_999/messages",
            json={"role": "user", "content": "Halo"},
        )

        assert response.status_code == 404

    def test_messages_are_returned_in_chronological_order(self):
        created = self._create_conversation()

        for index in range(3):
            for role in ("user", "assistant"):
                self.client.post(
                    f"/build/conversations/{created['id']}/messages",
                    json={
                        "role": role,
                        "content": _cpu_message_content(index)
                        if role == "user"
                        else _assistant_message_content(index),
                    },
                )

        response = self.client.get(
            f"/build/conversations/{created['id']}/messages"
        )

        assert response.status_code == 200
        messages = response.json()
        assert [message["role"] for message in messages] == [
            "user",
            "assistant",
        ] * 3
        assert [message["content"] for message in messages] == [
            _cpu_message_content(0),
            _assistant_message_content(0),
            _cpu_message_content(1),
            _assistant_message_content(1),
            _cpu_message_content(2),
            _assistant_message_content(2),
        ]
        assert [message["id"] for message in messages] == sorted(
            message["id"] for message in messages
        )

    def test_appending_updates_the_conversation_timestamp(self):
        created = self._create_conversation()
        conversation_id = created["id"]

        response = self.client.post(
            f"/build/conversations/{conversation_id}/messages",
            json={"role": "user", "content": "Apakah build ini konsisten?"},
        )

        assert response.status_code == 201
        stored = self.client.get(
            f"/build/conversations/{conversation_id}"
        ).json()
        assert stored["id"] == conversation_id
        assert stored["created_at"] == created["created_at"]
        assert datetime.fromisoformat(
            stored["updated_at"]
        ) >= datetime.fromisoformat(created["updated_at"])

    def test_a_turn_stores_the_question_and_the_answer_together(self):
        created = self._create_conversation()

        response = self.client.post(
            f"/build/conversations/{created['id']}/turn",
            json={
                "question": "  Bagaimana karakter build ini?  ",
                "answer": "  Karikernya didominasi komponen yang tersedia.  ",
                "evidence": {"known_facts": ["CPU 6 cores / 12 threads."]},
                "analysis": {"strengths": ["Multi-core tersimpan."]},
            },
        )

        assert response.status_code == 201
        turn = response.json()
        assert turn["conversation_id"] == created["id"]
        assert turn["user_message"]["role"] == "user"
        assert turn["user_message"]["content"] == "Bagaimana karakter build ini?"
        assert turn["user_message"]["evidence"] is None
        assert turn["user_message"]["analysis"] is None
        assert turn["assistant_message"]["role"] == "assistant"
        assert turn["assistant_message"]["content"] == (
            "Karikernya didominasi komponen yang tersedia."
        )
        assert turn["assistant_message"]["evidence"]["known_facts"] == [
            "CPU 6 cores / 12 threads."
        ]
        assert turn["assistant_message"]["analysis"]["strengths"] == [
            "Multi-core tersimpan."
        ]

        history = self.client.get(
            f"/build/conversations/{created['id']}/messages"
        ).json()
        assert [message["role"] for message in history] == [
            "user",
            "assistant",
        ]

    @pytest.mark.parametrize(
        "payload",
        [
            {"question": "Bagaimana?", "answer": "Jawaban.", "extra": 1},
            {"question": "Bagaimana?", "answer": "Jawaban.", "analysis": {"nope": []}},
            {"question": "x" * 2001, "answer": "Jawaban."},
        ],
    )
    def test_invalid_turns_are_rejected(self, payload):
        created = self._create_conversation()

        response = self.client.post(
            f"/build/conversations/{created['id']}/turn",
            json=payload,
        )

        assert response.status_code == 422

    def test_a_turn_for_an_unknown_conversation_is_not_found(self):
        response = self.client.post(
            "/build/conversations/999_999/turn",
            json={"question": "Bagaimana?", "answer": "Jawaban."},
        )

        assert response.status_code == 404

    def test_build_identities_keep_separate_histories(self):
        first = self._create_conversation()
        second = self._create_conversation(gpu_id=self.gpu_id_other)

        self.client.post(
            f"/build/conversations/{first['id']}/turn",
            json={
                "question": "Bagaimana karakter build pertama?",
                "answer": "Jawaban pertama.",
            },
        )
        self.client.post(
            f"/build/conversations/{second['id']}/turn",
            json={
                "question": "Bagaimana karakter build kedua?",
                "answer": "Jawaban kedua.",
            },
        )

        first_history = self.client.get(
            f"/build/conversations/{first['id']}/messages"
        ).json()
        second_history = self.client.get(
            f"/build/conversations/{second['id']}/messages"
        ).json()

        assert [
            message["content"] for message in first_history
        ] == [
            "Bagaimana karakter build pertama?",
            "Jawaban pertama.",
        ]
        assert [
            message["content"] for message in second_history
        ] == [
            "Bagaimana karakter build kedua?",
            "Jawaban kedua.",
        ]

    def test_a_reset_clears_the_stored_history_and_keeps_the_build(self):
        created = self._create_conversation()
        conversation_id = created["id"]
        self.client.post(
            f"/build/conversations/{conversation_id}/turn",
            json={"question": "Bagaimana?", "answer": "Jawaban."},
        )

        response = self.client.post(
            f"/build/conversations/{conversation_id}/reset"
        )

        assert response.status_code == 200
        assert response.json()["id"] == conversation_id
        assert response.json()["cpu_hardware_id"] == self.cpu_id
        assert response.json()["gpu_hardware_id"] == self.gpu_id
        assert self.client.get(
            f"/build/conversations/{conversation_id}/messages"
        ).json() == []
        assert self.client.get(
            f"/build/conversations/{conversation_id}"
        ).json() == response.json()
        assert self._create_conversation()["id"] == conversation_id

    def test_a_reset_for_an_unknown_conversation_is_not_found(self):
        response = self.client.post("/build/conversations/999_999/reset")

        assert response.status_code == 404

    def test_history_survives_a_separate_database_session(self):
        created = self._create_conversation()
        conversation_id = created["id"]
        self.client.post(
            f"/build/conversations/{conversation_id}/turn",
            json={
                "question": "Apakah build ini konsisten?",
                "answer": "Karikernya konsisten.",
                "evidence": {"known_facts": ["CPU 6 cores / 12 threads."]},
            },
        )

        other_session_factory = sessionmaker(bind=self.engine)
        build_conversation_service.SessionLocal = other_session_factory

        conversation = build_conversation_service.get_conversation(
            conversation_id
        )
        messages = build_conversation_service.list_messages(conversation_id)

        assert conversation.id == conversation_id
        assert [message.role.value for message in messages] == [
            "user",
            "assistant",
        ]
        assert messages[1].evidence.known_facts == [
            "CPU 6 cores / 12 threads."
        ]

        with other_session_factory() as session:
            assert session.query(BuildConversation).count() == 1
            assert session.query(BuildMessage).count() == 2

    def test_persisting_a_conversation_does_not_change_hardware_data(self):
        created = self._create_conversation()
        self.client.post(
            f"/build/conversations/{created['id']}/turn",
            json={"question": "Bagaimana?", "answer": "Jawaban."},
        )

        with self.session_factory() as session:
            assert session.query(Hardware).count() == 4

    def test_build_chat_behavior_is_unchanged_by_persistence(self):
        build_chat_service.generate_build_chat_answer = lambda request: (
            _response(
                "Karikernya didominasi komponen yang tersedia.",
                known_facts=["CPU 6 cores / 12 threads."],
                unknown=["FPS pada 1440p."],
                analysis={"data_gaps": ["Benchmark GPU."]},
            )
        )
        created = self._create_conversation()

        response = self.client.post(
            "/build/chat",
            json={
                "build": {
                    "cpu": {"id": self.cpu_id, "name": "AMD Ryzen 5 5600"},
                    "gpu": {
                        "id": self.gpu_id,
                        "name": "NVIDIA GeForce RTX 5070 Ti",
                    },
                },
                "question": "Bagaimana karakter build ini?",
            },
        )

        assert response.status_code == 200
        assert response.json()["analysis"]["data_gaps"] == ["Benchmark GPU."]
        assert self.client.get(
            f"/build/conversations/{created['id']}/messages"
        ).json() == []

    def test_build_chat_history_stays_bounded(self):
        created = self._create_conversation()
        messages = [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": _assistant_message_content(index),
            }
            for index in range(12)
        ]

        response = self.client.post(
            "/build/chat",
            json={
                "build": {
                    "cpu": {"id": self.cpu_id, "name": "AMD Ryzen 5 5600"},
                    "gpu": {
                        "id": self.gpu_id,
                        "name": "NVIDIA GeForce RTX 5070 Ti",
                    },
                },
                "messages": messages,
                "question": "Bagaimana karakter build ini?",
            },
        )

        assert response.status_code == 422
        assert self.client.get(
            f"/build/conversations/{created['id']}/messages"
        ).json() == []

    def test_build_chat_history_message_length_stays_bounded(self):
        response = self.client.post(
            "/build/chat",
            json={
                "build": {
                    "cpu": {"id": self.cpu_id, "name": "AMD Ryzen 5 5600"},
                    "gpu": {
                        "id": self.gpu_id,
                        "name": "NVIDIA GeForce RTX 5070 Ti",
                    },
                },
                "messages": [
                    {
                        "role": "user",
                        "content": "x" * (MAX_HISTORY_MESSAGE_LENGTH + 1),
                    }
                ],
                "question": "Bagaimana karakter build ini?",
            },
        )

        assert response.status_code == 422
