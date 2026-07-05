# 08 — Roadmap

Phases are ordered to **de-risk early** (prove model-agnosticism + the agent loop first) and to reach the "all digital work" promise quickly (MCP promoted early).

Status legend: ⬜ not started · 🟡 in progress · ✅ done

## Phase 1 — Engine core & provider proof  ⬜
**Goal:** one task runs end-to-end against two different model dialects.
- Normalized message model (`agent/message.py`)
- `Provider` ABC + `ModelCapabilities` (`providers/base.py`, `registry.py`)
- Zero-dep HTTPS POST + SSE reader (`http.py`)
- Providers: **DeepSeek** + **Anthropic**
- Agent loop (`agent/loop.py`, `runtime.py`)
- Tools: `read`, `write`, `bash`
- Permission gate (ask before bash/write)
- Minimal CLI REPL
- **Exit criterion:** same prompt completes a real file+shell task on both models by changing one config value.

## Phase 2 — General tool suite & UX  ⬜
- Tools: `edit`, `glob`, `grep`, `web_fetch`, `web_search`, `todo`, `notebook_edit`
- Streaming render in CLI (markdown, diffs, spinners)
- Background bash + output streaming + kill
- Image input support
- Providers: add **OpenAI**, **Gemini**, **Ollama**

## Phase 3 — MCP client (capability multiplier)  ⬜
- MCP transports: stdio + HTTP/SSE
- Server discovery/config (`.mcp.json`), tool aggregation
- OAuth for remote MCP servers
- Expose MCP tools through the same tool runtime

## Phase 4 — HTTP API (the product surface)  ⬜
- `clims_server`: sessions, messages, SSE event protocol
- BYOK key handling (in-memory only)
- Product-level auth
- `GET /v1/models` capability listing
- OpenAI-compatible endpoint shim (optional, for easy integration)

## Phase 5 — Full Claude Code experience  ⬜
Drive [02-FEATURE-PARITY.md](02-FEATURE-PARITY.md) to 100%:
- Slash commands (built-in + custom `.clims/commands/*.md`)
- Project + user memory (CLIMS.md, @imports, nested)
- Subagents (`.clims/agents/*.md`)
- Hooks (all events)
- Skills
- Settings hierarchy + permission rules
- Plan mode, auto-accept mode
- Context auto-compaction, `/compact`, microcompaction
- Cost/usage tracking, sessions resume/continue
- Headless/print mode, output formats (json, stream-json)
- Status line, notifications, vim mode, keybindings
- IDE integration hooks (diagnostics, execute)

## Phase 6 — Productize  ⬜
- Sandbox hardening for shell/file tools
- Packaging (`pip install`, single-command server start)
- Auth/licensing for the self-hosted product
- Docs site, examples, quickstart
- Telemetry (opt-in), `/doctor` health check, `/bug` report

## Cross-cutting (every phase)
- Tests per module
- Keep engine zero-dependency
- Never log/persist BYOK keys
- Update PROGRESS.md and FEATURE-PARITY.md as features land
