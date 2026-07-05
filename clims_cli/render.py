"""Terminal rendering helpers for the CLI.

Uses `rich` when available for markdown, syntax-highlighted diffs, spinners, and a
status line; falls back to plain stdlib output otherwise. The engine never imports
this module — it is CLI-only (per ADR-002).
"""
from __future__ import annotations

import difflib
import sys as _sys

# ensure UTF-8 output BEFORE rich's Console is created, so block/glyph chars
# (logo, ⏺ ✓ →) never hit a cp1252 console encoder and crash.
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.table import Table
    from rich.panel import Panel
    _RICH = True
    # Force UTF-8 on Windows where the default console code page is cp1252.
    # We write to stdout.buffer directly so emoji / box-drawing chars never hit
    # the cp1252 encoder.
    import io as _io
    _utf8_stdout = _io.TextIOWrapper(
        _sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    _console = Console(file=_utf8_stdout, highlight=False)
except Exception:  # rich not installed -> graceful fallback
    _RICH = False
    _console = None

_STATUS_STYLE = {"running": "yellow", "done": "green", "error": "red"}
_STATUS_MARK = {"running": "…", "done": "✓", "error": "✗"}

# pixelated block logo (ANSI Shadow)
LOGO = r"""
 ██████╗██╗     ██╗███╗   ███╗███████╗
██╔════╝██║     ██║████╗ ████║██╔════╝
██║     ██║     ██║██╔████╔██║███████╗
██║     ██║     ██║██║╚██╔╝██║╚════██║
╚██████╗███████╗██║██║ ╚═╝ ██║███████║
 ╚═════╝╚══════╝╚═╝╚═╝     ╚═╝╚══════╝"""


def print_logo(version: str = "", tagline: str = "general-purpose agent for all digital work") -> None:
    meta = f"  v{version}  ·  {tagline}" if version else f"  {tagline}"
    try:
        if _RICH:
            shades = ["#5fffff", "#00d7ff", "#00afff", "#0087ff", "#0087d7", "#005faf"]
            for i, line in enumerate(LOGO.strip("\n").splitlines()):
                _console.print(Text(line, style=f"bold {shades[i % len(shades)]}"))
            _console.print(Text(meta, style="dim"))
            return
        print(LOGO)
        print(meta)
        return
    except Exception:
        pass
    # last-resort plain fallback (never crash startup on any console)
    try:
        print(LOGO)
        print(meta)
    except Exception:
        print("CLIMS" + meta)


def supports_rich() -> bool:
    return _RICH


def hint(text: str) -> None:
    """A dim one-line hint (e.g. 'Ctrl-C to interrupt')."""
    if _RICH:
        _console.print(Text("  · " + text, style="dim"))
    else:
        print(f"  \033[2m· {text}\033[0m")


def render_markdown(text: str) -> None:
    if _RICH and text.strip():
        _console.print(Markdown(text))
    else:
        print(text)


def unified_diff(old: str, new: str, path: str = "") -> str:
    """Plain unified diff string (used by tools and as a rich fallback)."""
    diff = difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="",
    )
    return "\n".join(diff)


def print_diff(old: str, new: str, path: str = "") -> None:
    diff_text = unified_diff(old, new, path)
    if not diff_text:
        return
    if _RICH:
        _console.print(Syntax(diff_text, "diff", theme="ansi_dark", word_wrap=True))
    else:
        print(diff_text)


def status_text(provider: str, model: str, mode: str,
                in_tokens: int, out_tokens: int) -> str:
    return f"{provider}:{model}  ·  mode={mode}  ·  {in_tokens} in / {out_tokens} out tokens"


def status_line(provider: str, model: str, mode: str,
                in_tokens: int, out_tokens: int) -> None:
    msg = status_text(provider, model, mode, in_tokens, out_tokens)
    if _RICH:
        _console.print(Text("  " + msg, style="yellow"))
    else:
        print(f"  \033[33m{msg}\033[0m")  # yellow


def _trunc(s: str, n: int = 100) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[:n] + "…"


def _arg_summary(tool_input: dict) -> str:
    # show the most salient argument (command/path/url/query/pattern), else compact dict
    for k in ("command", "path", "url", "query", "pattern", "task", "question"):
        if k in (tool_input or {}):
            return _trunc(str(tool_input[k]), 80)
    return _trunc(", ".join(f"{k}={v}" for k, v in (tool_input or {}).items()), 80)


def print_tool_call(name: str, tool_input: dict) -> None:
    """Claude-Code-style tool line: ⏺ tool(arg)."""
    summary = _arg_summary(tool_input)
    if _RICH:
        _console.print(f"[bold cyan]⏺[/bold cyan] [cyan]{name}[/cyan]"
                       f"([white]{summary}[/white])")
    else:
        print(f"\n  > {name}({summary})")


def print_tool_result(content: str, is_error: bool) -> None:
    """Indented, dimmed result summary under the tool call: ⎿ ✓ result."""
    body = (content or "").strip()
    first = body.splitlines()[0] if body else "(no output)"
    extra = len(body.splitlines()) - 1
    tail = f"  (+{extra} lines)" if extra > 0 else ""
    if _RICH:
        style = "red" if is_error else "green"
        mark = "✗" if is_error else "✓"
        _console.print(f"  [dim]⎿[/dim] [{style}]{mark}[/{style}] "
                       f"[dim]{_trunc(first, 100)}{tail}[/dim]")
    else:
        print(f"  {'x' if is_error else 'ok'} {_trunc(first, 100)}{tail}")


def task_line(task) -> str:
    """One-line plain formatter for a background task (testable)."""
    mark = _STATUS_MARK.get(task.status, "?")
    return f"{mark} {task.id} [{task.status}] {task.label}"


def print_tasks(tasks) -> None:
    if not tasks:
        print("  no background tasks")
        return
    if _RICH:
        table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        table.add_column("id"); table.add_column("status"); table.add_column("label")
        for t in tasks:
            table.add_row(t.id, f"[{_STATUS_STYLE.get(t.status,'white')}]{t.status}[/]", t.label)
        _console.print(table)
    else:
        for t in tasks:
            print("  " + task_line(t))


def panel(title: str, body: str) -> None:
    if _RICH:
        _console.print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "─" * max(8, min(60, len(title) + 4))
        print(f"  ┌─ {title} {bar}")
        for line in body.splitlines():
            print(f"  │ {line}")
        print(f"  └{'─' * (len(title) + len(bar) + 4)}")


def status_summary(pending_tasks: int, schedules: int) -> str:
    """Short pending-work summary (testable)."""
    bits = []
    if pending_tasks:
        bits.append(f"{pending_tasks} bg task(s) running")
    if schedules:
        bits.append(f"{schedules} schedule(s)")
    return " · ".join(bits)


class spinner:
    """Context manager: a 'thinking' spinner while waiting for the first token."""
    def __init__(self, label: str = "thinking"):
        self.label = label
        self._status = None

    def __enter__(self):
        if _RICH:
            self._status = _console.status(f"[dim]{self.label}…[/dim]", spinner="dots")
            self._status.__enter__()
        return self

    def stop(self):
        if self._status is not None:
            self._status.__exit__(None, None, None)
            self._status = None

    def __exit__(self, *exc):
        self.stop()
        return False
