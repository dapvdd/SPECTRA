# BUILD AI PERSISTENCE

This document describes the Sprint 17 persistence contract: how a Build AI
conversation is stored in SQLite, how it is bound to a CPU + GPU build identity,
and how the frontend restores it without changing the `POST /build/chat`
contract.

## Purpose

```
CPU detail + GPU detail loaded
        ↓
POST /build/conversations        (create or reuse the conversation for the build)
GET  /build/conversations/{id}/messages   (restore the stored transcript)
        ↓
frontend build chat state        (answer, evidence, analysis restored)
        ↓
POST /build/chat                 (unchanged, bounded history, shared Gemini provider)
        ↓
POST /build/conversations/{id}/turn       (store the question and the answer)
```

Persistence wraps the existing build chat flow. It does not change the AI
contract, the prompt, the provider, or the bounded history rules.

## Data model

```text
hardware
   ├── build_conversations.cpu_hardware_id → hardware.id
   └── build_conversations.gpu_hardware_id → hardware.id

build_conversations
   ├── id
   ├── cpu_hardware_id
   ├── gpu_hardware_id
   ├── created_at
   ├── updated_at
   └── UNIQUE (cpu_hardware_id, gpu_hardware_id)

build_messages
   ├── id
   ├── conversation_id → build_conversations.id
   ├── role            ("user" | "assistant")
   ├── content
   ├── evidence_json   (assistant only, JSON, nullable)
   ├── analysis_json   (assistant only, JSON, nullable)
   └── created_at
```

The Sprint 16 structured response (`answer`, `evidence`, `analysis`) is preserved
on the message row itself. `answer` is stored in `content`; `evidence` and
`analysis` are stored as JSON columns on the same row. There are no separate
evidence or analysis tables, because nothing queries them independently.

## Build identity

A conversation belongs to exactly one CPU + GPU pair.

- `UNIQUE (cpu_hardware_id, gpu_hardware_id)` makes the conversation
  deterministic per build.
- `POST /build/conversations` is create-or-reuse, so a reload finds the same
  conversation row instead of starting a new one.
- The backend verifies both references against `hardware` and rejects a GPU id
  in the CPU slot, a CPU id in the GPU slot, and unknown ids (422).
- Changing the selected CPU or GPU changes the build identity token, so the
  frontend starts from a different conversation and never shows the previous
  build's messages.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/build/conversations` | Create or reuse the conversation for a CPU + GPU pair. |
| `GET` | `/build/conversations/{id}` | Retrieve a conversation. |
| `GET` | `/build/conversations/{id}/messages` | Load the stored transcript in chronological order. |
| `POST` | `/build/conversations/{id}/messages` | Append one message. |
| `POST` | `/build/conversations/{id}/turn` | Append the question and the answer of one completed turn. |
| `POST` | `/build/conversations/{id}/reset` | Clear the stored transcript and keep the build identity. |

`POST .../turn` exists so a completed exchange is stored in a single
transaction. Two separate appends would leave a stored `user` message without
its answer if the second request failed, which would break the strictly
alternating history contract on the next turn.

| Condition | HTTP status |
| --- | --- |
| Unknown conversation id | 404 |
| Unknown hardware id, wrong component type, schema violation | 422 |
| Stored message that cannot be read back | 500 |

## Field rules

| Field | Rule |
| --- | --- |
| `cpu_hardware_id`, `gpu_hardware_id` | Required, `> 0`, must exist, and must match the slot type. |
| `role` | Reuses the build chat vocabulary: `user` or `assistant` only. |
| `content` | Trimmed, non-blank, at most 40000 characters. |
| `evidence`, `analysis` on a `user` message | Rejected. |
| `evidence`, `analysis` on an `assistant` message | Optional; default to empty sections. Reuse the build chat evidence and analysis schemas. |
| `question`, `answer` on a turn | Trimmed, non-blank, within the same length bound. |
| extra fields | Rejected everywhere (`extra="forbid"`). |

## Bounded history is unchanged

Persistence does not change what reaches Gemini.

- `POST /build/chat` still receives the bounded `messages` array from the
  frontend and still rejects more than 10 messages, a non-alternating order, an
  unknown role, and blank or oversized content.
- A restored transcript can be longer than 10 messages. The frontend applies the
  existing history window (10 newest messages, starting with `user`) before the
  next request, so the provider context stays bounded.
- Stored evidence and analysis are never sent back to the provider. They are a
  presentational detail, exactly as before.
- `POST /build/chat` never reads or writes the conversation tables. Persistence
  is a separate layer around it.

## Client-side rules

| Situation | Behaviour |
| --- | --- |
| Build becomes ready | Create or reuse the conversation and restore the stored messages. |
| Restored message | Rendered with its answer, evidence, and analysis. |
| Successful turn | The question and the answer are stored as one turn. |
| Save failure | The answer stays visible; a recoverable notice offers a retry of the same turn. |
| Load failure | No history is shown and no history is invented. A recoverable notice offers a retry, and the user can still ask a new question. |
| CPU or GPU change | The previous conversation is discarded before the new one is loaded. |
| New conversation | Clears the visible transcript and clears the stored transcript for the same build identity. |
| Stale load or save | Ignored, via `createChatRequestGuard` and the build identity token. |

## Out of scope

- No authentication, no users, no ownership, no session system.
- No conversation list, search, rename, or delete UI.
- No persistent hardware chat (`/hardware/chat`) and no persistent comparison
  explanations.
- No cross-build or cross-device conversation listing.
- Stored AI output is a transcript of an interpretation layer, not a new source
  of hardware truth.
