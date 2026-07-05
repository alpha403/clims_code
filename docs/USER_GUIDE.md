# clims_code — User Guide (Terminal)

Everything you need to drive the agent efficiently from the terminal.

---

## 1. Mental model

clims_code has two ways to run:

- **Interactive REPL** — a chat session in your terminal. You type, it works, you
  keep talking. Best for real work. → `python -m clims_cli.main`
- **Headless** — run one instruction and exit. Best for scripts/automation. →
  `python -m clims_cli.main -p "do X"`

It operates on the **current working directory** — `cd` into your project first.
It can read/write files, run shell commands, search, and browse the web.

---

## 2. First 5 minutes

```powershell
# 1. set your model key (BYOK) — do this once per terminal session
$env:DEEPSEEK_API_KEY = "sk-..."

# 2. go to the project you want to work in
cd C:\path\to\your\project

# 3. start the agent
python -m clims_cli.main
```

You'll see a banner with provider/model/mode. Now just type what you want:

```
you > list the python files here and tell me what each does
you > create a file hello.py that prints hello world, then run it
you > /exit
```

---

## 3. Startup flags (headless or to override defaults)

| Flag | Meaning | Example |
|------|---------|---------|
| `-p "..."` | headless: run one prompt and exit | `-p "summarize README.md"` |
| `--provider` | which model API | `--provider deepseek` |
| `--model` | which model | `--model deepseek-chat` |
| `--mode` | permission mode | `--mode bypass` |
| `--output-format` | `text` / `json` / `stream-json` | `--output-format json` |
| `--resume` | resume your most recent session | `--resume` |
| `-i PATH` | attach an image (repeatable) | `-i screenshot.png` |

Example — one-shot, no prompts, JSON out:
```powershell
python -m clims_cli.main -p "count lines in app.py" --mode bypass --output-format json
```

---

## 4. Permission modes (IMPORTANT — controls how much it asks)

| Mode | Behavior | Use when |
|------|----------|----------|
| `default` | asks before running commands / writing files | normal, cautious work |
| `acceptEdits` | auto-allows file writes/edits; still asks for shell | editing-heavy tasks |
| `plan` | read-only — researches & proposes, changes nothing | "what would you do?" |
| `bypass` | allows everything, no prompts | trusted, fast iteration |

Set at start with `--mode bypass`, or switch live with `/mode bypass` or `/auto`.

---

## 5. Slash commands (type these in the REPL)

**Session**
- `/help` — list commands
- `/exit` `/quit` — leave
- `/clear` — wipe the conversation context (fresh start)
- `/rewind [n]` — undo the last n turns
- `/resume` — reload your most recent session
- `/export [file]` — save the transcript to markdown
- `/cost` — tokens used this session

**Model & behavior**
- `/model` — show current model · `/model deepseek-reasoner` — switch live
- `/mode [name]` — show/set permission mode · `/auto` — toggle auto-accept
- `/style [name]` — output style: default|concise|explanatory|formal|bullet

**Inspect**
- `/tools` — list available tools
- `/permissions` — show mode + allow/deny/ask rules
- `/config` — show current config (key redacted)
- `/doctor` (`/status`) — health check (python, providers, tools, mcp, key)
- `/mcp` — list connected MCP servers · `/agents` `/commands` `/skills` — list those
- `/hooks` — list configured hooks · `/diagnostics` — show editor diagnostics

**Memory & maintenance**
- `/init` — create a CLIMS.md template in this project
- `/memory` — show loaded CLIMS.md memory
- `/compact` — summarize the conversation to free context
- `/update [now]` — check/run a self-update

**Research & dev workflow**
- `/research <question>` — deep research: fans out searches, fetches sources in parallel,
  synthesizes a cited answer, and fact-checks it
- `/review` — review your current git diff
- `/bug` — write a bug report (env + recent transcript)
- `/pr-comments` — show PR comments (needs `gh` CLI)
- `/terminal-setup` — write default keybindings + tips
- `/vim` — info on enabling vim editing

---

## 6. Power moves (efficiency)

- **@-mention files**: drop `@path/to/file` in your message and its contents are
  pulled in automatically. `you > explain the bug in @app.py`
- **Custom commands**: put a markdown prompt template in `.clims/commands/<name>.md`
  (use `$ARGUMENTS`); invoke with `/<name> ...`. Great for repeated workflows.
- **Project rules**: create `CLIMS.md` (run `/init`) and write conventions there —
  it's injected into every prompt. e.g. "Always use type hints. Tests live in /tests."
- **Persistent memory**: ask it to "remember X" and it uses the `memory` tool
  (stored in `.clims/memory/`) — survives across sessions.
- **Subagents**: "use a subagent to research X" spins up a focused child agent.
- **Plan first on big tasks**: start in `--mode plan`, review the plan, then `/mode acceptEdits`.
- **Switch models per task**: `/model` to a stronger model for hard reasoning, cheaper for routine.

---

## 7. Config files (set once, applies every run)

Merged low→high precedence:
- `~/.clims/settings.json` (global) → `./.clims/settings.json` (project) →
  `./.clims/settings.local.json` (project, gitignored)

Example `./.clims/settings.json`:
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "permission_mode": "default",
  "output_style": "concise",
  "allow": ["Read(*)", "Glob(*)", "Bash(git status*)"],
  "deny": ["Bash(rm -rf *)"],
  "ask": ["Bash(*)", "Write(*)"]
}
```

MCP servers go under `"mcpServers"` here, or in `./.clims/mcp.json`.

---

## 8. Useful environment variables

| Var | Effect |
|-----|--------|
| `DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | provider keys (BYOK) |
| `CLIMS_API_KEY` | generic key used regardless of provider |
| `CLIMS_PROVIDER` / `CLIMS_MODEL` / `CLIMS_PERMISSION_MODE` | defaults |
| `CLIMS_MARKDOWN=1` | render final answers as markdown (needs `rich`) |
| `CLIMS_VIM=1` | vim editing (needs `prompt_toolkit`) |
| `CLIMS_NOTIFY=0` | mute the completion bell |
| `CLIMS_PROXY=http://...` | route HTTP through a proxy |
| `CLIMS_SHELL` | force a specific shell for the bash tool |

---

## 8b. Proactive memory & self-documentation (on by default)

The agent keeps continuity for you automatically:
- **At session start** it reads `.clims/memory/` + any `CLIMS.md`, `PROGRESS.md`,
  `DECISIONS.md`, `ARCHITECTURE.md` and continues from them.
- **As it works** it records durable facts/preferences/decisions to `.clims/memory/`
  via the `memory` tool (never secrets — only where to find them).
- **On real multi-step projects** it creates & maintains **PROGRESS.md**, **DECISIONS.md**,
  and **ARCHITECTURE.md** at the project root (skipped for trivial one-off tasks).

Control it:
- `/memory` — review what it's tracking (CLIMS.md, memory files, tracking docs).
- Turn it off: `$env:CLIMS_NO_PROACTIVE_MEMORY = "1"` or `"proactive_memory": false` in settings.
- Next session, run with `--resume` (or `/resume`) to pick up where you left off.

## 9. Safety quick facts
- It can only touch files **inside the working directory** (workspace boundary).
- `.clims-ignore` (gitignore-style) blocks files it must never read/write.
- Default-ignored: `.env`, `*.key`, `id_rsa`, `.git/**`.
- In `default` mode it asks before anything risky.

---

## 10. Cheat sheet (the 10 you'll use most)

```
python -m clims_cli.main            # start
/mode bypass                        # stop asking (trusted work)
@file.py                            # pull a file into your message
/model deepseek-reasoner            # switch model
/plan ... then /mode acceptEdits    # plan, then execute
/rewind                             # undo last turn
/clear                              # fresh context
/compact                            # free up context on long sessions
/cost                               # token usage
/exit                               # leave
```
