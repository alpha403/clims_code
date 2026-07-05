# Usage

`clims_code` has three entry points: the **CLI**, the **HTTP API server**, and the
**engine as a library**. The engine needs no third-party packages.

## 0. BYOK — set a provider key

```powershell
# DeepSeek (validated)
$env:DEEPSEEK_API_KEY = "sk-..."
# or Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
# or a generic override used regardless of provider
$env:CLIMS_API_KEY = "..."
```

Keys are read from the environment, used in memory, and **never written to disk**.

## 1. CLI

```powershell
# interactive REPL
python -m clims_cli.main

# choose provider/model/permission-mode
python -m clims_cli.main --provider deepseek --model deepseek-chat --mode default

# headless (one prompt, exit) — good for scripting/CI
python -m clims_cli.main -p "Summarize every .py file in this folder"
```

Permission modes: `default` (ask before exec/write), `acceptEdits`, `plan` (read-only),
`bypass` (allow all — only for trusted automation).

## 2. HTTP API server (the product surface)

```powershell
$env:CLIMS_SERVER_TOKEN = "my-product-token"   # optional product auth
python -m clims_server.api                       # serves on 127.0.0.1:8765
```

Example session (BYOK key travels in the request body):

```bash
# create a session
curl -s -X POST localhost:8765/v1/sessions
# -> {"session_id":"sess_..."}

# send a message, stream SSE
curl -N -X POST localhost:8765/v1/sessions/sess_xxx/messages \
  -H "Content-Type: application/json" \
  -d '{"provider":"deepseek","model":"deepseek-chat","api_key":"sk-...",
       "message":"create hello.txt with the text hi","permission_mode":"acceptEdits"}'

# list models
curl -s localhost:8765/v1/models
```

Run behind nginx/Caddy for TLS and concurrency (the server uses stdlib HTTP).

### OpenAI-compatible endpoint (drop-in integration)

Any OpenAI SDK/client can target clims_code by changing the base URL. The bearer
token is your BYOK provider key; pick the provider with the `x-clims-provider` header.

```bash
curl -s localhost:8765/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "x-clims-provider: deepseek" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8765/v1", api_key="<your-deepseek-key>")
client.chat.completions.create(model="deepseek-chat",
    messages=[{"role": "user", "content": "hello"}])  # streaming supported too
```

### Headless output formats

```powershell
python -m clims_cli.main -p "list files" --output-format json         # one JSON object
python -m clims_cli.main -p "list files" --output-format stream-json  # JSONL events
```

## 3. As a library (SDK)

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
result = agent.send([Message.user("List the files here and summarize.")],
                    on_event=lambda e: print(e.text, end=""))
```

## 4. Memory (CLIMS.md)

Drop a `CLIMS.md` in your project (or `~/.clims/CLIMS.md` for global rules). Its
content is injected into the system prompt. Supports `@import path/to/file.md`.

## 5. Settings

JSON files merged low→high precedence:
`~/.clims/settings.json` → `./.clims/settings.json` → `./.clims/settings.local.json`.
Keys: `provider`, `model`, `permission_mode`, `temperature`, `max_tokens`,
`allow`, `deny`, `ask`, `system`.

## 6. Tests & benchmarks

```powershell
python -m pytest tests -q                                   # offline unit tests
python -m bench.live_smoke                                  # live smoke (needs key)
python -m bench.run_benchmarks --suite all --trials 3       # full benchmark
```
