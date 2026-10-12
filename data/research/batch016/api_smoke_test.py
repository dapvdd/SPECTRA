"""Batch 016 backend API smoke tests.

Runs against a *live* uvicorn instance ("--base-url") backed by a disposable
copy of the SPECTRA database, so nothing here can affect the production dataset.
Reads the same disposable DB read-only to discover interesting rows (a CPU with
both Geekbench test types, a GPU, a hardware row with multiple provenance
records, a CPU with specs but no provenance).

Writes _api_smoke_result.json and exits non-zero if any check fails.
"""

import argparse
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "_api_smoke_result.json"

CHECKS = []


def record(name, passed, detail=""):
    CHECKS.append({"name": name, "passed": bool(passed), "detail": str(detail)})


def call(base_url, method, path, body=None):
    url = f"{base_url}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return error.code, parsed


def db_lookup(db_path):
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    def one(sql):
        return con.execute(sql).fetchone()[0]

    bench_cpu = one(
        "SELECT hardware_id FROM benchmark_results GROUP BY hardware_id "
        "HAVING COUNT(DISTINCT test_type) = 2 LIMIT 1"
    )
    multi = con.execute(
        "SELECT hardware_id, table_name, field_name, COUNT(*) AS n "
        "FROM field_provenance WHERE benchmark_result_id IS NULL "
        "GROUP BY hardware_id, table_name, field_name HAVING n > 1 LIMIT 1"
    ).fetchone()
    info = {
        "bench_cpu": bench_cpu,
        "any_cpu": one("SELECT id FROM hardware WHERE type='CPU' LIMIT 1"),
        "any_gpu": one("SELECT id FROM hardware WHERE type='GPU' LIMIT 1"),
        "no_bench_gpu": one(
            "SELECT id FROM hardware WHERE type='GPU' AND id NOT IN "
            "(SELECT DISTINCT hardware_id FROM benchmark_results) LIMIT 1"
        ),
        "no_spec_prov_cpu": one(
            "SELECT cs.hardware_id FROM cpu_specifications cs WHERE NOT EXISTS ("
            " SELECT 1 FROM field_provenance fp WHERE fp.hardware_id = cs.hardware_id"
            " AND fp.benchmark_result_id IS NULL) LIMIT 1"
        ),
        "benchmark_id": one("SELECT id FROM benchmark_results ORDER BY id LIMIT 1"),
        "multi_prov_hardware": multi["hardware_id"] if multi else None,
        "multi_prov_table": multi["table_name"] if multi else None,
        "multi_prov_field": multi["field_name"] if multi else None,
        "multi_prov_count": multi["n"] if multi else 0,
        "totals": {
            "hardware": one("SELECT COUNT(*) FROM hardware"),
            "cpu": one("SELECT COUNT(*) FROM hardware WHERE type='CPU'"),
            "gpu": one("SELECT COUNT(*) FROM hardware WHERE type='GPU'"),
            "sources": one("SELECT COUNT(*) FROM sources"),
        },
    }
    con.close()
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--db",
        default=r"C:\Users\user\AppData\Local\Temp\opencode\spectra_b016.db",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    ids = db_lookup(args.db)

    # ---- Service health -------------------------------------------------
    status, body = call(base, "GET", "/health")
    record("health", status == 200 and body.get("status") == "healthy", f"{status} {body}")
    status, body = call(base, "GET", "/")
    record("root_online", status == 200 and body.get("status") == "online", f"{status}")

    # ---- Hardware catalog ----------------------------------------------
    status, hardware = call(base, "GET", "/hardware")
    record(
        "hardware_list_count",
        status == 200 and len(hardware) == ids["totals"]["hardware"],
        f"{status} n={len(hardware)} expected={ids['totals']['hardware']}",
    )
    record(
        "hardware_row_schema",
        all(set(h) == {"id", "name", "manufacturer", "type"} for h in hardware),
        "id/name/manufacturer/type",
    )
    cpu_only = [h for h in hardware if h["type"] == "CPU"]
    gpu_only = [h for h in hardware if h["type"] == "GPU"]
    record(
        "hardware_type_counts",
        len(cpu_only) == ids["totals"]["cpu"] and len(gpu_only) == ids["totals"]["gpu"],
        f"cpu={len(cpu_only)} gpu={len(gpu_only)}",
    )
    status, body = call(base, "GET", "/hardware?type=CPU")
    record(
        "hardware_filter_cpu",
        status == 200 and len(body) == ids["totals"]["cpu"] and all(h["type"] == "CPU" for h in body),
        f"{status} n={len(body)}",
    )
    status, body = call(base, "GET", "/hardware?type=GPU")
    record(
        "hardware_filter_gpu",
        status == 200 and len(body) == ids["totals"]["gpu"] and all(h["type"] == "GPU" for h in body),
        f"{status} n={len(body)}",
    )
    status, body = call(base, "GET", "/hardware?type=Bogus")
    record("hardware_filter_unknown_empty", status == 200 and body == [], f"{status} {body}")

    # ---- Hardware detail ------------------------------------------------
    status, cpu = call(base, "GET", f"/hardware/{ids['any_cpu']}")
    cpu_keys = set(cpu.get("specifications", {})) if isinstance(cpu, dict) else set()
    record(
        "cpu_detail_schema",
        status == 200 and cpu.get("type") == "CPU" and cpu_keys
        == {"cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w", "process_node_nm", "socket"},
        f"{status} keys={sorted(cpu_keys)}",
    )
    status, gpu = call(base, "GET", f"/hardware/{ids['any_gpu']}")
    gpu_keys = set(gpu.get("specifications", {})) if isinstance(gpu, dict) else set()
    record(
        "gpu_detail_schema",
        status == 200 and gpu.get("type") == "GPU" and gpu_keys
        == {"memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz", "vram_bandwidth_gbps", "tdp_w", "interface", "length_mm"},
        f"{status} keys={sorted(gpu_keys)}",
    )
    status, body = call(base, "GET", "/hardware/999999")
    record("missing_hardware_detail_shape", status == 200 and body == {"error": "Hardware not found"}, f"{status} {body}")
    status, body = call(base, "GET", "/hardware/not-an-int")
    record("invalid_hardware_id_422", status == 422, f"{status}")

    # ---- Benchmarks -----------------------------------------------------
    status, benches = call(base, "GET", f"/hardware/{ids['bench_cpu']}/benchmarks")
    types = {row["test_type"] for row in benches} if isinstance(benches, list) else set()
    record(
        "benchmarks_distinguish_test_types",
        status == 200 and types == {"single-core", "multi-core"},
        f"{status} types={sorted(types)}",
    )
    record(
        "benchmark_row_schema",
        isinstance(benches, list)
        and len(benches) > 0
        and all(
            set(row) == {"id", "hardware_id", "benchmark_name", "score", "unit", "test_type", "source", "recorded_at"}
            for row in benches
        )
        and all(row["benchmark_name"] == "Geekbench 7" and row["unit"] == "points" for row in benches),
        f"keys ok, name=Geekbench 7",
    )
    status, single = call(base, "GET", f"/hardware/{ids['bench_cpu']}/benchmarks?test_type=single-core")
    record(
        "benchmark_filter_single_core",
        status == 200 and len(single) >= 1 and all(r["test_type"] == "single-core" for r in single),
        f"{status} n={len(single)}",
    )
    status, multi = call(base, "GET", f"/hardware/{ids['bench_cpu']}/benchmarks?test_type=multi-core")
    record(
        "benchmark_filter_multi_core",
        status == 200 and len(multi) >= 1 and all(r["test_type"] == "multi-core" for r in multi),
        f"{status} n={len(multi)}",
    )
    status, by_source = call(base, "GET", f"/hardware/{ids['bench_cpu']}/benchmarks?source_id=2")
    record(
        "benchmark_filter_source",
        status == 200 and len(by_source) == len(benches) and all(r["source"]["id"] == 2 for r in by_source),
        f"{status} n={len(by_source)}",
    )
    status, by_name = call(
        base,
        "GET",
        f"/hardware/{ids['bench_cpu']}/benchmarks?benchmark_name="
        + urllib.parse.quote("Geekbench 7"),
    )
    record("benchmark_filter_name", status == 200 and len(by_name) == len(benches), f"{status} n={len(by_name)}")
    status, body = call(base, "GET", "/hardware/999999/benchmarks")
    record("benchmarks_missing_hardware_404", status == 404, f"{status} {body}")
    status, benches_gpu = call(base, "GET", f"/hardware/{ids['no_bench_gpu']}/benchmarks")
    record(
        "gpu_no_fabricated_gaming_benchmark",
        status == 200 and benches_gpu == [],
        f"{status} {benches_gpu}",
    )

    # ---- Source transparency -------------------------------------------
    status, sources = call(base, "GET", "/sources")
    vocab = {"clear", "unknown", "restricted", "unresolved"}
    record(
        "sources_list",
        status == 200
        and len(sources) == ids["totals"]["sources"]
        and all(item["license_status"] in vocab for item in sources)
        and all("usage" in item for item in sources),
        f"{status} n={len(sources)}",
    )
    status, src5 = call(base, "GET", "/sources/5")
    record(
        "source_wikipedia_licence",
        status == 200 and src5["license_name"] == "CC BY-SA 4.0" and src5["license_status"] == "clear",
        f"{status} {src5.get('license_name')}",
    )
    status, src4 = call(base, "GET", "/sources/4")
    record(
        "source_gpu_ark_licence",
        status == 200 and src4["license_name"] == "CC BY 4.0" and src4["license_status"] == "clear",
        f"{status} {src4.get('license_name')}",
    )
    status, src1 = call(base, "GET", "/sources/1")
    record(
        "source_restricted_reported",
        status == 200 and sources[0]["license_status"] == "restricted" and src5["license_status"] == "clear",
        f"{status} source1={sources[0]['license_status']}",
    )
    status, body = call(base, "GET", "/sources/999")
    record("source_missing_404", status == 404, f"{status} {body}")

    status, prov = call(base, "GET", f"/hardware/{ids['any_cpu']}/provenance")
    record(
        "hardware_provenance_shape",
        status == 200
        and {"hardware_id", "hardware_name", "hardware_type", "fields", "benchmarks", "summary"} <= set(prov),
        f"{status} keys={sorted(prov) if isinstance(prov, dict) else prov}",
    )
    records_ok = isinstance(prov, dict) and all(
        set(field) == {"table_name", "field_name", "has_value", "status", "records"} for field in prov["fields"]
    )
    record("hardware_provenance_field_shape", records_ok, "table_name/field_name/has_value/status/records")
    record(
        "provenance_summary_counts_match",
        isinstance(prov, dict) and prov["summary"]["total_fields"] == len(prov["fields"]),
        f"total={prov['summary']['total_fields']} fields={len(prov['fields'])}" if isinstance(prov, dict) else "",
    )
    status, body = call(base, "GET", "/hardware/999999/provenance")
    record("hardware_provenance_missing_404", status == 404, f"{status} {body}")

    status, prov_bench = call(base, "GET", f"/benchmarks/{ids['benchmark_id']}/provenance")
    record(
        "benchmark_provenance_payload",
        status == 200
        and {"benchmark_result_id", "hardware_id", "benchmark_name", "score", "source", "records"} <= set(prov_bench),
        f"{status} keys={sorted(prov_bench) if isinstance(prov_bench, dict) else prov_bench}",
    )
    record(
        "benchmark_provenance_has_record",
        status == 200 and len(prov_bench["records"]) >= 1 and prov_bench["records"][0]["field_name"] == "score",
        f"records={len(prov_bench['records']) if isinstance(prov_bench, dict) else '?'}",
    )
    status, body = call(base, "GET", "/benchmarks/999999/provenance")
    record("benchmark_provenance_missing_404", status == 404, f"{status} {body}")

    status, prov_multi = call(base, "GET", f"/hardware/{ids['multi_prov_hardware']}/provenance")
    field = next(
        (
            f
            for f in prov_multi["fields"]
            if f["table_name"] == ids["multi_prov_table"] and f["field_name"] == ids["multi_prov_field"]
        ),
        None,
    )
    record(
        "multiple_provenance_records_per_field",
        status == 200 and field is not None and len(field["records"]) == ids["multi_prov_count"],
        f"records={len(field['records']) if field else 0} expected={ids['multi_prov_count']}",
    )

    status, prov_empty = call(base, "GET", f"/hardware/{ids['no_spec_prov_cpu']}/provenance")
    empties = [f for f in prov_empty["fields"] if not f["records"]]
    record(
        "empty_provenance_reported_honestly",
        status == 200 and len(empties) > 0 and all(f["status"] in {"unattributed", "unavailable"} for f in empties),
        f"{status} empty_fields={len(empties)}",
    )

    # ---- Build & chat ---------------------------------------------------
    status, created = call(
        base,
        "POST",
        "/build/conversations",
        {"cpu_hardware_id": ids["any_cpu"], "gpu_hardware_id": ids["any_gpu"]},
    )
    record(
        "build_conversation_create",
        status in (200, 201) and isinstance(created, dict) and bool(created.get("id")),
        f"{status} {created}",
    )
    conversation_id = created["id"] if isinstance(created, dict) else None
    if conversation_id:
        status, fetched = call(base, "GET", f"/build/conversations/{conversation_id}")
        record(
            "build_conversation_fetch",
            status == 200 and fetched.get("cpu_hardware_id") == ids["any_cpu"],
            f"{status}",
        )
        status, message = call(
            base,
            "POST",
            f"/build/conversations/{conversation_id}/messages",
            {"role": "user", "content": "Batch 016 smoke test message."},
        )
        record("build_message_append", status == 201 and message.get("role") == "user", f"{status}")
        status, messages = call(base, "GET", f"/build/conversations/{conversation_id}/messages")
        record(
            "build_messages_list",
            status == 200 and any(m["content"] == "Batch 016 smoke test message." for m in messages),
            f"{status} n={len(messages)}",
        )
        status, turn = call(
            base,
            "POST",
            f"/build/conversations/{conversation_id}/turn",
            {"question": "Is this a smoke test?", "answer": "Yes."},
        )
        record(
            "build_turn_append",
            status == 201
            and turn.get("user_message", {}).get("content") == "Is this a smoke test?"
            and turn.get("assistant_message", {}).get("content") == "Yes.",
            f"{status}",
        )
        status, reset = call(base, "POST", f"/build/conversations/{conversation_id}/reset")
        record("build_conversation_reset", status == 200, f"{status}")
    else:
        for name in (
            "build_conversation_fetch",
            "build_message_append",
            "build_messages_list",
            "build_turn_append",
            "build_conversation_reset",
        ):
            record(name, False, "no conversation id")

    status, body = call(base, "GET", "/build/conversations/999999")
    record("build_conversation_missing_404", status == 404, f"{status} {body}")

    status, body = call(base, "POST", "/build/chat", {"build": {}, "messages": [], "question": ""})
    record("build_chat_rejects_empty_question", status == 422, f"{status}")
    status, body = call(base, "POST", "/hardware/chat", {"hardware": {}, "question": ""})
    record("hardware_chat_rejects_invalid_payload", status == 422, f"{status}")

    # AI provider reachability is recorded, not asserted (external dependency).
    provider = {}
    status, body = call(
        base, "POST", "/comparison/explanation", {"comparison": {"cpu_a_name": "A", "cpu_b_name": "B"}}
    )
    provider["comparison_explanation_status"] = status
    provider["comparison_explanation_detail"] = body

    status, body = call(
        base,
        "POST",
        "/hardware/chat",
        {
            "hardware": {"id": ids["any_cpu"], "name": "Smoke CPU", "type": "CPU", "specifications": {}, "benchmarks": []},
            "question": "What is this CPU?",
        },
    )
    provider["hardware_chat_status"] = status
    provider["hardware_chat_detail"] = body

    status, body = call(
        base,
        "POST",
        "/build/chat",
        {
            "build": {
                "cpu": {"id": ids["any_cpu"], "name": "Smoke CPU"},
                "gpu": {"id": ids["any_gpu"], "name": "Smoke GPU"},
            },
            "messages": [],
            "question": "Which should I upgrade first?",
        },
    )
    provider["build_chat_status"] = status
    provider["build_chat_detail"] = body

    passed = sum(1 for c in CHECKS if c["passed"])
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "db": args.db,
        "ids": ids,
        "checks": CHECKS,
        "passed": passed,
        "failed": len(CHECKS) - passed,
        "all_passed": passed == len(CHECKS),
        "ai_provider": provider,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for check in CHECKS:
        print(("PASS" if check["passed"] else "FAIL"), check["name"], "-", check["detail"])
    print("\nAI provider: " + json.dumps(provider))
    print(f"\nTOTAL {passed}/{len(CHECKS)} passed -> {OUT}")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
