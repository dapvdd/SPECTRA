# BUILD AI CONTEXT

This document describes the `POST /build/chat` contract, the structured build
context it accepts, and the trust boundary between the SPECTRA frontend and the
SPECTRA backend.

## Purpose

```
CPU detail + GPU detail + user context
        ↓
structured Build AI Context
        ↓
POST /build/chat
        ↓
GeminiProvider (shared with /comparison/explanation and /hardware/chat)
```

The assistant receives structured, factual context. It never receives frontend
prose, and it is instructed to stay inside the supplied evidence.

## Request contract

```
POST /build/chat
```

```json
{
  "build": {
    "cpu": {
      "id": 1,
      "name": "Ryzen 7 7800X3D",
      "manufacturer": "AMD",
      "type": "CPU",
      "architecture": "Zen 4",
      "release_date": "2023-04-06",
      "specifications": {
        "cores": 8,
        "threads": 16,
        "base_clock_ghz": 4.2,
        "boost_clock_ghz": 5.0,
        "tdp_w": 120.0,
        "process_node_nm": 5.0,
        "socket": "AM5"
      },
      "benchmarks": [
        {
          "id": 7,
          "hardware_id": 1,
          "benchmark_name": "Geekbench 7",
          "test_type": "single-core",
          "score": 2100.0,
          "unit": "points",
          "source": null,
          "recorded_at": null
        }
      ]
    },
    "gpu": {
      "id": 2,
      "name": "GeForce RTX 5070 Ti",
      "manufacturer": "NVIDIA",
      "type": "GPU",
      "architecture": "Blackwell",
      "release_date": "2025-02-27",
      "specifications": {
        "memory_gb": 16.0,
        "memory_type": "GDDR7",
        "core_clock_mhz": 2017.0,
        "boost_clock_mhz": 2512.0,
        "vram_bandwidth_gbps": 896.0,
        "tdp_w": 300.0,
        "interface": "PCIe 5.0 x16",
        "length_mm": 300.0
      },
      "benchmarks": []
    },
    "context": {
      "use_case": "gaming",
      "resolution": "1440p"
    }
  },
  "question": "Bagaimana karakter build ini untuk gaming 1440p?"
}
```

Response:

```json
{ "answer": "..." }
```

## Field rules

| Field | Rule |
| --- | --- |
| `build.cpu`, `build.gpu` | Both are required. CPU-only and GPU-only builds are rejected. |
| `type` | Fixed per slot: `Literal["CPU"]` for the CPU slot, `Literal["GPU"]` for the GPU slot. A GPU record cannot be sent as the CPU component. |
| `specifications` | Explicit field whitelist per component. Unknown keys are rejected. |
| `benchmarks` | Explicit field whitelist. An empty list is valid and expected. |
| `specifications.*`, `name` | Null and missing are preserved as unknown. They are never coerced to `0` and never inferred. |
| `context.use_case` | `gaming`, `productivity`, `ai_compute`, `general`, `unspecified`. |
| `context.resolution` | `unspecified`, `1080p`, `1440p`, `4k`. |
| `question` | Free-form user content. Trimmed, non-blank, 1-2000 characters. |
| extra fields | Rejected everywhere (`extra="forbid"`). |

The frontend maps its display labels to the machine vocabulary:
`"AI / Compute"` → `ai_compute`, `"4K"` → `4k`, `"Not specified"` → `unspecified`.
Unknown values fall back to `unspecified`; arbitrary user strings are never sent
for these two fields.

## Benchmark rule

GPU benchmark results in SPECTRA are currently zero. Therefore:

- The GPU benchmark list is serialized as `[]`.
- No benchmark record is ever created, inferred, or substituted for a GPU.
- No GPU FPS, GPU score, or GPU performance number exists in the context.
- CPU benchmark records are passed through only when SPECTRA already holds them.

A missing benchmark list and an empty benchmark list are both valid and are not
the same as a zero score.

## Trust boundary

The build context is supplied by the client and is **not** treated as trusted
database truth. SPECTRA validates structure, not provenance.

In scope for this contract:

- The backend validates the full schema and rejects unknown fields.
- The backend rejects malformed values, wrong component types, and invalid
  context vocabulary.
- `build` is serialized as JSON data. `question` is user content. The two are
  never merged into one free-form prompt field, so frontend-supplied strings
  cannot become system instructions.
- The system instruction is fixed on the server and is never influenced by
  request data.
- There is no database lookup. Component identity (`id`) is recorded, not
  verified, in this sprint.

Explicitly out of scope:

- Verifying that a client-supplied `id`, name, or specification matches the
  database record.
- Any score, FPS, bottleneck, PSU, thermal, or price computation.

If a future sprint requires verified component identity, the contract should be
changed so the backend resolves `id` against `hardware` and `*_specification`
rows instead of trusting the client payload.

## Provider reuse

`POST /build/chat` reuses the single `GeminiProvider` from
`backend/app/services/explanation_service.py`. It inherits API key handling,
model configuration, the 30 second timeout, the retry policy for transient HTTP
and network failures, redacted logging, and provider error mapping.

| Condition | HTTP status |
| --- | --- |
| Schema or vocabulary violation | 422 |
| `ProviderError` (provider failed, invalid, or empty response) | 502 |
| `ProviderUnavailableError` (missing API key or model) | 503 |

## Explicitly unsupported claims

The system instruction forbids the assistant from introducing any of the
following, because SPECTRA does not hold the evidence:

- Build scores or composite ratings.
- FPS, frame-time, or application timings.
- Bottleneck percentages or CPU/GPU balance ratios.
- PSU sizing or power supply recommendations.
- Temperature or thermal predictions.
- Price optimization.
- Automatic hardware recommendations.
- Motherboard, PSU, case, cooling, RAM, or PCIe compatibility claims.
- Treating a sum of listed TDP values as measured system power draw.
