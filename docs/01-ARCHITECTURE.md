# 01 — Architecture

## Layered model

```
        ┌──────────────── CLIENTS (thin) ────────────────┐
        │  Terminal CLI/TUI   ·   Telegram bot   ·  HTTP  │
        └───────────────┬─────────────────────────────────┘
                        │  HTTP + SSE  (BYOK key in request)
                        ▼
        ┌─────────────────────────────────────────────────┐
        │  clims_server   — REST + SSE, auth, routing      │
        ├─────────────────────────────────────────────────┤
        │  clims_core (ENGINE)                             │
        │   agent loop · tool runtime · permission gate    │
        │   session store · memory · subagents · hooks     │
        │   compaction · checkpoint · orchestrate          │
        ├─────────────────────────────────────────────────┤
        │  Tool sources                                    │
        │   built-in tools (15+)    +    MCP client         │
        ├─────────────────────────────────────────────────┤
        │  Provider layer                                   │
        │   anthropic · openai · deepseek · gemini          │
        │   ollama · vertex · bedrock                       │
        └─────────────────────────────────────────────────┘
```

All layers use pure Python (stdlib + rich for CLI UX). No C extensions.

## Project structure

```
clims_code/
  clims_core/
    __init__.py
    config.py                     # settings hierarchy loader
    http.py                       # stdlib HTTPS POST + SSE reader/parser
    providers/
      base.py                     # Provider ABC + StreamEvent + ToolSchema
      registry.py                 # model -> ModelCapabilities
      anthropic.py                # Anthropic adapter (Messages API)
      openai.py                   # OpenAI adapter (chat completions)
      deepseek.py                 # DeepSeek adapter (OpenAI-compatible)
      gemini.py                   # Google Gemini adapter
      ollama.py                   # Local models via Ollama
      vertex.py                   # GCP Vertex AI
      bedrock.py                  # AWS Bedrock
      _sigv4.py                   # AWS SigV4 signing (Bedrock)
    agent/
      message.py                  # Message, ContentBlock types (Text/ToolUse/Image/Thinking)
      loop.py                     # Agent class — the main agentic loop
      runtime.py                  # ToolRuntime — dispatch + permission gate
      subagent.py                 # SubagentTool — spawn focused child agents
      compaction.py               # Context compaction (microcompact + full)
    tools/
      base.py                     # Tool ABC, ToolContext, ToolResult
      read.py                     # ReadTool — text, PDF, images, binary detection
      write.py                    # WriteTool — create/overwrite
      edit.py                     # EditTool — exact-string replace
      multi_edit.py               # MultiEditTool — atomic multi-edit in one file
      bash.py                     # BashTool — shell exec, background mode
      bash_jobs.py                # BashOutputTool + KillShellTool
      glob.py                     # GlobTool — file pattern matching
      grep.py                     # GrepTool — pure-Python regex, falls back to rg
      web_fetch.py                # WebFetchTool — HTML to text
      web_search.py               # WebSearchTool — DuckDuckGo
      todo.py                     # TodoTool — task list
      notebook.py                 # NotebookEditTool — .ipynb cell ops
      plan.py                     # ExitPlanModeTool
      memory_tool.py              # MemoryTool — cross-session notes
      generate_image.py           # GenerateImageTool — ComfyUI / Imagen
      analyze_image.py            # AnalyzeImageTool — vision model
      config_tool.py              # ConfigureTool — self-configuration
      syntax_check.py             # SyntaxCheckTool — JS/Python lint
      winshims.py                 # Windows Unix-command shims (python3, head, tail, cat...)
    mcp/
      client.py                   # StdioMCPClient — stdio JSON-RPC
      http_client.py              # HttpMCPClient — HTTP Streamable transport
      manager.py                  # MCPManager — connect/discover servers
      registry.py                 # Known MCP server registry (12+ servers)
      oauth.py                    # OAuth flow for MCP servers
    permissions/
      policy.py                   # PermissionPolicy, PermissionMode, rule matching
    session/
      store.py                    # sqlite-backed session store
    memory/
      manager.py                  # CLIMS.md + .clims/memory/ reader
    hooks/
      runner.py                   # Event hooks: PreToolUse, PostToolUse, etc.
    data/
      skills/                     # Bundled skill files (ad-campaign, reel, SEO, etc.)
  clims_server/
    __init__.py
    api.py                        # ThreadingHTTPServer, REST + SSE + OpenAI shim
  clims_cli/
    __init__.py
    main.py                       # Entry point: cli() + headless mode
    repl.py                       # Interactive REPL loop
    render.py                     # Rich text rendering (markdown, diffs, spinners)
    prompt.py                     # Prompt_toolkit prompt with tab-completion
    interrupt.py                  # Esc/Ctrl-C interrupt handler
    input_queue.py                # Message queue for multi-line input
    notify.py                     # Desktop notifications
    telegram_bot.py               # Telegram bot entry point
  tests/                          # 50+ test files, 212 tests
  docs/
  pyproject.toml
  PROGRESS.md
```

## Message normalization

A single internal message model that every provider converts to/from:

```python
Role = Literal["system", "user", "assistant", "tool"]

class TextBlock:        text: str
class ThinkingBlock:    text: str
class ImageBlock:       media_type: str; data: bytes
class ToolUseBlock:     id: str; name: str; input: dict
class ToolResultBlock:  tool_use_id: str; content: str; is_error: bool

ContentBlock = TextBlock | ThinkingBlock | ImageBlock | ToolUseBlock | ToolResultBlock

class Message:
    role: Role
    content: list[ContentBlock]
```

Each provider adapter implements:

```python
class Provider(ABC):
    def chat(self, *, model, messages, tools, system, api_key,
             stream=True, **opts) -> Iterator[StreamEvent]: ...
    def capabilities(self, model: str) -> ModelCapabilities: ...
```

Wire-format differences are hidden by adapters:
- **Anthropic** — `tool_use` / `tool_result` content blocks; `system` is top-level.
- **OpenAI / DeepSeek / Ollama** — `tool_calls` array; tool replies use `role:"tool"`.
- **Gemini** — `functionCall` / `functionResponse` parts; different roles ("model").
- **Vertex / Bedrock** — wrap their respective cloud APIs.

Adding a new provider = one new file implementing the `Provider` ABC.

## The agent loop

```
1. Build request: system prompt + memory + environment context + messages + tools
2. provider.chat(...) → stream text/thinking deltas to client
3. If response contains tool_use blocks:
     for each: permission gate → execute (built-in or MCP) → collect ToolResult
     append assistant(tool_use) + tool(tool_result) to history
     goto 2
4. Else: final answer → emit done
   (interleave hooks at PreToolUse/PostToolUse; honor cancel Event; auto-compact on context pressure)
```

## Concurrency & server

- `clims_server` uses stdlib `ThreadingHTTPServer`; sits behind a reverse proxy (nginx/Caddy) for TLS + scale.
- Long-running responses stream via **SSE**.
- Sessions are isolated by `session_id`; state in **sqlite** (stdlib).
- MCP client subprocesses are tracked per-agent; cleaned up on server shutdown.
