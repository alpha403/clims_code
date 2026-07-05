# clims_code

**A self-hosted, model-agnostic, API-first agentic assistant for *all digital work*.**

`clims_code` is a from-scratch clone of Claude Code's capabilities that works with **any capable AI model** (Anthropic, OpenAI, DeepSeek, Gemini, local models via Ollama — anything with native function-calling). It is not limited to coding: with built-in tools plus the **MCP** ecosystem it is meant to be efficient and reliable across browsing, research, data, automation, email, files, APIs — almost any digital task.

## Principles

1. **Model-agnostic** — one internal message model; every provider is a thin adapter behind a single interface. Adding a model = one new file.
2. **Zero-dependency core** — the engine + provider layer use only the Python standard library. The CLI client may use minimal deps (e.g. `rich`) for UX. The engine never does.
3. **API-first** — a headless engine exposed over HTTP. The CLI/TUI is just one client. Other platforms integrate via the API.
4. **BYOK** — bring your own key. The provider API key is supplied per request, used in-memory only, never logged or persisted.
5. **Self-hosted** — the customer runs the engine + API themselves.
6. **Full feature parity with Claude Code** — every feature Claude Code has, clims_code has. See [docs/02-FEATURE-PARITY.md](docs/02-FEATURE-PARITY.md).
7. **General-purpose** — coding is one use case among many. The agent identity is not coding-specific.

## Status

🟡 **Planning complete — implementation not started.** See [PROGRESS.md](PROGRESS.md) for live development tracking.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/00-OVERVIEW.md](docs/00-OVERVIEW.md) | Vision, scope, glossary |
| [docs/01-ARCHITECTURE.md](docs/01-ARCHITECTURE.md) | Layers, project structure, message normalization |
| [docs/02-FEATURE-PARITY.md](docs/02-FEATURE-PARITY.md) | **Exhaustive Claude Code feature inventory + parity status** |
| [docs/03-PROVIDERS.md](docs/03-PROVIDERS.md) | Provider abstraction, model capability registry |
| [docs/04-API.md](docs/04-API.md) | HTTP API, BYOK, SSE event protocol |
| [docs/05-MCP.md](docs/05-MCP.md) | MCP client design |
| [docs/06-TOOLS.md](docs/06-TOOLS.md) | Built-in tool specifications |
| [docs/07-PERMISSIONS.md](docs/07-PERMISSIONS.md) | Permission modes + settings hierarchy |
| [docs/08-ROADMAP.md](docs/08-ROADMAP.md) | Phased build plan |
| [docs/09-DECISIONS.md](docs/09-DECISIONS.md) | Decision log (ADR-style) |

## Tech baseline

- **Python 3.11+**
- Engine deps: **none** (stdlib only: `urllib`, `ssl`, `http.server`, `sqlite3`, `json`, `asyncio`)
- First two providers: **DeepSeek + Anthropic**
