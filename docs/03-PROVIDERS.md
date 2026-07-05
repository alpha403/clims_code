# 03 — Providers

## Interface

```python
# clims_core/providers/base.py (sketch)

@dataclass
class ModelCapabilities:
    context_window: int
    max_output: int
    supports_tools: bool
    supports_vision: bool
    supports_thinking: bool
    supports_prompt_cache: bool
    supports_streaming: bool

class StreamEvent:  # discriminated union emitted by chat()
    # one of: text_delta | thinking_delta | tool_use | usage | done | error
    ...

class Provider(ABC):
    name: str
    @abstractmethod
    def chat(self, *, model: str, messages: list[Message], tools: list[ToolSchema],
             system: str | None, api_key: str, stream: bool = True,
             temperature: float | None = None, max_tokens: int | None = None,
             extra: dict | None = None) -> Iterator[StreamEvent]: ...
    @abstractmethod
    def capabilities(self, model: str) -> ModelCapabilities: ...
```

All HTTP goes through `clims_core/http.py` (stdlib `urllib` + `ssl`, SSE line reader). **No `requests`, no SDKs.**

## Wire-format differences each adapter hides

| Concern | Anthropic | OpenAI | Gemini | DeepSeek | Ollama |
|---------|-----------|--------|--------|----------|--------|
| Endpoint | `/v1/messages` | `/v1/chat/completions` | `:generateContent` | OpenAI-compat | OpenAI-compat / native |
| System prompt | top-level `system` | `role:"system"` msg | `systemInstruction` | system msg | system msg |
| Tool call out | `tool_use` block | `tool_calls[]` | `functionCall` part | `tool_calls[]` | `tool_calls[]` |
| Tool result in | `tool_result` block | `role:"tool"` msg | `functionResponse` part | `role:"tool"` | `role:"tool"` |
| Assistant role | `assistant` | `assistant` | `model` | `assistant` | `assistant` |
| Streaming | SSE event types | SSE `choices[].delta` | SSE chunks | SSE deltas | NDJSON / SSE |
| Auth header | `x-api-key` + `anthropic-version` | `Authorization: Bearer` | `?key=` or header | `Authorization: Bearer` | none (local) |
| Vision | image block | image_url | inlineData | n/a (varies) | varies |

## Capability registry

`providers/registry.py` maps known model ids → `ModelCapabilities`. Unknown models fall back to conservative defaults and a one-time probe. Powers `/model`, `GET /v1/models`, and context-window-aware compaction.

## Adding a provider (the payoff)

1. New file `providers/<name>.py` implementing `chat()` + `capabilities()`.
2. Register in a provider map.
3. Add model rows to the registry.
That's it — the agent loop, tools, server, and CLI are untouched.

## Phase 1 targets

- **DeepSeek** (`deepseek-chat`) — OpenAI-compatible dialect.
- **Anthropic** (`claude-*`) — block-based dialect.
Two different dialects = strongest proof the abstraction holds.
