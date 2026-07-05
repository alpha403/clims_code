# 00 — Overview

## Vision

`clims_code` is a **general-purpose agentic assistant** with full feature parity to Claude Code, but:
- works with **any capable AI model** (not just Claude),
- is **API-first** so it can be embedded in other products,
- is **self-hosted** and **BYOK**,
- is **pure Python** with no platform-specific dependencies.

The agent is **not a coding tool**. Coding is one of many domains. Its competence across "all digital work" comes from:
1. **15+ built-in tools** (file I/O, shell, web search, web fetch, glob, grep, image analysis, todo, notebook edit, subagent, memory, plan mode, etc.)
2. The **entire MCP ecosystem** — clims_code is a first-class MCP client (stdio + HTTP), so any MCP server (Slack, GitHub, Postgres, Gmail, browser automation, Drive, etc.) adds instant capability.
3. **Skills** — reusable multi-step workflow guides bundled or user-written.
4. **Multi-agent orchestration** — subagents, background tasks, scheduled tasks, workflow scripts.

## Status

✅ **Fully implemented** — 212 tests pass, live-validated on DeepSeek. 100% Claude Code feature parity (116/116 applicable features).

## Scope

| In scope | Out of scope (for now) |
|----------|------------------------|
| Multi-provider agent engine | Training/fine-tuning models |
| Native function-calling models | Prompt-based tool parsing for weak models |
| Built-in general tools | Hundreds of bespoke domain tools (use MCP instead) |
| MCP client (stdio + HTTP) | MCP server marketplace/hosting |
| HTTP API + CLI client | Hosted SaaS (we are self-hosted) |
| Full Claude Code feature parity | Mobile apps |
| Telegram bot | Discord / Slack native bot |
| Cross-platform (Win/Mac/Linux) | |

## Glossary

- **Provider** — an adapter to one model API (Anthropic, OpenAI, DeepSeek, Gemini, Ollama, Vertex, Bedrock).
- **Capable model** — a model with reliable native function/tool calling.
- **Engine / core** — the pure-Python package: agent loop, tools, providers, permissions, sessions, MCP.
- **Tool** — a function the model can call (built-in or from an MCP server).
- **MCP** — Model Context Protocol; a standard for exposing tools/resources to an agent over stdio or HTTP.
- **BYOK** — Bring Your Own Key; the provider key is supplied per request.
- **Session** — a persisted conversation with state, history, and config (sqlite-backed).
- **Subagent** — a focused child agent spawned by the main agent for a sub-task.
- **Skill** — a markdown file with step-by-step instructions for a recurring task pattern.
- **Workflow** — a Python script using `WorkflowAPI` to orchestrate multiple agents.
- **Hook** — an external script invoked on agent lifecycle events (PreToolUse, Notification, etc.).
