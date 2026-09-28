# BUILD AI CONTEXT

This document describes the `POST /build/chat` contract, the structured build
context it accepts, and the trust boundary between the SPECTRA frontend and the
SPECTRA backend.

## Purpose

```
CPU detail + GPU detail + user context
        +
bounded conversation history
+
current question
        ↓
structured Build AI Context
        ↓
POST /build/chat
        ↓
GeminiProvider (shared with /comparison/explanation and /hardware/chat)
```

The assistant receives structured, factual context plus a bounded transcript of the
conversation so far. It never receives frontend prose, and it is instructed to stay
inside the supplied evidence.

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
  "messages": [
    { "role": "user", "content": "Apa yang diketahui dari build ini?" },
    { "role": "assistant", "content": "Spesifikasi CPU dan GPU tersimpan." }
  ],
  "question": "Bagaimana karakter build ini untuk gaming 1440p?"
}
```

Response:

```json
{
  "answer": "...",
  "evidence": {
    "known_facts": ["..."],
    "interpretation": ["..."],
    "unknown": ["..."]
  }
}
```

## Evidence contract

Every answer is classified into exactly three sections so the user can see what
SPECTRA actually knows, what the AI is reasoning about, and what cannot be
concluded.

| Section | Contents |
| --- | --- |
| `known_facts` | Values directly present in the supplied SPECTRA build context. No inference. |
| `interpretation` | Qualitative reasoning that follows from known facts. No invented measurements. |
| `unknown` | Important information that cannot be established from the supplied context. |

| Field rule | Value |
| --- | --- |
| `answer` | Trimmed, non-empty string. |
| `evidence.known_facts`, `.interpretation`, `.unknown` | Array of strings. |
| Items per section | At most 10. |
| Characters per item | At most 1000. |
| Blank items | Rejected. |
| Nested objects | Rejected. |
| Extra keys | Rejected (`extra="forbid"`). |

Evidence priority, highest first: current supplied build context, current supplied
benchmark records, current user context, conversation history, general model
knowledge. General model knowledge is never presented as a SPECTRA fact and is
never silently merged into `known_facts`.

GPU benchmark count in SPECTRA is currently zero, so `known_facts` must not
contain GPU benchmark scores, and `unknown` states measured GPU benchmark data is
not available when relevant. CPU benchmark values appear as known facts only when
that exact record is supplied. The backend strictly validates the structured
response; malformed or non-JSON provider output is a provider failure (502) and is
never rendered raw.

The frontend renders the three evidence fields directly as labelled sections under
each assistant message. They are displayed as plain data strings (no Markdown, no
`dangerouslySetInnerHTML`). Conversation history continues to send only the
`user`/`assistant` text content; evidence is a presentational detail and never
becomes conversation context.

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
| `messages` | Optional. Omitted or `[]` for a first turn. At most 10 entries. |
| `messages[].role` | `user` or `assistant` only. |
| `messages[].content` | Trimmed, non-blank, 1-4000 characters. |
| extra fields | Rejected everywhere (`extra="forbid"`). |

The frontend maps its display labels to the machine vocabulary:
`"AI / Compute"` → `ai_compute`, `"4K"` → `4k`, `"Not specified"` → `unspecified`.
Unknown values fall back to `unspecified`; arbitrary user strings are never sent
for these two fields.

## Conversation history

History is a **bounded transcript**, not an instruction channel.

| Rule | Value |
| --- | --- |
| Maximum messages | 10 |
| Maximum length per message | 4000 characters |
| Allowed roles | `user`, `assistant` |
| Ordering | Strictly alternating, starting with `user` |
| `system`, `developer`, `tool`, `function` | Rejected |
| Blank content | Rejected |
| Extra per-message fields | Rejected |
| Zero messages | Valid |
| Odd length ending in `user` | Valid |

The history is plain conversational text only. Evidence sections attached to an
assistant message are presentational and are excluded from the `messages` payload.

`question` is always separate from `messages`. The current question is never
appended to the history by the client, and a previous turn is never replayed as
the current one.

The frontend keeps the ten **newest** messages and omits the `messages` key
entirely when the conversation has no prior turns, so a first-turn request stays
byte-identical to the pre-history contract.

## Prompt structure

The user turn is a single JSON object with a fixed key order:

```
SYSTEM INSTRUCTION   (fixed on the server, never derived from request data)
BUILD CONTEXT        "build"
CONVERSATION HISTORY "messages"
CURRENT QUESTION     "question"
```

`build`, `messages`, and `question` stay structurally separate inside that object.
History content is never concatenated into the system instruction, so no
client-supplied string can become a system instruction.

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
- Conversation history is data. It is serialized in its own `messages` field,
  never appended to the system instruction, and never promoted into one.
- A previous assistant claim is not evidence. The build context wins on conflict.
- User messages cannot lift an evidence bound or change the assistant's rules.
- The system instruction is fixed on the server and is never influenced by
  request data.
- There is no database lookup. Component identity (`id`) is recorded, not
  verified, in this sprint.
- History is in-memory only. Nothing is persisted and nothing is authenticated.

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
- Repeating an unsupported claim only because it appeared earlier in the
  conversation.

## Client-side conversation rules

| Situation | Behaviour |
| --- | --- |
| Successful turn | `previous messages + user message + assistant answer + evidence sections` becomes the new state. |
| Failed turn | The failed question is not appended, previous messages are preserved, and the question stays available for retry. |
| Retry | Re-asks the pending question against the current build only, without duplicating the failed user message. |
| New conversation | Clears messages, error, pending question, and loading state. Keeps CPU, GPU, use case, and resolution. |
| CPU / GPU / use case / resolution change | Invalidates the conversation: clear messages, clear the pending request, clear the error, return to idle, keep the build. |
| Stale success or failure | Ignored, via `createChatRequestGuard` and the build identity token. |
