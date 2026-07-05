"""Keybindings config loader (~/.clims/keybindings.json or .clims/keybindings.json).

Returns an action->key map. Applied by the prompt_toolkit input layer when vim/
rich input is active; otherwise stored for reference. Ships sensible defaults.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULTS = {
    "submit": "enter",
    "newline": "escape+enter",
    "cancel": "c-c",
    "clear": "c-l",
    "history_prev": "up",
    "history_next": "down",
}


def load_keybindings(cwd: Path | None = None, home: Path | None = None) -> dict:
    cwd = cwd or Path.cwd(); home = home or Path.home()
    binds = dict(DEFAULTS)
    for p in (home / ".clims" / "keybindings.json", cwd / ".clims" / "keybindings.json"):
        if p.is_file():
            try:
                binds.update(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
    return binds
