"""M4 Task 8: AI digest in build chat (rules 43-45 + intelligence payload).

Covers:
- build_prompt_payload includes "intelligence" when components are selected
- intelligence key is omitted (not null) when no component is selected
- SYSTEM_PROMPT carries rules 43-45 (digest authority + absent-digest rule)
- rule text binds the assistant to the engine outputs; no new claims
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.schemas.build_chat import (
    BuildBenchmarkContext,
    BuildCpuContext,
    BuildCpuSpecifications,
    BuildGpuContext,
    BuildGpuSpecifications,
    BuildHardwareChatRequest,
)
from backend.app.services import build_chat_service


def _cpu_context(cpu_id=None):
    return BuildCpuContext(
        id=cpu_id,
        name="CPU A" if cpu_id else None,
        specifications=BuildCpuSpecifications(
            cores=8, threads=16, base_clock_ghz=3.0, boost_clock_ghz=4.4,
            tdp_w=65.0,
        ),
        benchmarks=[
            BuildBenchmarkContext(
                benchmark_name="Geekbench 7", test_type="multi-core",
                score=9000.0, unit="points",
            ),
        ],
    )


def _request(cpu_id=None, gpu_id=None, question="Is this build good?"):
    """Build a chat request. The build-chat contract requires cpu and gpu
    context objects, so a "no component" request keeps the shells with
    ids unset — the digest layer must treat id-less contexts as
    unselected (no intelligence digest emitted)."""
    cpu = _cpu_context(cpu_id if cpu_id else 101)
    gpu = BuildGpuContext(
        id=gpu_id if gpu_id else 300,
        name="GPU B",
        specifications=BuildGpuSpecifications(
            memory_gb=16.0, memory_type="GDDR6X", tdp_w=250.0,
        ),
        benchmarks=[],
    )
    if cpu_id is None:
        cpu = cpu.model_copy(update={"id": None, "name": "CPU A"})
    if gpu_id is None:
        gpu = gpu.model_copy(update={"id": None})
    return BuildHardwareChatRequest(
        build={"cpu": cpu, "gpu": gpu},
        messages=[],
        question=question,
    )


def test_rules_43_45_present_in_system_prompt():
    prompt = build_chat_service.SYSTEM_PROMPT
    for marker in ("43.", "44.", "45."):
        assert marker in prompt
    assert "intelligence" in prompt


def test_rule_43_binds_digest_as_authoritative():
    prompt = build_chat_service.SYSTEM_PROMPT
    rule43 = prompt.split("43.")[1].split("44.")[0].lower()
    assert "authoritative" in rule43 or "spectra fact" in rule43


def test_rule_45_handles_absent_digest():
    prompt = build_chat_service.SYSTEM_PROMPT
    rule45 = prompt.split("45.")[1][:600].lower()
    assert "absent" in rule45 or "not supplied" in rule45


def test_prompt_payload_includes_intelligence_with_components():
    request_data = _request(cpu_id=101, gpu_id=300)
    payload = json.loads(build_chat_service.build_prompt_payload(request_data))
    # the digest rides inside build.intelligence (alongside compatibility)
    assert "intelligence" in payload["build"]
    intel = payload["build"]["intelligence"]
    assert "scenario_scores" in intel
    assert "build_intelligence" in intel
    # scenario scores ride per component (cpu present)
    assert intel["scenario_scores"].get("cpu") is not None


def test_prompt_payload_omits_intelligence_without_components():
    request_data = _request(cpu_id=None, gpu_id=None)
    payload = json.loads(build_chat_service.build_prompt_payload(request_data))
    assert "intelligence" not in payload["build"]
