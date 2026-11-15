"""M2.5 Task 5: verified six-component compatibility context for build chat.

Contracts:
- ``BuildContext.compatibility`` is optional; existing CPU/GPU payloads
  validate unchanged (regression).
- The digest is bounded: at most one aggregate state, at most one entry per
  rule result (bounded count), bounded strings, bounded slot summary.
- The digest is a pass-through of SPECTRA-computed facts — the service
  never derives compatibility itself, never invents rules.
- When a build is INCOMPATIBLE, the prompt rules must make it impossible to
  present the build as ready, and the incompatible rules must be named.
- The prompt payload includes the compatibility digest when supplied.
- Chat remains CPU/GPU-scoped for conversation identity; the digest travels
  per-request and must not alter the conversation token in any way.
"""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import main
from backend.app.schemas.build_chat import (
    MAX_COMPATIBILITY_RULE_RESULTS,
    BuildCompatibilityDigest,
    BuildContext,
    BuildHardwareChatRequest,
)
from backend.app.services import build_chat_service, explanation_service


def _cpu_payload(**overrides):
    payload = {
        "id": 123,
        "name": "AMD Ryzen 5 5600",
        "manufacturer": "AMD",
        "type": "CPU",
        "specifications": {"cores": 6, "threads": 12, "tdp_w": 65, "socket": "AM4"},
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
        "specifications": {"memory_gb": 16, "tdp_w": 300, "interface": "PCIe 5.0 x16"},
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
    payload = {"build": build, "question": "Is this build ready to use?"}
    payload.update(overrides)
    return payload


def _incompatible_digest():
    return {
        "aggregate_state": "INCOMPATIBLE",
        "rule_results": [
            {
                "rule_id": "cpu-motherboard-socket",
                "state": "INCOMPATIBLE",
                "explanation": (
                    "CPU socket AM4 does not match motherboard socket AM5."
                ),
            }
        ],
        "unresolved": [
            "psu-build-wattage: listed TDP is not recorded for gpu_specifications.tdp_w"
        ],
        "slots": {
            "cpu": 123,
            "gpu": 456,
            "motherboard": 789,
        },
    }


class TestBuildContextSchema:
    def test_context_without_digest_validates_unchanged(self):
        context = BuildContext.model_validate(
            {
                "cpu": _cpu_payload(),
                "gpu": _gpu_payload(),
                "context": {"use_case": "gaming", "resolution": "1440p"},
            }
        )

        assert context.compatibility is None

    def test_context_accepts_bounded_digest(self):
        context = BuildContext.model_validate(
            {
                "cpu": _cpu_payload(),
                "gpu": _gpu_payload(),
                "compatibility": _incompatible_digest(),
            }
        )

        digest = context.compatibility
        assert digest.aggregate_state == "INCOMPATIBLE"
        assert digest.rule_results[0].rule_id == "cpu-motherboard-socket"
        assert digest.unresolved[0].startswith("psu-build-wattage:")
        assert digest.slots["cpu"] == 123

    def test_context_rejects_unbounded_rule_results(self):
        payload = _incompatible_digest()
        payload["rule_results"] = [
            {
                "rule_id": f"rule-{index}",
                "state": "UNKNOWN",
                "explanation": "x",
            }
            for index in range(MAX_COMPATIBILITY_RULE_RESULTS + 1)
        ]

        with pytest.raises(ValidationError):
            BuildContext.model_validate(
                {
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": payload,
                }
            )

    def test_digest_rejects_unknown_aggregate_state(self):
        payload = _incompatible_digest()
        payload["aggregate_state"] = "MAYBE"

        with pytest.raises(ValidationError):
            BuildContext.model_validate(
                {
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": payload,
                }
            )

    def test_digest_rejects_unbounded_strings(self):
        payload = _incompatible_digest()
        payload["rule_results"][0]["explanation"] = "x" * 601

        with pytest.raises(ValidationError):
            BuildContext.model_validate(
                {
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": payload,
                }
            )

    def test_digest_rule_state_must_be_a_compatibility_state(self):
        payload = _incompatible_digest()
        payload["rule_results"][0]["state"] = "EXCELLENT"

        with pytest.raises(ValidationError):
            BuildContext.model_validate(
                {
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": payload,
                }
            )


class TestPromptPayload:
    def setup_method(self):
        self.original = explanation_service.generate_chat_response

    def teardown_method(self):
        explanation_service.generate_chat_response = self.original

    def _capture(self):
        captured = {}

        def generate(system_prompt, user_text):
            captured["system_prompt"] = system_prompt
            captured["user_text"] = user_text
            return json.dumps(
                {
                    "answer": "ok",
                    "evidence": {"known_facts": [], "interpretation": [], "unknown": []},
                    "analysis": {"strengths": [], "considerations": [], "data_gaps": []},
                }
            )

        explanation_service.generate_chat_response = generate
        return captured

    def test_prompt_payload_includes_digest_when_supplied(self):
        captured = self._capture()
        request = BuildHardwareChatRequest.model_validate(
            _build_payload(
                build={
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": _incompatible_digest(),
                }
            )
        )

        build_chat_service.generate_build_chat_answer(request)

        context = json.loads(captured["user_text"])
        assert context["build"]["compatibility"]["aggregate_state"] == "INCOMPATIBLE"
        assert context["build"]["compatibility"]["rule_results"][0]["rule_id"] == (
            "cpu-motherboard-socket"
        )

    def test_prompt_payload_keeps_digest_key_null_when_absent(self):
        captured = self._capture()
        request = BuildHardwareChatRequest.model_validate(_build_payload())

        build_chat_service.generate_build_chat_answer(request)

        context = json.loads(captured["user_text"])
        assert context["build"]["compatibility"] is None

    def test_prompt_names_incompatible_builds_and_forbids_ready_claims(self):
        captured = self._capture()
        request = BuildHardwareChatRequest.model_validate(
            _build_payload(
                build={
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": _incompatible_digest(),
                }
            )
        )

        build_chat_service.generate_build_chat_answer(request)

        normalized_prompt = " ".join(captured["system_prompt"].split())
        for phrase in (
            "compatibility summary",
            "INCOMPATIBLE",
            "never describe",
            "ready to use",
            "ready to build",
        ):
            assert phrase in normalized_prompt, phrase

    def test_unresolved_checks_are_prompt_payload_members(self):
        captured = self._capture()
        request = BuildHardwareChatRequest.model_validate(
            _build_payload(
                build={
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": _incompatible_digest(),
                }
            )
        )

        build_chat_service.generate_build_chat_answer(request)

        context = json.loads(captured["user_text"])
        unresolved = context["build"]["compatibility"]["unresolved"]
        assert any("psu-build-wattage" in item for item in unresolved)


class TestApiLevel:
    def setup_method(self):
        self.client = TestClient(main.app)
        self.original = build_chat_service.generate_build_chat_answer

    def teardown_method(self):
        build_chat_service.generate_build_chat_answer = self.original

    def test_api_accepts_digest_and_returns_answer(self):
        build_chat_service.generate_build_chat_answer = lambda request: (
            build_chat_service.parse_build_chat_response(
                json.dumps(
                    {
                        "answer": "Build is not ready.",
                        "evidence": {
                            "known_facts": [],
                            "interpretation": [],
                            "unknown": [],
                        },
                        "analysis": {"strengths": [], "considerations": [], "data_gaps": []},
                    }
                )
            )
        )

        response = self.client.post(
            "/build/chat",
            json=_build_payload(
                build={
                    "cpu": _cpu_payload(),
                    "gpu": _gpu_payload(),
                    "compatibility": _incompatible_digest(),
                }
            ),
        )

        assert response.status_code == 200
        assert response.json()["answer"] == "Build is not ready."

    def test_api_rejects_malformed_digest_with_422(self):
        payload = _build_payload(
            build={
                "cpu": _cpu_payload(),
                "gpu": _gpu_payload(),
                "compatibility": {"aggregate_state": "TOTALLY_SHILL"},
            }
        )

        response = self.client.post("/build/chat", json=payload)

        assert response.status_code == 422
