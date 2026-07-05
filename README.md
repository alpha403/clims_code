# clims_code

**A self-hosted, model-agnostic, API-first agentic assistant for *all digital work*.**

Works with **any capable AI model** (Anthropic, OpenAI, DeepSeek, Gemini, Ollama, Vertex AI, Bedrock — anything with native function-calling). Not limited to coding: with 15+ built-in tools plus the entire **MCP ecosystem**, it handles research, automation, data, file ops, web, and more.

> ✅ **Fully implemented** — 212 tests pass, live-validated on DeepSeek. 100% feature parity with Claude Code (116/116 applicable features).

---

## Quick install

```bash
pip install git+https://github.com/alpha403/clims_code.git
```

Or with extras:

```bash
pip install git+https://github.com/alpha403/clims_code.git#egg=clims_code[full]
# [full] adds: pypdf (PDF text), python-telegram-bot, tiktoken
```

Works on **Windows, macOS, and Linux** — pure Python, no C extensions.

### Requirements

- **Python ≥ 3.10**
- An API key from a supported provider (DeepSeek, Anthropic, OpenAI, Gemini, etc.)

---

## Quick start

```bash
# Set your API key — no config files needed
export DEEPSEEK_API_KEY="sk-..."

# Launch interactive REPL
clims

# Or headless (one-shot)
clims -p "List all files and summarize the project"
```

On first launch, `clims` walks you through provider selection and key setup. That's it.

---

## Capabilities at a glance

| Area | What it can do |
|------|---------------|
| **File operations** | Read, write, edit (exact-string replace), glob, grep — full file system access with safety guard |
| **Shell execution** | Run commands, background jobs, kill, poll output — cross-platform (cmd/PowerShell on Windows, sh/bash on POSIX) |
| **Web** | Fetch URLs, search the web (DuckDuckGo) |
| **Vision** | Analyze images inline via supported providers |
| **Planning** | Plan mode → agent researches read-only, you approve → it executes |
| **Research** | `/research` — parallel search + fetch across multiple queries, synthesize, fact-check |
| **Background tasks** | `/bg` — kick off an agent task and keep working |
| **Scheduled tasks** | `/schedule add 1h "check for new issues"` — recurring automation |
| **Workflows** | Python scripts using `WorkflowAPI` (parallel agents, pipelines) |
| **Context management** | Auto-compaction, manual `/compact`, `/rewind` to any checkpoint |
| **Sessions** | `/resume` — pick up where you left off across restarts |
| **Memory** | CLIMS.md (project rules) + `.clims/memory/` (cross-session notes) |
| **MCP servers** | Connect GitHub, Slack, Postgres, Filesystem, Brave Search, and 10+ more by name — or any custom stdio/HTTP MCP server |
| **Telegram bot** | Run as a background bot — interact with the agent from Telegram |
| **HTTP API** | REST + SSE — the agent as a service, behind your own reverse proxy |
| **OpenAI-compatible endpoint** | Drop-in replacement — any OpenAI SDK can point at clims_code |
| **Permission modes** | `default` (ask before exec/write), `acceptEdits` (auto-approve), `plan` (read-only), `bypass` (unrestricted) |
| **Subagents** | Spawn focused child agents with their own tools and context (recursion-bounded) |
| **Hooks** | Event-driven hooks (PreToolUse, PostToolUse, Notification, SessionStart, Stop) — run scripts on agent lifecycle events |
| **Skills** | Pre-written skill files (ad-campaign, content-plan, email, reel, SEO brief, etc.) that guide the agent through multi-step workflows |
| **Custom commands** | Define `/yourcommand` scripts in `.clims/commands/` |

---

## Usage

### Interactive REPL

```bash
clims                              # launch
clims --provider openai --model gpt-4o  # pick provider/model
clims --mode acceptEdits           # auto-approve tool calls
clims --resume                     # resume last session
```

Slash commands inside the REPL:

```
/help       — list all commands
/model      — show/switch model
/mode       — show/switch permission mode
/cost       — token usage for this session
/clear      — clear context
/compact    — summarize old turns
/rewind [n] — go back n turns
/resume [id]— reload a saved session
/research   — deep research on a question
/bg <task>  — background agent task
/tasks      — list background tasks
/schedule   — recurring tasks
/workflow   — run a workflow script
/memory     — show memory state
/export     — export conversation
/doctor     — system diagnostics
/bot start/stop/status — Telegram bot
```

### Headless (for scripting/CI)

```bash
clims -p "Refactor this file"                              # plain text output
clims -p "Fix all lint errors" --output-format json         # JSON result
clims -p "Summarize repo" --output-format stream-json       # JSONL events
```

### HTTP API server

```bash
export CLIMS_SERVER_TOKEN="my-token"   # optional auth
clims-server                           # serves on 127.0.0.1:8765
```

```bash
# Create a session
curl -s -X POST localhost:8765/v1/sessions

# Send a message (SSE stream)
curl -N -X POST localhost:8765/v1/sessions/sess_xxx/messages \
  -H "Content-Type: application/json" \
  -d '{"provider":"deepseek","model":"deepseek-chat","api_key":"sk-...",
       "message":"create hello.txt","permission_mode":"acceptEdits"}'
```

### OpenAI-compatible endpoint

Any OpenAI SDK works — just change the base URL:

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:8765/v1",
    api_key="<your-deepseek-key>"
)
# Use like normal OpenAI client
```

```bash
curl -s localhost:8765/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "x-clims-provider: deepseek" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}'
```

### Telegram bot

```bash
clims-bot   # runs in background; configure via /setup or interactive first-run
```

### As a Python library

```python
from clims_core.agent.loop import Agent
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers import get_provider
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

provider = get_provider("deepseek")
runtime = ToolRuntime(tool_map(default_tools()),
                      PermissionPolicy(mode=PermissionMode.BYPASS),
                      ToolContext())
agent = Agent(provider=provider, model="deepseek-chat", api_key="sk-...",
              runtime=runtime, temperature=0)
result = agent.send([Message.user("List the files and summarize.")])
```

---

## Providers

| Provider | Models tested | Key env var |
|----------|--------------|-------------|
| **DeepSeek** | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| **Anthropic** | claude-sonnet-4, claude-3-haiku | `ANTHROPIC_API_KEY` |
| **OpenAI** | gpt-4o, o3-mini, gpt-4.1 | `OPENAI_API_KEY` |
| **Gemini** | gemini-2.5-flash, gemini-2.5-pro | `GEMINI_API_KEY` |
| **Ollama** | Any local model (no key needed) | — |
| **Vertex AI** | Gemini via GCP | `VERTEX_CREDENTIALS` |
| **Bedrock** | Claude via AWS | AWS credentials |

---

## Configuration

Settings are merged (low → high priority):

```
~/.clims/settings.json → ./.clims/settings.json → ./.clims/settings.local.json
```

Available keys: `provider`, `model`, `permission_mode`, `temperature`, `max_tokens`, `allow`, `deny`, `ask`, `system`, `hooks`.

Credentials (API keys) are stored in `.clims/credentials.json` — never committed (in `.gitignore`).

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/00-OVERVIEW.md](docs/00-OVERVIEW.md) | Vision, scope, glossary |
| [docs/01-ARCHITECTURE.md](docs/01-ARCHITECTURE.md) | Layers, project structure, message normalization |
| [docs/02-FEATURE-PARITY.md](docs/02-FEATURE-PARITY.md) | Exhaustive Claude Code feature inventory + parity status |
| [docs/03-PROVIDERS.md](docs/03-PROVIDERS.md) | Provider abstraction, model capability registry |
| [docs/04-API.md](docs/04-API.md) | HTTP API, BYOK, SSE event protocol |
| [docs/05-MCP.md](docs/05-MCP.md) | MCP client design |
| [docs/06-TOOLS.md](docs/06-TOOLS.md) | Built-in tool specifications |
| [docs/07-PERMISSIONS.md](docs/07-PERMISSIONS.md) | Permission modes + settings hierarchy |
| [docs/08-ROADMAP.md](docs/08-ROADMAP.md) | Development history and future plans |
| [docs/09-DECISIONS.md](docs/09-DECISIONS.md) | Decision log (ADR-style) |
| [docs/USAGE.md](docs/USAGE.md) | Extended usage guide |
| [PROGRESS.md](PROGRESS.md) | Live development tracker |

---

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -q   # 212 tests
```
