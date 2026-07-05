# 01 — Architecture

## Layered model

```
        ┌──────────────── CLIENTS (thin) ────────────────┐
        │  Terminal CLI/TUI   ·   3rd-party apps   ·  Web │
        └───────────────┬─────────────────────────────────┘
                        │  HTTP + SSE  (BYOK key in request)
                        ▼
        ┌─────────────────────────────────────────────────┐
        │  clims_server   — REST + SSE, auth, routing      │
        ├─────────────────────────────────────────────────┤
        │  clims_core (ENGINE)              [ZERO-DEP]     │
        │   agent loop · tool runtime · permission gate    │
        │   session store · memory · subagents · hooks     │
        ├─────────────────────────────────────────────────┤
        │  Tool sources                                    │
        │   built-in tools        +        MCP client      │
        ├─────────────────────────────────────────────────┤
        │  Provider layer                   [ZERO-DEP]     │
        │   one interface → anthropic/openai/deepseek/...  │
        └─────────────────────────────────────────────────┘
```

The **engine + provider layer** are the portable IP and are strictly zero-dependency. The **server** wraps the engine. **Clients** are replaceable.

## Project structure

```
clims_code/
  clims_core/                     # ZERO external deps
    __init__.py
    config.py                     # settings hierarchy loader
    http.py                       # stdlib HTTPS POST + SSE reader
    providers/
      base.py                     # Provider ABC + normalized types
      registry.py                 # model -> ModelCapabilities
      anthropic.py
      openai.py
      deepseek.py
      gemini.py
      ollama.py
    agent/
      message.py                  # Message, ContentBlock (Text/ToolUse/ToolResult/Image/Thinking)
      loop.py                     # the agentic loop
      runtime.py                  # tool dispatch + result formatting
      subagent.py                 # spawn focused child agents
    tools/
      base.py                     # Tool ABC (name, schema, run, permission class)
      read.py write.py edit.py
      bash.py                     # incl. background exec + output streaming
      glob.py grep.py
      web_fetch.py web_search.py
      todo.py                     # task tracking tool
      notebook_edit.py
    mcp/
      client.py                   # stdio + HTTP/SSE MCP transport
      manager.py                  # discover/connect servers, aggregate tools
    permissions/
      policy.py                   # ask/allow/deny rules, modes, rule matching
    session/
      store.py                    # sqlite-backed sessions, history, transcripts
    memory/
      manager.py                  # CLAUDE.md-style project+user memory, @imports
    hooks/
      runner.py                   # event hooks (PreToolUse, PostToolUse, ...)
    slash/
      commands.py                 # built-in + custom slash commands
    skills/
      loader.py                   # user-invocable skills
  clims_server/
    api.py                        # stdlib ThreadingHTTPServer, REST + SSE
    auth.py                       # product-level auth (separate from BYOK)
    schemas.py
  clims_cli/                      # MAY use minimal deps (rich)
    main.py repl.py tui.py
    render.py                     # markdown, diffs, spinners
  tests/
  docs/
  pyproject.toml
  PROGRESS.md
```

## Message normalization (the crux)

A single internal model that every provider converts to/from:

```python
# clims_core/agent/message.py  (sketch)
Role = Literal["system", "user", "assistant", "tool"]

class TextBlock:        text: str
class ThinkingBlock:    text: str
class ImageBlock:       media_type: str; data: bytes        # base64 at the wire
class ToolUseBlock:     id: str; name: str; input: dict
class ToolResultBlock:  tool_use_id: str; content: list; is_error: bool

ContentBlock = TextBlock | ThinkingBlock | ImageBlock | ToolUseBlock | ToolResultBlock

class Message:
    role: Role
    content: list[ContentBlock]
```

Each provider adapter implements:

```python
class Provider(ABC):
    @abstractmethod
    def chat(self, *, model, messages, tools, system, api_key,
             stream=True, **opts) -> Iterator[StreamEvent]: ...
    @abstractmethod
    def capabilities(self, model: str) -> ModelCapabilities: ...
```

Wire-format differences hidden by adapters:
- **Anthropic** — `tool_use` / `tool_result` content blocks; `system` is top-level.
- **OpenAI** — `tool_calls` array on assistant; tool replies use `role:"tool"`.
- **Gemini** — `functionCall` / `functionResponse` parts; different roles ("model").
- **DeepSeek** — OpenAI-compatible.
- **Ollama** — OpenAI-compatible (`/v1`) or native; local, no key.

**If `base.py` is clean, a new model is one file.** This is the abstraction that makes "any model" real.

## The agent loop (conceptual)

```
1. Build request: system prompt + memory + messages + available tools
2. provider.chat(...) → stream text/thinking deltas to client
3. If response contains tool_use blocks:
     for each: permission gate → execute (built-in or MCP) → collect ToolResult
     append assistant(tool_use) + tool(tool_result) to history
     goto 2
4. Else: final answer → emit `done`
   (interleave hooks at PreToolUse/PostToolUse; honor interrupts; auto-compact on context pressure)
```

## Concurrency & server

- `clims_server` uses stdlib `ThreadingHTTPServer`; intended to sit behind a reverse proxy (nginx/Caddy) for TLS + scale. Keeps the zero-dep promise.
- Long-running responses stream via **SSE**. See [04-API.md](04-API.md).
- Sessions are isolated by `session_id`; state in **sqlite** (stdlib).
