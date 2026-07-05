# 00 — Overview

## Vision

`clims_code` is a **general-purpose agentic assistant** with full feature parity to Claude Code, but:
- works with **any capable AI model** (not just Claude),
- is **API-first** so it can be embedded in other products,
- is **self-hosted** and **BYOK**,
- has a **zero-dependency core**.

The agent is **not a coding tool**. Coding is one of many domains. Its competence across "all digital work" comes from two sources:
1. A small set of **general built-in tools** (file I/O, shell, web, search).
2. The **entire MCP ecosystem** — clims_code is a first-class MCP client, so any MCP server (Slack, GitHub, Postgres, Gmail, browser automation, Drive, etc.) becomes an instant capability.

## Scope

| In scope | Out of scope (for now) |
|----------|------------------------|
| Multi-provider agent engine | Training/fine-tuning models |
| Native function-calling models | Prompt-based tool parsing for weak models |
| Built-in general tools | Hundreds of bespoke domain tools (use MCP instead) |
| MCP client | MCP server marketplace/hosting |
| HTTP API + CLI client | Hosted SaaS (we are self-hosted) |
| Full Claude Code feature parity | Mobile apps |

## Glossary

- **Provider** — an adapter to one model API (Anthropic, OpenAI, DeepSeek, Gemini, Ollama…).
- **Capable model** — a model with reliable native function/tool calling.
- **Engine / core** — the zero-dependency Python package: agent loop, tools, providers, permissions, sessions.
- **Tool** — a function the model can call (built-in or from an MCP server).
- **MCP** — Model Context Protocol; a standard for exposing tools/resources to an agent over stdio or HTTP.
- **BYOK** — Bring Your Own Key; the provider key is supplied per request.
- **Session** — a persisted conversation with state, history, and config.
- **Subagent** — a focused child agent spawned by the main agent for a sub-task.

## Non-negotiables

1. The engine and provider layer import **nothing outside the Python standard library**.
2. Provider API keys are **never written to disk or logs**.
3. Every Claude Code feature is tracked in [02-FEATURE-PARITY.md](02-FEATURE-PARITY.md) until it reaches parity.
