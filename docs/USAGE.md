# Usage

`clims_code` has four entry points: the **CLI** (`clims`), the **HTTP API server** (`clims-server`), the **Telegram bot** (`clims-bot`), and the **engine as a Python library**.

---

## 0. Installation

```bash
# From GitHub
pip install git+https://github.com/alpha403/clims_code.git

# With extras
pip install git+https://github.com/alpha403/clims_code.git#egg=clims_code[full]

# Or for development
git clone https://github.com/alpha403/clims_code.git
cd clims_code
pip install -e ".[dev]"
```

> The package installs three CLI entry points: `clims`, `clims-bot`, and `clims-server`.

---

## 1. First run — setup

On first launch, `clims` runs an interactive setup that asks for:

1. **Provider** — choose from: deepseek, anthropic, openai, gemini, ollama, vertex, bedrock
2. **API key** — your provider key (stored in `.clims/credentials.json`, masked in prompts)
3. **Telegram bot token** (optional) — for bot mode
4. **ComfyUI URL** (optional) — for image generation
5. **Permission mode** — default (ask), acceptEdits, plan, bypass

You can skip setup and just set the env var directly:

```bash
export DEEPSEEK_API_KEY="sk-..."
clims
```

---

## 2. Interactive CLI

```bash
clims                              # default provider
clims --provider openai --model gpt-4o
clims --mode acceptEdits           # auto-approve
clims --resume                     # resume last session
clims -i screenshot.png            # attach image
```

### Slash commands

```
/help                        — list all commands
/model [name]                — show/switch model
/style [name]                — show/switch output style
/mode [name]                 — show/switch permission mode
/cost                        — token usage this session
/clear                       — clear context
/compact                     — summarize old turns
/rewind [n]                  — go back n turns
/resume [id]                 — reload a saved session
/init                        — create CLIMS.md template
/memory                      — show memory state
/export [path]               — export conversation as JSON
/config                      — show current config (keys masked)
/doctor                      — system diagnostics
/diagnostics                 — show IDE diagnostics
/status                      — token totals
/permissions                 — show permission rules
/tools                       — list available tools
/mcp                         — list MCP connections
/agents                      — list file-defined agents
/commands                    — list custom slash commands
/update                      — check for updates (if git repo)
/vim                         — toggle vim keybindings
/terminal-setup              — write default keybindings

/research <question>         — deep research (parallel search+fetch+synthesize+fact-check)
/bg <task>                   — background agent task
/tasks                       — list background tasks
/bg-result <id>              — get background task result
/schedule add|list|remove    — recurring tasks
/workflow <name>             — run a workflow
/workflows                   — list available workflows

/bot start|stop|status|log   — Telegram bot control
```

### Plan mode

1. Type your request normally
2. The agent researches read-only and presents a plan
3. You review and type `y` to approve
4. The agent executes the plan

---

## 3. Headless mode (scripting/CI)

```bash
clims -p "Refactor this file"                           # text output
clims -p "Fix all lint errors" --output-format json     # JSON
clims -p "Summarize" --output-format stream-json        # JSONL events
clims -p "Create report" --provider openai --model gpt-4o
```

---

## 4. HTTP API server

```bash
clims-server                    # serves on 127.0.0.1:8765
export CLIMS_SERVER_TOKEN="x"   # optional bearer auth
```

### Endpoints

```
POST /v1/sessions                                → create session
POST /v1/sessions/{id}/messages                  → SSE stream (agent response)
GET  /v1/sessions/{id}                           → session metadata + history
DELETE /v1/sessions/{id}                         → delete
GET  /v1/sessions                                → list
GET  /v1/models                                  → providers + capabilities
POST /v1/tool-results/{tool_use_id}              → approve/deny a tool
GET  /healthz                                    → liveness
```

### SSE event protocol

```
event: text_delta         data: {"text":"..."}
event: thinking_delta     data: {"text":"..."}
event: tool_use           data: {"id":"...","name":"bash","input":{...}}
event: permission_request data: {"tool_use_id":"...","tool":"bash","input":{...}}
event: tool_result        data: {"tool_use_id":"...","is_error":false,"content":[...]}
event: usage              data: {"input_tokens":..,"output_tokens":..}
event: error              data: {"message":"...","type":"..."}
event: done               data: {"stop_reason":"end_turn"}
```

### OpenAI-compatible endpoint

```bash
POST /v1/chat/completions
```

Any OpenAI SDK can target clims_code by changing the base URL. The bearer token is your BYOK provider key; pick the provider with the `x-clims-provider` header.

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:8765/v1",
    api_key="<your-deepseek-key>"
)
# streaming supported too
stream = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "hello"}],
    stream=True
)
```

---

## 5. Telegram bot

```bash
clims-bot
```

Requires a Telegram bot token (set via `/setup` in the interactive CLI or in `.clims/credentials.json`).
The bot runs as a background process and responds to messages in the configured chat.

Commands in Telegram:
```
/start     — welcome + help
/help      — command list
/model     — show/switch model
/mode      — show/switch permission mode
/cancel    — interrupt current response
/config    — show config
/clear     — clear context
/research  — deep research
/setkey    — update a credential
/users     — list/manage allowed users
/admin     — list/manage admins
```

---

## 6. Memory system

Two memory layers:

- **CLIMS.md** — project-level instructions. Place at project root (or `~/.clims/CLIMS.md` for global). Supports `@import path/to/file.md`. Loaded into every system prompt.
- **`.clims/memory/`** — agent's private cross-session notebook. The agent reads/writes it with the `memory` tool. Persists across sessions.

Created with `/init` if it doesn't exist.

---

## 7. Configuration files

Settings merged low → high priority:

```
~/.clims/settings.json
./.clims/settings.json
./.clims/settings.local.json
```

Keys: `provider`, `model`, `permission_mode`, `temperature`, `max_tokens`, `allow`, `deny`, `ask`, `system`, `hooks`, `proactive_memory`, `output_style`, `background_tasks`, `schedules`.

Credentials stored in `.clims/credentials.json` (never committed).

---

## 8. MCP servers

Connect at runtime — just ask:

```
"connect github with <token>"
"connect filesystem for ./data"
"connect postgres with postgresql://..."
```

Or configure in `settings.json`:

```json
{
  "mcp_servers": [
    {"name": "github", "token": "ghp_..."},
    {"name": "filesystem", "args": ["./data"]}
  ]
}
```

Known servers resolvable by name: github, slack, postgres, filesystem, brave-search, gitlab, puppeteer, sqlite, redis, email, playwright, sequential-thinking, everything, fetch, sentry, cloudflare, docker, k8s.

---

## 9. Hooks

Run external scripts on agent lifecycle events. Configured in `settings.json`:

```json
{
  "hooks": {
    "PreToolUse": ["python scripts/audit_tool.py"],
    "Notification": ["notify-send clims 'Task complete'"]
  }
}
```

Events: `SessionStart`, `PreCompact`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `Notification`.

The hook script receives JSON on stdin. Return `{"block": true, "reason": "..."}` to deny, or `{"context": "..."}` to append to the tool result.

---

## 10. Workflows

Python scripts in `.clims/workflows/*.py` that use `WorkflowAPI`:

```python
from clims_core.workflows import WorkflowAPI

def run(api: WorkflowAPI):
    files = api.agent("List changed files").splitlines()
    reviews = api.parallel(
        [lambda f=f: api.agent(f"Review {f}") for f in files]
    )
    api.agent(f"Summarize reviews:\n" + "\n".join(reviews))
```

Run with: `/workflow <name>`

---

## 11. Tests

```bash
pip install -e ".[dev]"
pytest tests/ -q                # 212 offline tests
pytest tests/ -q -k "not render"  # skip rich/capsys tests
```
