import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import main
from backend.app.schemas.build_chat import (
    MAX_ANALYSIS_ITEM_LENGTH,
    MAX_ANALYSIS_ITEMS,
    MAX_EVIDENCE_ITEMS,
    BuildAnalysis,
    BuildHardwareChatResponse,
)
from backend.app.services import build_chat_service, explanation_service


ANALYSIS_SECTIONS = ["strengths", "considerations", "data_gaps"]


def _cpu_payload(**overrides):
    payload = {
        "id": 123,
        "name": "AMD Ryzen 5 5600",
        "manufacturer": "AMD",
        "type": "CPU",
        "architecture": "Zen 3",
        "release_date": "2022-04-04",
        "specifications": {
            "cores": 6,
            "threads": 12,
            "base_clock_ghz": 3.5,
            "boost_clock_ghz": 4.4,
            "tdp_w": 65,
            "process_node_nm": 7,
            "socket": "AM4",
        },
        "benchmarks": [],
    }
    payload.update(overrides)
    return payload


def _gpu_payload(**overrides):
    payload = {
        "id": 456,
        "name": "NVIDIA GeForce RTX 5070 Ti",
        "manufacturer": "NVIDIA",
        "type": "GPU",
        "architecture": "Blackwell",
        "release_date": "2025-02-27",
        "specifications": {
            "memory_gb": 16,
            "memory_type": "GDDR7",
            "core_clock_mhz": 2017,
            "boost_clock_mhz": 2512,
            "vram_bandwidth_gbps": 896,
            "tdp_w": 300,
            "interface": "PCIe 5.0 x16",
            "length_mm": 300,
        },
        "benchmarks": [],
    }
    payload.update(overrides)
    return payload


def _build_payload(**overrides):
    build = {
        "cpu": _cpu_payload(),
        "gpu": _gpu_payload(),
        "context": {"use_case": "gaming", "resolution": "1440p"},
    }
    build.update(overrides.pop("build", {}))
    payload = {"build": build, "question": "Apa yang diketahui dari build ini?"}
    payload.update(overrides)
    return payload


def _structured(answer="Analisis berbasis data tersimpan.", analysis=None, **evidence):
    return {
        "answer": answer,
        "evidence": {
            "known_facts": evidence.get("known_facts", []),
            "interpretation": evidence.get("interpretation", []),
            "unknown": evidence.get("unknown", []),
        },
        "analysis": (
            {
                "strengths": analysis.get("strengths", []),
                "considerations": analysis.get("considerations", []),
                "data_gaps": analysis.get("data_gaps", []),
            }
            if analysis is not None
            else None
        ),
    }


def _valid_analysis():
    return {
        "strengths": [
            "CPU 6 cores / 12 threads mendukung karakter multi-threaded."
        ],
        "considerations": [
            "Data yang tersedia tidak memuat FPS aktual pada game tertentu."
        ],
        "data_gaps": ["Benchmark GPU untuk GPU yang dipilih belum tersedia."],
    }


class TestBuildAnalysisResponse:
    def setup_method(self):
        self.client = TestClient(main.app)
        self.original = build_chat_service.generate_build_chat_answer

    def teardown_method(self):
        build_chat_service.generate_build_chat_answer = self.original

    def _accept(self, provider_text):
        build_chat_service.generate_build_chat_answer = lambda request: (
            build_chat_service.parse_build_chat_response(provider_text)
        )
        return self.client.post("/build/chat", json=_build_payload())

    def test_valid_analysis_is_returned_with_the_response(self):
        response = self._accept(
            json.dumps(
                _structured(
                    known_facts=["CPU 6 cores / 12 threads."],
                    analysis=_valid_analysis(),
                )
            )
        )

        assert response.status_code == 200
        assert response.json() == {
            "answer": "Analisis berbasis data tersimpan.",
            "evidence": {
                "known_facts": ["CPU 6 cores / 12 threads."],
                "interpretation": [],
                "unknown": [],
            },
            "analysis": _valid_analysis(),
        }

    def test_empty_analysis_arrays_are_valid(self):
        response = self._accept(json.dumps(_structured(analysis={})))

        assert response.status_code == 200
        assert response.json()["analysis"] == {
            "strengths": [],
            "considerations": [],
            "data_gaps": [],
        }

    def test_missing_analysis_is_rejected(self):
        payload = _structured(analysis=_valid_analysis())
        payload.pop("analysis")
        response = self._accept(json.dumps(payload))

        assert response.status_code == 502
        assert response.json() == {"detail": "The AI provider returned an invalid response."}

    def test_null_analysis_is_rejected(self):
        response = self._accept(json.dumps(_structured(analysis=None)))

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_exactly_max_items_are_accepted(self, section):
        payload = _structured(analysis={section: [f"item {i}" for i in range(MAX_ANALYSIS_ITEMS)]})
        response = self._accept(json.dumps(payload))

        assert response.status_code == 200
        assert len(response.json()["analysis"][section]) == MAX_ANALYSIS_ITEMS

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_more_than_max_items_are_rejected(self, section):
        payload = _structured(
            analysis={section: [f"item {i}" for i in range(MAX_ANALYSIS_ITEMS + 1)]}
        )
        response = self._accept(json.dumps(payload))

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_items_exactly_at_the_character_bound_are_accepted(self, section):
        payload = _structured(analysis={section: ["x" * MAX_ANALYSIS_ITEM_LENGTH]})
        response = self._accept(json.dumps(payload))

        assert response.status_code == 200

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_items_longer_than_the_character_bound_are_rejected(self, section):
        payload = _structured(
            analysis={section: ["x" * (MAX_ANALYSIS_ITEM_LENGTH + 1)]}
        )
        response = self._accept(json.dumps(payload))

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_empty_items_are_rejected(self, section):
        response = self._accept(json.dumps(_structured(analysis={section: ["   "]}) ))

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_non_string_items_are_rejected(self, section):
        response = self._accept(json.dumps(_structured(analysis={section: [42]})))

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_nested_objects_are_rejected(self, section):
        response = self._accept(
            json.dumps(_structured(analysis={section: [{"value": "object"}]}))
        )

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_non_array_sections_are_rejected(self, section):
        response = self._accept(
            json.dumps(_structured(analysis={section: "bukan array"}))
        )

        assert response.status_code == 502

    @pytest.mark.parametrize("section", ANALYSIS_SECTIONS)
    def test_unexpected_analysis_field_is_rejected(self, section):
        payload = _structured(analysis=_valid_analysis())
        payload["analysis"]["recommendation"] = ["tidak diizinkan"]
        response = self._accept(json.dumps(payload))

        assert response.status_code == 502

    def test_analysis_items_are_trimmed(self):
        response = self._accept(
            json.dumps(_structured(analysis={"strengths": ["  kekuatan.  "]}))
        )

        assert response.status_code == 200
        assert response.json()["analysis"]["strengths"] == ["kekuatan."]

    def test_evidence_contract_still_works_alongside_analysis(self):
        response = self._accept(
            json.dumps(
                _structured(
                    known_facts=["fakta."],
                    interpretation=["interpretasi."],
                    unknown=["tidak diketahui."],
                    analysis=_valid_analysis(),
                )
            )
        )

        assert response.status_code == 200
        assert response.json()["evidence"] == {
            "known_facts": ["fakta."],
            "interpretation": ["interpretasi."],
            "unknown": ["tidak diketahui."],
        }

    def test_evidence_limits_are_unchanged_by_the_analysis_contract(self):
        payload = _structured(analysis=_valid_analysis())
        payload["evidence"]["known_facts"] = [
            f"item {i}" for i in range(MAX_EVIDENCE_ITEMS + 1)
        ]
        response = self._accept(json.dumps(payload))

        assert response.status_code == 502

    def test_malformed_provider_json_is_still_rejected(self):
        response = self._accept('{"answer": "ok", "analysis":')

        assert response.status_code == 502

    def test_fenced_json_with_analysis_is_parsed(self):
        response = self._accept(
            "```json\n"
            + json.dumps(_structured(analysis=_valid_analysis()))
            + "\n```"
        )

        assert response.status_code == 200
        assert response.json()["analysis"] == _valid_analysis()


class TestBuildAnalysisPrompt:
    def setup_method(self):
        self.original_chat = explanation_service.generate_chat_response

    def teardown_method(self):
        explanation_service.generate_chat_response = self.original_chat

    def _capture(self):
        captured = {}

        def generate(system_prompt, user_text):
            captured["system_prompt"] = system_prompt
            captured["user_text"] = user_text
            return json.dumps(_structured(analysis=_valid_analysis()))

        explanation_service.generate_chat_response = generate
        return captured

    def _prompt(self):
        captured = self._capture()
        request = build_chat_service.BuildHardwareChatRequest.model_validate(
            _build_payload()
        )
        build_chat_service.generate_build_chat_answer(request)
        return " ".join(captured["system_prompt"].split())

    def test_prompt_requests_the_analysis_object(self):
        prompt = self._prompt()

        for phrase in (
            "STRENGTHS",
            "CONSIDERATIONS",
            "DATA GAPS",
            '"analysis"',
            '"strengths"',
            '"considerations"',
            '"data_gaps"',
        ):
            assert phrase in prompt, phrase

    def test_prompt_binds_the_analysis_to_the_supplied_evidence(self):
        prompt = self._prompt()

        for phrase in (
            "Analysis is evidence-bounded",
            "must be supported by the supplied",
            "When a measurement is missing, name it as a data gap",
            "An empty analysis list is correct",
        ):
            assert phrase in prompt, phrase

    def test_prompt_forbids_fabricated_performance_numbers(self):
        prompt = self._prompt()

        for phrase in (
            "Never state FPS",
            "bottleneck percentage",
            "PSU requirement",
            "total system power",
            "Never state a bottleneck percentage",
        ):
            assert phrase in prompt, phrase

    def test_analysis_is_never_sent_back_as_build_context(self):
        captured = self._capture()
        request = build_chat_service.BuildHardwareChatRequest.model_validate(
            _build_payload()
        )

        build_chat_service.generate_build_chat_answer(request)

        payload = json.loads(captured["user_text"])
        assert sorted(payload) == ["build", "messages", "question"]
        assert "analysis" not in payload
        assert "evidence" not in payload
        assert "analysis" not in payload["build"]

    def test_history_still_carries_only_message_content(self):
        captured = self._capture()
        request = build_chat_service.BuildHardwareChatRequest.model_validate(
            _build_payload(
                messages=[
                    {"role": "user", "content": "Apa yang diketahui?"},
                    {"role": "assistant", "content": "Spesifikasi."},
                ]
            )
        )

        build_chat_service.generate_build_chat_answer(request)

        payload = json.loads(captured["user_text"])
        assert all(set(message) == {"role", "content"} for message in payload["messages"])


class TestBuildAnalysisSchemaLimits:
    def test_analysis_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            BuildAnalysis.model_validate(
                {
                    "strengths": [],
                    "considerations": [],
                    "data_gaps": [],
                    "score": 90,
                }
            )

    def test_analysis_item_count_limit_is_enforced(self):
        with pytest.raises(ValidationError):
            BuildAnalysis.model_validate(
                {"strengths": [f"item {i}" for i in range(MAX_ANALYSIS_ITEMS + 1)]}
            )

    def test_analysis_item_length_limit_is_enforced(self):
        with pytest.raises(ValidationError):
            BuildAnalysis.model_validate(
                {"data_gaps": ["x" * (MAX_ANALYSIS_ITEM_LENGTH + 1)]}
            )

    def test_blank_analysis_item_is_rejected(self):
        with pytest.raises(ValidationError):
            BuildAnalysis.model_validate({"considerations": ["  "]})

    def test_non_string_analysis_item_is_rejected(self):
        with pytest.raises(ValidationError):
            BuildAnalysis.model_validate({"strengths": [3.5]})

    def test_analysis_item_is_trimmed(self):
        analysis = BuildAnalysis.model_validate({"strengths": ["  workforce.  "]})

        assert analysis.strengths == ["workforce."]

    def test_response_rejects_a_non_object_analysis(self):
        with pytest.raises(ValidationError):
            BuildHardwareChatResponse.model_validate(
                {
                    "answer": "ok",
                    "evidence": {
                        "known_facts": [],
                        "interpretation": [],
                        "unknown": [],
                    },
                    "analysis": ["strengths"],
                }
            )
