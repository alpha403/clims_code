# 09 — Decision Log (ADR-style)

Append-only. Each entry: context → decision → consequences.

## ADR-001 — Model-agnostic via hand-rolled provider adapters
**Context:** Must support "any capable model." Options: LiteLLM, OpenRouter, custom.
**Decision:** Hand-roll a `Provider` interface + per-provider adapters using only stdlib HTTP.
**Consequences:** Zero deps, full control, no third-party service margin. Cost: we maintain wire-format adapters ourselves. Mitigated by a clean `base.py` so a new model = one file.

## ADR-002 — Zero-dependency engine, minimal-dep CLI
**Context:** Product to sell; portability and trust matter. Full TUI is heavy in pure stdlib.
**Decision:** `clims_core` + `clims_server` use **stdlib only**. `clims_cli` MAY use minimal deps (e.g. `rich`) for rendering.
**Consequences:** Engine is portable/embeddable IP. UI polish isolated to the client. sqlite/urllib/ssl/http.server count as zero-dep.

## ADR-003 — API-first, headless engine
**Context:** Must integrate into other platforms.
**Decision:** Engine is headless; HTTP API is the primary surface; CLI is one client.
**Consequences:** Clean separation, embeddable. Slightly more upfront structure than a monolithic CLI.

## ADR-004 — BYOK, key supplied per request
**Context:** Commercial, self-hosted; we must not front token costs or hold customer keys.
**Decision:** Provider API key is passed in each API call, used in-memory only, never logged/persisted.
**Consequences:** Simple billing, low legal risk. Requires strict secret hygiene; product auth is separate from BYOK.

## ADR-005 — Self-hosted, behind reverse proxy
**Context:** Zero-dep server vs production hardening.
**Decision:** stdlib `ThreadingHTTPServer`; rely on nginx/Caddy for TLS + scale.
**Consequences:** Keeps zero-dep promise; deployment doc must specify the proxy.

## ADR-006 — Capable models only (native function-calling)
**Context:** "Any model on the planet" vs reliability.
**Decision:** Target models with reliable native tool-calling. No prompt-based tool-parsing fallback in v1.
**Consequences:** Much simpler, reliable agent loop. Weak/old models unsupported for now (revisit later).

## ADR-007 — General-purpose, MCP-forward
**Context:** Not just coding — "all digital work."
**Decision:** Built-ins are general primitives; domain capability comes via MCP. MCP promoted to Phase 3.
**Consequences:** Broad reach without bespoke tool sprawl. Depends on MCP client quality.

## ADR-008 — Brand name `clims_code`
**Decision:** Product name is `clims_code`. Do NOT use Anthropic's "Claude Code" name/branding in shipped product.
**Consequences:** Avoids trademark issues; concept clone is fine, name reuse is not.

## ADR-009 — Python 3.10+; first providers DeepSeek + Anthropic
**Context:** Target was 3.11+, but the dev machine has Python 3.10.11 installed and the user is asleep (can't install).
**Decision:** Baseline **Python 3.10+** (all needed features — PEP 604 unions, match, dataclasses — exist in 3.10). Phase 1 proves the abstraction with two different dialects (DeepSeek OpenAI-style, Anthropic block-style).
**Consequences:** Avoid 3.11-only stdlib (`tomllib`, exception groups, `typing.Self`). Use a tiny config loader instead of `tomllib`.
