# 04 — HTTP API

API-first: the server wraps `clims_core`. Self-hosted, behind a reverse proxy for TLS.
Two distinct credentials:
- **Product auth** — who may call *this server* (header `Authorization: Bearer <product-token>`).
- **BYOK provider key** — which model account to use; **supplied in the request body**, used in-memory only, never logged/persisted.

## Endpoints (v1)

```
POST /v1/sessions
  → { "session_id": "..." , "created_at": "..." }

POST /v1/sessions/{id}/messages          (returns SSE stream)
  body:
  {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-...",            // BYOK — in-memory only
    "message": "Summarize repo and open a PR",
    "permission_mode": "ask",        // ask | acceptEdits | plan | bypass
    "tools": ["read","write","bash","mcp:*"],   // optional allowlist
    "system": null
  }

GET  /v1/sessions/{id}                    → session metadata + history
DELETE /v1/sessions/{id}                  → delete session
GET  /v1/sessions                         → list sessions

GET  /v1/models                           → configured providers + capabilities
POST /v1/tool-results/{tool_use_id}       → answer a permission_request / supply HITL result

GET  /healthz                             → liveness
```

## SSE event protocol

`POST .../messages` streams `text/event-stream`. Event types:

```
event: text_delta        data: {"text":"..."}
event: thinking_delta     data: {"text":"..."}
event: tool_use           data: {"id":"...","name":"bash","input":{...}}
event: permission_request data: {"tool_use_id":"...","tool":"bash","input":{...}}
event: tool_result        data: {"tool_use_id":"...","is_error":false,"content":[...]}
event: usage              data: {"input_tokens":..,"output_tokens":..}
event: error              data: {"message":"...","type":"..."}
event: done               data: {"stop_reason":"end_turn"}
```

When `permission_request` is emitted in `ask` mode, the client approves/denies via `POST /v1/tool-results/{id}` (or a control message), and the stream continues.

## OpenAI-compatible shim (optional, Phase 4)

`POST /v1/chat/completions` accepting OpenAI's schema, so existing OpenAI SDK clients can point at clims_code with a base-url change. Internally adapts to the engine. Enables drop-in integration into other platforms.

## Security rules

1. `api_key` is read into memory, passed to the provider, then dropped. Never written to sqlite, logs, or transcripts.
2. Redact secrets in any error surfaced to clients.
3. Product auth and BYOK are independent — never conflate them.
