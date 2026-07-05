"""Input layer with slash-command autocomplete + optional vim editing.

When prompt_toolkit is available and stdin is a TTY, input uses a PromptSession
with a completer that pops up the slash-command menu as you type `/` (and supports
history + vi keybindings). Otherwise it falls back to the stdlib input() so tests
and redirected/non-interactive use still work.
"""
from __future__ import annotations

import sys

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    _PT = True
except Exception:
    _PT = False
    Completer = object  # type: ignore


def prompt_toolkit_available() -> bool:
    return _PT


class SlashCompleter(Completer):
    """Completes slash commands when the line starts with '/'."""
    def __init__(self, commands: dict | None = None):
        # commands: {"/help": "list commands", ...}
        self.commands = dict(commands or {})

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        # only complete the command token (first word)
        if " " in text:
            return
        for name in sorted(self.commands):
            if name.startswith(text):
                yield Completion(name, start_position=-len(text),
                                 display=name, display_meta=self.commands[name])


class Input:
    def __init__(self, vim: bool = False, commands: dict | None = None,
                 status_fn=None):
        self._pt = _PT and sys.stdin.isatty()
        self.vim = vim and self._pt
        self.status_fn = status_fn
        self._session = None
        if self._pt:
            try:
                style = Style.from_dict({
                    # #1 highlighted input area: white text on a teal bar
                    "prompt": "bold #ffffff bg:#0087af",
                    "prompt.user": "bold #ffffff bg:#0087af",
                    # #3 status below input, yellow
                    "bottom-toolbar": "#ffd700 bg:#1c1c1c",
                })
                self._session = PromptSession(
                    completer=SlashCompleter(commands),
                    complete_while_typing=True,
                    history=InMemoryHistory(),
                    style=style,
                    bottom_toolbar=self._toolbar if status_fn else None,
                )
            except Exception:
                self._pt = False

    def _toolbar(self):
        try:
            return HTML(f" {self.status_fn()} ")
        except Exception:
            return ""

    def read(self, prompt: str = "you > ") -> str:
        if self._pt and self._session is not None:
            try:
                kw = {"editing_mode": EditingMode.VI} if self.vim else {}
                # highlighted prompt bar makes user messages easy to find in scrollback
                return self._session.prompt(HTML("<prompt> you ❯ </prompt>"), **kw)
            except Exception:
                pass
        return input(prompt)
