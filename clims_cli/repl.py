"""Interactive REPL — the first client of the clims_code engine.

Plain stdlib rendering (rich optional, added in Phase 2). Wires:
  config → provider → tools → permission policy → ToolRuntime → Agent
and streams events to the terminal.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from clims_core.agent.loop import Agent, DEFAULT_SYSTEM
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.config import Config, load_config
from clims_core.memory import load_memory
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers import get_provider
from clims_core.providers.base import StreamEvent
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext


BANNER = "clims_code — general-purpose agent · /help for commands · /exit to quit"

# built-in slash commands (for the autocomplete popup)
SLASH_COMMANDS = {
    "/help": "list commands", "/exit": "quit", "/quit": "quit",
    "/clear": "reset conversation context", "/model": "show / switch model",
    "/tools": "list available tools", "/mcp": "MCP servers (connected + known)",
    "/mode": "permission mode", "/auto": "toggle auto-accept edits",
    "/cost": "token usage this session", "/memory": "show loaded memory",
    "/compact": "summarize to free context", "/rewind": "undo last turn(s)",
    "/resume": "reload most recent session", "/init": "create CLIMS.md template",
    "/agents": "list file-defined agents", "/commands": "list custom commands",
    "/skills": "list skills", "/export": "save transcript to markdown",
    "/permissions": "show permission rules", "/config": "show config",
    "/doctor": "health check", "/status": "status", "/diagnostics": "editor diagnostics",
    "/update": "self-update", "/vim": "vim editing info", "/terminal-setup": "keybindings",
    "/style": "output style", "/hooks": "list configured hooks",
    "/research": "deep web research (cited)", "/bg": "run a task in the background",
    "/tasks": "list background tasks", "/bg-result": "show a background result",
    "/schedule": "recurring tasks", "/workflow": "run a workflow",
    "/workflows": "list workflows", "/review": "review git diff",
    "/bug": "write a bug report", "/pr-comments": "show PR comments",
}


def _approve(name: str, tool_input: dict, target: str) -> bool:
    """Interactive permission prompt for ASK decisions."""
    print(f"\n  ⚠  Allow tool '{name}'?  {target}")
    try:
        ans = input("     [y]es / [n]o > ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def _stdout_write(text: str) -> None:
    """Write text to stdout as raw UTF-8 bytes, bypassing Windows cp1252 codec issues.

    Rich / prompt_toolkit replace sys.stdout with their own wrapper whose encoding
    is determined at runtime from the Windows console code page (often cp1252).
    Writing directly to sys.stdout.buffer with an explicit encode skips that layer.
    Falls back to normal sys.stdout.write() on platforms where .buffer isn't available.
    """
    try:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    except AttributeError:
        # No .buffer (e.g. IDLE, some test environments) — best-effort
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:
            sys.stdout.write(text.encode("ascii", errors="replace").decode("ascii"))


def _stdout_flush() -> None:
    try:
        sys.stdout.buffer.flush()
    except AttributeError:
        sys.stdout.flush()


def _make_event_printer(suppress_text: bool = False):
    from clims_cli import render
    state = {"in_text": False, "in_think": False, "buf": []}

    def flush_md():
        text = "".join(state["buf"]).strip()
        state["buf"] = []
        if text:
            render.render_markdown(text)

    def on_event(ev: StreamEvent) -> None:
        if ev.type == "thinking_delta":
            if suppress_text:
                return
            if not state["in_think"]:
                _stdout_write("\n\033[2m[thinking] ")
                state["in_think"] = True
            _stdout_write(ev.text)
        elif ev.type == "text_delta":
            if state["in_think"]:
                _stdout_write("\033[0m\n")
                state["in_think"] = False
            if suppress_text:
                state["buf"].append(ev.text)
                return
            state["in_text"] = True
            _stdout_write(ev.text)
        elif ev.type == "tool_use":
            if suppress_text:
                flush_md()
            elif state["in_text"]:
                _stdout_write("\n")
                state["in_text"] = False
            render.print_tool_call(ev.tool_name, ev.tool_input)
        elif ev.type == "tool_result":
            render.print_tool_result(ev.message, ev.is_error)
        elif ev.type == "error":
            render.panel("error", ev.message) if render.supports_rich() else \
                _stdout_write(f"\n  [error] {ev.message}\n")
        elif ev.type == "done":
            if suppress_text:
                flush_md()
            elif state["in_text"]:
                _stdout_write("\n")
                state["in_text"] = False
        _stdout_flush()

    return on_event


def _short(d: dict) -> str:
    s = ", ".join(f"{k}={_short_text(str(v))}" for k, v in d.items())
    return s[:120]


def _short_text(s: str) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= 100 else s[:100] + "…"


def build_agent(cfg: Config, cwd: Path, extra_tools=None, unrestricted: bool = False) -> Agent:
    provider = get_provider(cfg.provider)
    tools = default_tools()
    mcp_mgr = None
    if cfg.mcp_servers:
        from clims_core.mcp import MCPManager
        mcp_mgr = MCPManager()
        errors = mcp_mgr.connect_all({"mcpServers": cfg.mcp_servers})
        for e in errors:
            print(f"  [mcp] failed: {e}")
        mcp_tools = mcp_mgr.tools()
        if mcp_tools:
            print(f"  [mcp] connected {len(cfg.mcp_servers)} server(s), "
                  f"{len(mcp_tools)} tool(s)")
        tools += mcp_tools
    policy = PermissionPolicy(
        mode=PermissionMode(cfg.permission_mode),
        allow=cfg.allow, deny=cfg.deny, ask=cfg.ask,
    )
    ctx = ToolContext(cwd=cwd)
    hooks = None
    if cfg.hooks:
        from clims_core.hooks import HookRunner
        hooks = HookRunner(cfg.hooks, cwd=cwd)

    # subagent: children get the built-in tools but NOT a subagent (bounds recursion)
    from clims_core.styles import style_suffix
    from clims_core.agent.loop import assemble_system
    from clims_core.memory import memory_digest
    base_system = (cfg.system or DEFAULT_SYSTEM) + style_suffix(cfg.output_style)
    memory = load_memory(cwd)
    digest = memory_digest(cwd) if cfg.proactive_memory else ""
    system = assemble_system(base_system, memory=memory, digest=digest,
                             proactive=cfg.proactive_memory)

    if extra_tools:
        tools = tools + list(extra_tools)

    from clims_core.commands import load_agents
    file_agents = load_agents(cwd)

    from clims_core.agent_types import get_agent_spec, filter_tools

    def _spawn(task: str, agent_type: str | None = None) -> str:
        child_system = system
        child_model = cfg.model
        child_tools = default_tools()
        child_max_iter = 20
        spec = get_agent_spec(agent_type)
        if agent_type and agent_type in file_agents:        # file-defined agent
            adef = file_agents[agent_type]
            child_system = adef.system or system
            child_model = adef.model or cfg.model
        elif spec is not None:                               # built-in specialist
            child_system = spec.system
            child_tools = filter_tools(child_tools, spec.tools)
            child_max_iter = spec.max_iterations
        child_runtime = ToolRuntime(tool_map(child_tools), policy,
                                    ToolContext(cwd=cwd), approve=_approve, hooks=hooks)
        child = Agent(provider=provider, model=child_model, api_key=cfg.api_key,
                      runtime=child_runtime, system=child_system,
                      temperature=cfg.temperature, max_tokens=cfg.max_tokens,
                      max_iterations=child_max_iter)
        res = child.send([Message.user(task)], lambda e: None)
        return res.messages[-1].text() if res.messages else ""

    from clims_core.agent.subagent import SubagentTool
    from clims_core.tools.config_tool import ConfigTool
    session_holder: dict = {}  # populated with the live agent below
    config_tool = ConfigTool(policy, cwd, session_holder)
    tools = tools + [SubagentTool(_spawn), config_tool]
    # vision sidecar: give the agent eyes when a vision provider is configured,
    # even if the main (text) model can't see (e.g. DeepSeek + Gemini for vision).
    if cfg.vision_provider and cfg.vision_api_key:
        from clims_core.tools.analyze_image import AnalyzeImageTool
        tools = tools + [AnalyzeImageTool(cfg.vision_provider, cfg.vision_model,
                                          cfg.vision_api_key)]

    from clims_core.safety import PathGuard, load_ignore
    if unrestricted:
        path_guard = PathGuard(enabled=False)   # no workspace boundary for Telegram
    else:
        path_guard = PathGuard(roots=[cwd], ignore=load_ignore(cwd))
    runtime = ToolRuntime(tool_map(tools), policy, ctx, approve=_approve,
                          hooks=hooks, path_guard=path_guard)
    agent = Agent(
        provider=provider,
        model=cfg.model,
        api_key=cfg.api_key,
        runtime=runtime,
        system=system,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )
    agent._mcp_mgr = mcp_mgr  # keep MCP subprocesses alive for the agent's lifetime
    # let the configure tool apply live changes (permissions, model, MCP servers, …)
    session_holder["agent"] = agent
    session_holder["runtime"] = runtime
    session_holder["mcp_mgr"] = mcp_mgr
    return agent


def _bot_is_running(pid: int) -> bool:
    """Check if a process with this PID is alive (cross-platform, no psutil needed)."""
    if sys.platform == "win32":
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return False
    else:
        import os as _os
        try:
            _os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def _start_telegram_bot(cwd: Path, verbose: bool = False) -> bool:
    """
    Launch clims_cli.telegram_bot as a detached background module.
    Logs to .clims/_bot.log so errors are visible via /bot log.
    Returns True if the bot is running after this call.
    Safe to call repeatedly — no-op if already running.
    """
    import json as _json
    import subprocess

    creds_file = cwd / ".clims" / "credentials.json"
    pid_file   = cwd / ".clims" / "_bot.pid"
    log_file   = cwd / ".clims" / "_bot.log"

    try:
        creds = _json.loads(creds_file.read_text(encoding="utf-8")) if creds_file.exists() else {}
    except Exception:
        creds = {}

    if not creds.get("telegram_bot_token"):
        if verbose:
            print("  [telegram] no bot token in credentials — run /setup to configure")
        return False

    # Already running?
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if _bot_is_running(pid):
                if verbose:
                    print(f"  [telegram] bot already running (PID {pid})")
                return True
        except Exception:
            pass

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Tell the bot where to find credentials (may differ from its own cwd)
    env = os.environ.copy()
    env["CLIMS_CREDS_FILE"] = str(creds_file)

    try:
        with open(log_file, "a", encoding="utf-8") as lf:
            if sys.platform == "win32":
                # pythonw.exe = no console window on Windows
                pythonw = Path(sys.executable).parent / "pythonw.exe"
                exe = str(pythonw) if pythonw.exists() else sys.executable
                proc = subprocess.Popen(
                    [exe, "-m", "clims_cli.telegram_bot"],
                    env=env, cwd=str(cwd),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                )
            else:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "clims_cli.telegram_bot"],
                    env=env, cwd=str(cwd),
                    start_new_session=True,
                    stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                )
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        print(f"  [telegram] bot started (PID {proc.pid})  — /bot log to see output")
        return True
    except Exception as exc:
        print(f"  [telegram] could not start bot: {exc}")
        return False


def _stop_telegram_bot(cwd: Path) -> None:
    """Kill the tracked bot process (cross-platform)."""
    pid_file = cwd / ".clims" / "_bot.pid"
    if not pid_file.exists():
        print("  [telegram] bot is not running (no PID file)")
        return
    try:
        pid = int(pid_file.read_text().strip())
        if not _bot_is_running(pid):
            print("  [telegram] bot already stopped (stale PID)")
            pid_file.unlink(missing_ok=True)
            return
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(
                ctypes.windll.kernel32.OpenProcess(1, False, pid), 0)
        else:
            import os as _os, signal as _sig
            _os.kill(pid, _sig.SIGTERM)
        pid_file.unlink(missing_ok=True)
        print(f"  [telegram] bot stopped (PID {pid})")
    except Exception as exc:
        print(f"  [telegram] could not stop bot: {exc}")


def _bot_status(cwd: Path) -> None:
    """Print current bot status."""
    import json as _json
    pid_file   = cwd / ".clims" / "_bot.pid"
    creds_file = cwd / ".clims" / "credentials.json"
    log_file   = cwd / ".clims" / "_bot.log"

    try:
        creds = _json.loads(creds_file.read_text(encoding="utf-8")) if creds_file.exists() else {}
    except Exception:
        creds = {}

    token  = creds.get("telegram_bot_token", "")
    users  = creds.get("telegram_allowed_users", [])
    has_tok = bool(token)

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            running = _bot_is_running(pid)
        except Exception:
            pid, running = None, False
    else:
        pid, running = None, False

    print(f"  [telegram] status   : {'RUNNING' if running else 'STOPPED'}"
          + (f" (PID {pid})" if running and pid else ""))
    print(f"  [telegram] token    : {'set (' + token[:8] + '...)' if has_tok else 'NOT SET — run /setup'}")
    print(f"  [telegram] allowed  : {users if users else 'none set (open to all)'}")
    print(f"  [telegram] log      : {log_file}")

    if not running and has_tok:
        print("  [telegram] hint     : type '/bot start' to launch")


def _register_windows_startup(cwd: Path) -> None:
    """
    Add telegram_bot.py to Windows HKCU startup so it runs automatically
    on every login — no manual start needed ever.
    """
    import winreg
    pythonw  = Path(sys.executable).parent / "pythonw.exe"
    exe      = str(pythonw) if pythonw.exists() else sys.executable
    cmd      = f'"{exe}" -m clims_cli.telegram_bot'
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "ClimsTelegramBot", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print("  [telegram] registered to auto-start on Windows login")
    except Exception as exc:
        print(f"  [telegram] could not register startup: {exc}")


def _inject_credentials(cwd: Path) -> None:
    """Load .clims/credentials.json and inject keys into os.environ so load_config picks them up."""
    import json as _json
    creds_file = cwd / ".clims" / "credentials.json"
    if not creds_file.exists():
        return
    try:
        creds = _json.loads(creds_file.read_text(encoding="utf-8"))
    except Exception:
        return
    if creds.get("llm_api_key"):
        os.environ.setdefault("CLIMS_API_KEY", creds["llm_api_key"])
    if creds.get("google_api_key"):
        os.environ.setdefault("GOOGLE_API_KEY", creds["google_api_key"])
        os.environ.setdefault("GEMINI_API_KEY", creds["google_api_key"])
    if creds.get("meta_ads_token"):
        os.environ.setdefault("META_ADS_TOKEN", creds["meta_ads_token"])
    if creds.get("comfyui_api_url"):
        os.environ.setdefault("COMFYUI_API_URL", creds["comfyui_api_url"])
    if creds.get("comfyui_model"):
        os.environ.setdefault("COMFYUI_MODEL", creds["comfyui_model"])


_PROVIDER_DEFAULTS = {
    "deepseek":  ("deepseek-chat",      "DEEPSEEK_API_KEY"),
    "anthropic": ("claude-sonnet-4-6",  "ANTHROPIC_API_KEY"),
    "openai":    ("gpt-4o",             "OPENAI_API_KEY"),
    "gemini":    ("gemini-2.5-flash",   "GEMINI_API_KEY"),
    "ollama":    ("llama3.2",           None),
}


def _first_run_setup(cwd: Path) -> "Config":
    """
    Chat-style first-run wizard that runs inside the clims terminal before the
    agent starts.  Collects all credentials, saves them to
    .clims/credentials.json + .clims/settings.json, injects env vars, and
    returns a freshly loaded Config.  No LLM needed.
    """
    import json as _json

    CREDS_FILE    = cwd / ".clims" / "credentials.json"
    SETTINGS_FILE = cwd / ".clims" / "settings.json"

    try:
        creds = _json.loads(CREDS_FILE.read_text(encoding="utf-8")) if CREDS_FILE.exists() else {}
    except Exception:
        creds = {}

    def say(*lines: str) -> None:
        for line in lines:
            print(f"\n  clims > {line}")

    def ask(hint: str = "") -> str:
        if hint:
            print(f"          {hint}")
        try:
            return input("  you   > ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def mask(k: str) -> str:
        return f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"

    say(
        "Hey! Before we get started I need a few details from you.",
        "This only happens once — I'll save everything so you never have to set it again.",
    )

    # ── LLM provider ──────────────────────────────────────────────────────────
    say("Which LLM provider do you want to use?",
        "Options: deepseek  anthropic  openai  gemini  ollama")
    cur_prov = creds.get("llm_provider", "deepseek")
    raw = ask(f"(current: {cur_prov} — press Enter to keep)")
    provider = raw if raw in _PROVIDER_DEFAULTS else cur_prov
    creds["llm_provider"] = provider

    default_model, _ = _PROVIDER_DEFAULTS[provider]
    cur_model = creds.get("llm_model", default_model)
    say(f"Which {provider} model?")
    raw = ask(f"(default: {cur_model})")
    creds["llm_model"] = raw or cur_model

    if provider != "ollama":
        cur_key = creds.get("llm_api_key", "")
        say(f"Your {provider.capitalize()} API key:")
        raw = ask(f"(current: {mask(cur_key)})" if cur_key else "")
        if raw:
            creds["llm_api_key"] = raw

    # ── Telegram bot token ────────────────────────────────────────────────────
    say(
        "Now let's set up Telegram so you can reach me from anywhere.",
        "Go to Telegram → message @BotFather → /newbot → copy the token.",
    )
    cur_tok = creds.get("telegram_bot_token", "")
    raw = ask(f"(current: {mask(cur_tok)})" if cur_tok else "")
    if raw:
        creds["telegram_bot_token"] = raw

    # ── Telegram allowed users ────────────────────────────────────────────────
    say(
        "What are your Telegram user ID(s)?",
        "Message @userinfobot on Telegram to find yours.",
        "Separate multiple IDs with commas. The first one is the admin.",
    )
    cur_ids = creds.get("telegram_allowed_users", [])
    cur_str = ", ".join(str(i) for i in cur_ids)
    raw = ask(f"(current: {cur_str})" if cur_str else "")
    if raw:
        try:
            creds["telegram_allowed_users"] = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            say("Couldn't parse those IDs — keeping existing. Add more with /adduser in Telegram.")

    # ── Optional: Google API key ──────────────────────────────────────────────
    say("Optional — Google / Gemini API key (image generation + vision).",
        "Press Enter to skip.")
    cur_g = creds.get("google_api_key", "")
    raw = ask(f"(current: {mask(cur_g)})" if cur_g else "")
    if raw:
        creds["google_api_key"] = raw

    # ── Optional: Meta Ads token ──────────────────────────────────────────────
    say("Optional — Meta Ads access token (autonomous ad campaigns).",
        "Press Enter to skip.")
    cur_m = creds.get("meta_ads_token", "")
    raw = ask(f"(current: {mask(cur_m)})" if cur_m else "")
    if raw:
        creds["meta_ads_token"] = raw

    # ── Optional: ComfyUI ────────────────────────────────────────────────────
    say("Optional — ComfyUI API URL for local AI image generation.",
        "Example: http://100.84.108.103:8188   Press Enter to skip.")
    cur_cu = creds.get("comfyui_api_url", "")
    raw = ask(f"(current: {cur_cu})" if cur_cu else "")
    if raw:
        creds["comfyui_api_url"] = raw.rstrip("/")
        say("Which model checkpoint? (default: flux1-dev.safetensors)")
        cur_cm = creds.get("comfyui_model", "flux1-dev.safetensors")
        raw2 = ask(f"(current: {cur_cm})")
        creds["comfyui_model"] = raw2 or cur_cm

    # ── Persist ───────────────────────────────────────────────────────────────
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(_json.dumps(creds, indent=2), encoding="utf-8")

    try:
        settings = _json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
    except Exception:
        settings = {}
    settings["provider"] = creds["llm_provider"]
    settings["model"]    = creds.get("llm_model", "")
    SETTINGS_FILE.write_text(_json.dumps(settings, indent=2), encoding="utf-8")

    # Inject into env so the freshly loaded Config picks them up
    if creds.get("llm_api_key"):
        os.environ["CLIMS_API_KEY"] = creds["llm_api_key"]
    if creds.get("google_api_key"):
        os.environ["GOOGLE_API_KEY"] = creds["google_api_key"]
        os.environ["GEMINI_API_KEY"] = creds["google_api_key"]
    if creds.get("meta_ads_token"):
        os.environ["META_ADS_TOKEN"] = creds["meta_ads_token"]
    if creds.get("comfyui_api_url"):
        os.environ["COMFYUI_API_URL"] = creds["comfyui_api_url"]
    if creds.get("comfyui_model"):
        os.environ["COMFYUI_MODEL"] = creds["comfyui_model"]

    # Start the bot immediately in the background
    _start_telegram_bot(cwd)

    say(
        "All set! Credentials saved — you won't be asked again.",
        "The Telegram bot is running in the background.",
        "Starting your agent now...",
    )
    print()

    return load_config(cwd)


def run() -> int:
    cwd = Path.cwd()
    _inject_credentials(cwd)        # load credentials.json → os.environ before config reads them
    cfg = load_config(cwd)
    if not cfg.api_key:
        cfg = _first_run_setup(cwd) # chat-style wizard, no env vars needed
    else:
        _start_telegram_bot(cwd)    # ensure bot is running on every clims launch

    # Background watcher: auto-start the bot if credentials appear mid-session.
    # 60s cooldown prevents spawning a new instance while one is still starting up.
    import threading as _threading, time as _time
    _bot_watcher_last = [0.0]
    def _bot_watcher_loop():
        while True:
            _time.sleep(15)
            pid_file = cwd / ".clims" / "_bot.pid"
            # Skip if PID file was written in the last 60 seconds (bot may still be starting)
            if pid_file.exists():
                try:
                    age = _time.time() - pid_file.stat().st_mtime
                    if age < 60:
                        continue
                except OSError:
                    pass
            _start_telegram_bot(cwd)
    _watcher = _threading.Thread(target=_bot_watcher_loop, daemon=True, name="bot-watcher")
    _watcher.start()

    from clims_cli import render
    from clims_core import __version__
    render.print_logo(version=__version__)
    vis = f"  ·  vision={cfg.vision_provider}:{cfg.vision_model}" if cfg.vision_provider and cfg.vision_api_key else ""
    print(f"  provider={cfg.provider}  model={cfg.model}  mode={cfg.permission_mode}  "
          f"key={'set' if cfg.api_key else 'MISSING'}{vis}  ·  /help  ·  /exit")

    agent = build_agent(cfg, cwd)  # noqa: F821
    # SessionStart hook
    _hooks = getattr(agent.runtime, "hooks", None)
    if _hooks and _hooks.has("SessionStart"):
        _hooks.run_event("SessionStart", {"cwd": str(cwd)})
    from clims_cli import render
    # rich markdown rendering is the default when available (cleaner, Claude-Code-like);
    # set CLIMS_NO_MARKDOWN=1 to force plain streaming.
    markdown_mode = render.supports_rich() and os.environ.get("CLIMS_NO_MARKDOWN") != "1"
    on_event = _make_event_printer(suppress_text=markdown_mode)
    history: list[Message] = []
    totals = {"in": 0, "out": 0}

    from clims_core.commands import load_commands, load_skills, expand_command
    from clims_core.checkpoints import Checkpoints
    from clims_core.session.store import SQLiteSessionStore
    custom_commands = load_commands(cwd)
    skills = load_skills(cwd)
    for sname, sk in skills.items():  # skills are invocable like commands
        custom_commands.setdefault(sname, sk.body)
    if custom_commands:
        print(f"  [commands] {', '.join('/' + c for c in custom_commands)}")

    checkpoints = Checkpoints()
    db = Path.home() / ".clims" / "sessions.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteSessionStore(str(db))
    if os.environ.get("CLIMS_RESUME"):
        last = store.latest_id()
        if last and store.get(last):
            history = store.get(last)
            sid = last
            print(f"  [resume] loaded session {sid} ({len(history)} messages)")
        else:
            sid = store.create()
    else:
        sid = store.create()

    from clims_cli.prompt import Input
    # build the autocomplete catalog: built-ins + custom commands + skills
    completion_cmds = dict(SLASH_COMMANDS)
    for c in custom_commands:
        completion_cmds.setdefault("/" + c, "custom command")
    for s in skills:
        completion_cmds.setdefault("/" + s, "skill")
    def _status_fn():
        return render.status_text(cfg.provider, agent.model,
                                  agent.runtime.policy.mode.value, totals["in"], totals["out"])
    reader = Input(vim=bool(os.environ.get("CLIMS_VIM")), commands=completion_cmds,
                   status_fn=_status_fn)

    # orchestration: background tasks + recurring scheduler
    import time as _time
    from clims_core.background import BackgroundTasks
    from clims_core.scheduler import Scheduler, SchedulerLoop
    from clims_core.orchestrate import spawn_agent as _spawn_agent
    from clims_cli.notify import notify as _notify
    bg = BackgroundTasks(on_complete=lambda t: _notify(f"background {t.label}: {t.status}"))
    scheduler = Scheduler()
    sched_loop = SchedulerLoop(
        scheduler,
        runner=lambda p: bg.start(
            lambda pp=p: _spawn_agent(provider=agent.provider, model=agent.model,
                                      api_key=agent.api_key, task=pp, cwd=cwd),
            label=f"sched:{p[:20]}"),
        clock=_time.time, tick_seconds=30)
    if scheduler.list():
        sched_loop.start()
    pending_exec = None  # plan-mode approve→execute carries the follow-up here

    while True:
        if pending_exec is not None:
            user, pending_exec = pending_exec, None
        else:
            try:
                user = reader.read("\nyou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.")
                return 0
        if not user:
            continue
        if user.startswith("/"):
            name = user[1:].split()[0] if len(user) > 1 else ""
            low = user.split()[0]
            if low == "/rewind":
                n = int(user.split()[1]) if len(user.split()) > 1 and user.split()[1].isdigit() else 1
                restored = checkpoints.rewind(n)
                history = restored if restored is not None else history
                print(f"  rewound {n} step(s) -> {len(history)} messages")
                continue
            if low == "/resume":
                last = store.latest_id()
                loaded = store.get(last) if last else None
                if loaded:
                    history = loaded
                    sid = last
                    print(f"  resumed session {sid} ({len(history)} messages)")
                else:
                    print("  no saved session to resume")
                continue
            if low == "/skills":
                print("  " + (", ".join(f"{n}: {s.description}" for n, s in skills.items())
                              if skills else "no skills (.clims/skills/)"))
                continue
            if low == "/bug":
                from clims_core.devtools import bug_report
                tail = "\n".join(f"{m.role}: {m.text()}" for m in history[-6:])
                (cwd / "clims_bug_report.md").write_text(
                    bug_report(cfg.provider, cfg.model, tail), encoding="utf-8")
                print("  wrote clims_bug_report.md")
                continue
            if low == "/pr-comments":
                import subprocess
                try:
                    r = subprocess.run(["gh", "pr", "view", "--comments"], cwd=str(cwd),
                                       capture_output=True, text=True, timeout=30)
                    print(r.stdout or r.stderr or "(no output)")
                except FileNotFoundError:
                    print("  gh CLI not found — install GitHub CLI for /pr-comments")
                except Exception as e:
                    print(f"  /pr-comments: {e}")
                continue
            if low == "/research":
                q = user[len("/research"):].strip()
                if not q:
                    print("  usage: /research <question>")
                    continue
                _run_research(agent, q)
                continue
            if low == "/bg":
                q = user[len("/bg"):].strip()
                if not q:
                    print("  usage: /bg <task>")
                    continue
                tid = bg.start(
                    lambda qq=q: _spawn_agent(provider=agent.provider, model=agent.model,
                                              api_key=agent.api_key, task=qq, cwd=cwd),
                    label=q[:40])
                print(f"  started background task {tid} (use /tasks, /bg-result {tid})")
                continue
            if low == "/tasks":
                from clims_cli import render
                render.print_tasks(bg.list())
                continue
            if low == "/bg-result":
                toks = user.split()
                t = bg.get(toks[1]) if len(toks) > 1 else None
                if not t:
                    print("  usage: /bg-result <id>")
                else:
                    print(f"  [{t.status}]\n{t.result or t.error or '(still running)'}")
                continue
            if low == "/schedule":
                toks = user.split()
                sub = toks[1] if len(toks) > 1 else "list"
                if sub == "list":
                    ss = scheduler.list()
                    if not ss:
                        print("  no schedules")
                    for s in ss:
                        print(f"  {s.id} every {s.interval_seconds}s "
                              f"[{'on' if s.enabled else 'off'}] {s.label}")
                elif sub == "remove" and len(toks) > 2:
                    print("  removed" if scheduler.remove(toks[2]) else "  unknown id")
                elif sub == "add" and len(toks) > 3:
                    secs = _parse_interval(toks[2])
                    prompt = user.split(None, 3)[3]
                    sid2 = scheduler.add(prompt, secs, label=prompt[:40])
                    sched_loop.start()
                    print(f"  scheduled {sid2}: every {secs}s")
                else:
                    print("  usage: /schedule add <interval e.g. 5m> <prompt> | list | remove <id>")
                continue
            if low == "/workflows":
                from clims_core.workflows import list_workflows
                wfs = list_workflows(cwd)
                print("  " + (", ".join(wfs) if wfs else "no workflows (.clims/workflows/*.py)"))
                continue
            if low == "/workflow":
                toks = user.split()
                if len(toks) < 2:
                    print("  usage: /workflow <name>")
                    continue
                from clims_core.workflows import WorkflowAPI, run_workflow
                api = WorkflowAPI(provider=agent.provider, model=agent.model,
                                  api_key=agent.api_key, cwd=cwd,
                                  on_log=lambda m: print(f"  · {m}"))
                try:
                    res = run_workflow(toks[1], api, cwd=cwd)
                    print("\n" + (str(res) if res is not None else "(workflow done)"))
                except Exception as e:
                    print(f"  workflow error: {e}")
                continue
            if low == "/review":
                from clims_core.devtools import review_prompt
                rp = review_prompt(_git_diff(cwd))
                if not rp:
                    print("  no git diff to review (clean tree / not a git repo)")
                    continue
                user = rp  # fall through to run a review turn
            elif name in custom_commands:
                cmd_args = user[len("/" + name):].strip()
                user = expand_command(custom_commands[name], cmd_args)
            else:
                cont, history = _handle_slash(user, cfg, agent, history, totals, cwd)
                if cont == "exit":
                    print("bye.")
                    return 0
                continue

        # expand @file mentions into inline context
        from clims_core.mentions import expand_mentions
        user = expand_mentions(user, cwd)

        history.append(Message.user(user))
        if not markdown_mode:
            sys.stdout.write("clims > ")  # label for plain streaming mode
        # spinner while waiting for the first token (rich; no-op without it)
        from clims_cli import render
        from clims_cli.interrupt import run_interruptible
        render.hint("Esc or Ctrl-C to interrupt")
        sp = render.spinner("working — Esc to interrupt")
        sp.__enter__()
        stopped = {"v": False}

        def ev_sink(ev):
            if not stopped["v"] and ev.type in (
                    "text_delta", "thinking_delta", "tool_use", "tool_result", "error"):
                sp.stop()
                stopped["v"] = True
            on_event(ev)

        import threading as _threading
        cancel_event = _threading.Event()
        try:
            # run the turn on a worker thread; main thread watches for Esc/Ctrl-C
            result, interrupted = run_interruptible(
                lambda: agent.send(history, ev_sink, cancel=cancel_event), cancel_event)
        except Exception as e:  # never crash the REPL
            sp.stop()
            print(f"\n  [fatal] {type(e).__name__}: {e}")
            continue
        finally:
            sp.stop()
        if interrupted:
            print("\n  ⎿ interrupted — back to you (any running command was stopped)")
            if result is not None:  # keep the partial turn so context is consistent
                history = result.messages
            continue
        history = result.messages
        # final/intermediate text is rendered live by the event printer (flush on
        # tool_use/done), so no separate end-of-turn render is needed here.
        totals["in"] += result.input_tokens
        totals["out"] += result.output_tokens
        # persist + checkpoint after each turn (resume + rewind)
        checkpoints.checkpoint(history)
        try:
            store.set(sid, history)
        except Exception:
            pass
        render.status_line(cfg.provider, cfg.model, agent.runtime.policy.mode.value,
                           result.input_tokens, result.output_tokens)
        from clims_cli.notify import notify
        notify()  # ring the terminal bell when a turn completes (CLIMS_NOTIFY=0 to mute)

        # plan-mode approve→execute: if the agent produced a plan in plan mode, show it
        # and offer to switch to execution.
        plan = agent.runtime.ctx.jobs.pop("__plan__", None)
        if plan and agent.runtime.policy.mode == PermissionMode.PLAN:
            print()
            render.panel("plan ready — review", plan)
            try:
                ans = reader.read("  Approve & execute this plan? [y/N] > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans in ("y", "yes"):
                agent.runtime.policy.mode = PermissionMode.ACCEPT_EDITS
                pending_exec = "The plan is approved. Implement it now, step by step."
                print("  → switching to acceptEdits and executing the plan…")


def _parse_interval(s: str) -> int:
    """Parse '30s' / '5m' / '2h' / '90' (seconds) -> seconds."""
    s = s.strip().lower()
    mult = 1
    if s and s[-1] in "smh":
        mult = {"s": 1, "m": 60, "h": 3600}[s[-1]]
        s = s[:-1]
    try:
        return max(1, int(float(s)) * mult)
    except ValueError:
        return 300


def _run_research(agent, question: str):
    """Run the deep-research harness (parallel search+fetch+synthesize) and print it."""
    from clims_core.research import deep_research
    from clims_core.tools.web_search import search_web
    from clims_core.tools.web_fetch import fetch_url_text

    def llm_fn(prompt: str) -> str:
        out = []
        for ev in agent.provider.chat(model=agent.model, messages=[Message.user(prompt)],
                                      tools=None, system="You are a precise research assistant.",
                                      api_key=agent.api_key, stream=False, temperature=0,
                                      max_tokens=2000):
            if ev.type == "text_delta":
                out.append(ev.text)
        return "".join(out)

    from clims_cli import render
    result = deep_research(question, search_fn=search_web, fetch_fn=fetch_url_text,
                           llm_fn=llm_fn, on_log=lambda m: print(f"  · {m}"))
    print()
    render.render_markdown(result["report"] or "(no report)")
    if result.get("revised"):
        print("  \033[2m(report was revised to address the fact-check)\033[0m")
    if result.get("sources"):
        print("  \033[2msources: " + ", ".join(result["sources"]) + "\033[0m")


def _git_diff(cwd) -> str:
    import subprocess
    for args in (["git", "diff", "HEAD"], ["git", "diff"], ["git", "diff", "--staged"]):
        try:
            r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=20)
            if r.stdout.strip():
                return r.stdout
        except Exception:
            return ""
    return ""


def _handle_slash(user, cfg, agent, history, totals, cwd: Path = None):
    """Return (control, history). control is 'exit' to quit, else ''."""
    parts = user.split()
    cmd = parts[0]
    if cmd in ("/exit", "/quit"):
        return "exit", history
    if cmd == "/help":
        print("  commands: /help /model /tools /mcp /mode [name] /cost /clear /memory")
        print("            /init /compact /agents /commands /export [path] /permissions")
        print("            /config /doctor /status /diagnostics /update /vim /terminal-setup")
        print("  orchestration: /research <q> /bg <task> /tasks /bg-result <id>")
        print("            /schedule add|list|remove /workflow <name> /workflows")
        print("            (subagent agent_type: explore|plan|reviewer|researcher)")
        print("            plan mode -> agent proposes a plan -> you approve -> it executes")
        print("            /exit")
        return "", history
    if cmd == "/model":
        if len(parts) > 1:
            agent.model = parts[1]
            cfg.model = parts[1]
            print(f"  model -> {cfg.provider}:{agent.model}")
        else:
            print(f"  {cfg.provider}:{agent.model}")
        return "", history
    if cmd == "/style":
        from clims_core.styles import style_names
        if len(parts) > 1 and parts[1] in style_names():
            cfg.output_style = parts[1]
            print(f"  output style -> {parts[1]} (applies to new agent; /clear or restart to rebuild)")
        else:
            print(f"  styles: {', '.join(style_names())}  (current: {cfg.output_style or 'default'})")
        return "", history
    if cmd == "/auto":
        from clims_core.permissions.policy import PermissionMode
        p = agent.runtime.policy
        p.mode = (PermissionMode.DEFAULT if p.mode == PermissionMode.ACCEPT_EDITS
                  else PermissionMode.ACCEPT_EDITS)
        print(f"  auto-accept {'ON' if p.mode == PermissionMode.ACCEPT_EDITS else 'OFF'} "
              f"(mode={p.mode.value})")
        return "", history
    if cmd == "/hooks":
        hk = getattr(agent.runtime, "hooks", None)
        if hk and hk.config:
            print(f"  configured hook events: {', '.join(sorted(hk.config))}")
        else:
            print("  no hooks configured (settings['hooks'])")
        return "", history
    if cmd == "/tools":
        names = ", ".join(sorted(agent.runtime.tools))
        print(f"  {len(agent.runtime.tools)} tools: {names}")
        return "", history
    if cmd == "/mcp":
        from clims_core.mcp.registry import known_servers
        mgr = getattr(agent, "_mcp_mgr", None)
        if not mgr or not mgr.clients:
            print("  connected: none")
        else:
            print(f"  connected: {', '.join(mgr.clients)} · {len(mgr.tools())} tool(s)")
        print(f"  known servers (connect by name): {', '.join(known_servers())}")
        print('  tip: just ask — e.g. "connect github with <token>" or "connect filesystem for ./data"')
        return "", history
    if cmd == "/mode":
        from clims_core.permissions.policy import PermissionMode
        if len(parts) > 1:
            try:
                agent.runtime.policy.mode = PermissionMode(parts[1])
                print(f"  permission mode -> {parts[1]}")
            except ValueError:
                print("  modes: default | acceptEdits | plan | bypass")
        else:
            print(f"  mode: {agent.runtime.policy.mode.value}")
        return "", history
    if cmd == "/cost":
        print(f"  session: {totals['in']} input / {totals['out']} output tokens")
        return "", history
    if cmd == "/clear":
        print("  context cleared.")
        return "", []
    if cmd == "/memory":
        from clims_core.memory import load_memory
        cwd = Path.cwd()
        mem = load_memory(cwd)
        print(f"  CLIMS.md: {len(mem)} chars loaded" if mem else "  CLIMS.md: none")
        mem_dir = cwd / ".clims" / "memory"
        files = sorted(p.relative_to(mem_dir).as_posix()
                       for p in mem_dir.rglob("*") if p.is_file()) if mem_dir.is_dir() else []
        print(f"  .clims/memory/: {', '.join(files) if files else '(empty)'}")
        docs = [d for d in ("PROGRESS.md", "DECISIONS.md", "ARCHITECTURE.md") if (cwd / d).is_file()]
        print(f"  tracking docs: {', '.join(docs) if docs else '(none)'}")
        print(f"  proactive memory: {'on' if cfg.proactive_memory else 'off'}")
        return "", history
    if cmd == "/init":
        return "", _cmd_init(history)
    if cmd == "/compact":
        return "", _cmd_compact(agent, history)
    if cmd == "/agents":
        from clims_core.commands import load_agents
        agents = load_agents(Path.cwd())
        if agents:
            for n, a in agents.items():
                print(f"  {n}: {a.description or '(no description)'}")
        else:
            print("  no file-defined agents (.clims/agents/*.md)")
        return "", history
    if cmd == "/commands":
        from clims_core.commands import load_commands
        cmds = load_commands(Path.cwd())
        print("  " + (", ".join("/" + c for c in cmds) if cmds else "no custom commands"))
        return "", history
    if cmd == "/export":
        path = parts[1] if len(parts) > 1 else "clims_transcript.md"
        _cmd_export(history, Path(path))
        print(f"  exported {len(history)} messages -> {path}")
        return "", history
    if cmd == "/permissions":
        p = agent.runtime.policy
        print(f"  mode={p.mode.value}  allow={p.allow}  deny={p.deny}  ask={p.ask}")
        return "", history
    if cmd == "/config":
        import json as _json
        print(_json.dumps(cfg.redacted(), indent=2))
        return "", history
    if cmd in ("/doctor", "/status"):
        _cmd_doctor(cfg, agent)
        return "", history
    if cmd == "/diagnostics":
        from clims_core.diagnostics import load_diagnostics, format_diagnostics
        print("  " + format_diagnostics(load_diagnostics(Path.cwd())).replace("\n", "\n  "))
        return "", history
    if cmd == "/update":
        from clims_core.updater import current_version, update
        print(f"  current version {current_version()}")
        ok, out = update(run=(len(parts) > 1 and parts[1] == "now"))
        print(f"  {'ok' if ok else 'note'}: {out}")
        return "", history
    if cmd == "/vim":
        from clims_cli.prompt import prompt_toolkit_available
        if prompt_toolkit_available():
            print("  vim editing available — start with CLIMS_VIM=1 (pip install prompt_toolkit).")
        else:
            print("  install prompt_toolkit to enable vim editing, then set CLIMS_VIM=1.")
        return "", history
    if cmd == "/terminal-setup":
        from clims_core.keybindings import DEFAULTS
        kb = Path.cwd() / ".clims" / "keybindings.json"
        kb.parent.mkdir(parents=True, exist_ok=True)
        if not kb.exists():
            import json as _json
            kb.write_text(_json.dumps(DEFAULTS, indent=2), encoding="utf-8")
            print(f"  wrote default keybindings -> {kb}")
        else:
            print(f"  keybindings already exist at {kb}")
        print("  tip: bind Shift+Enter to insert a newline in your terminal for multi-line input.")
        return "", history
    if cmd == "/bot":
        sub = parts[1] if len(parts) > 1 else "status"
        if sub == "start":
            _start_telegram_bot(cwd, verbose=True)
        elif sub == "stop":
            _stop_telegram_bot(cwd)
        elif sub == "log":
            log_file = cwd / ".clims" / "_bot.log"
            if log_file.exists():
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines[-40:]:
                    print(f"  {line}")
            else:
                print("  [telegram] no log file yet")
        else:
            _bot_status(cwd)
        return "", history
    print(f"  unknown command {cmd} (/help for list)")
    return "", history


_CLIMS_TEMPLATE = """# Project memory (CLIMS.md)

This file is loaded into the agent's system prompt. Document project conventions,
key commands, and constraints here.

## Commands
- build: <how to build>
- test: <how to run tests>

## Conventions
- <coding style, patterns, do/don't>

## Notes
- <anything the agent should always know>
"""


def _cmd_init(history):
    target = Path.cwd() / "CLIMS.md"
    if target.exists():
        print("  CLIMS.md already exists — not overwriting.")
    else:
        target.write_text(_CLIMS_TEMPLATE, encoding="utf-8")
        print(f"  created {target}")
    return history


def _cmd_compact(agent, history):
    from clims_core.agent.compaction import compact
    if len(history) < 3:
        print("  nothing to compact.")
        return history
    cw = agent.provider.capabilities(agent.model).context_window
    new_hist, did = compact(history, agent._summarize, cw, trigger_frac=0.0)
    print(f"  compacted {len(history)} -> {len(new_hist)} messages" if did
          else "  no compaction performed.")
    return new_hist


def _cmd_export(history, path: Path):
    lines = ["# clims_code transcript", ""]
    for m in history:
        text = m.text()
        if text:
            lines.append(f"## {m.role}\n\n{text}\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _cmd_doctor(cfg, agent):
    import platform
    from clims_cli import render
    from clims_core.providers import available_providers
    mgr = getattr(agent, "_mcp_mgr", None)
    print("  clims_code doctor:")
    print(f"    python:    {platform.python_version()}")
    print(f"    provider:  {cfg.provider}:{cfg.model}  key={'set' if cfg.api_key else 'MISSING'}")
    print(f"    providers: {', '.join(available_providers())}")
    print(f"    tools:     {len(agent.runtime.tools)}")
    print(f"    mcp:       {len(mgr.clients) if mgr else 0} server(s)")
    print(f"    rich UI:   {'yes' if render.supports_rich() else 'no'}")
    print(f"    guard:     {'on' if agent.runtime.path_guard else 'off'}")
